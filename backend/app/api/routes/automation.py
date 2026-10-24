"""Endpoints for n8n (or any scheduler). Protected by AUTOMATION_API_KEY in the X-API-Key header.

Delivery is two-step so a notification is neither lost nor repeated: each endpoint returns content plus
`delivery_keys`; after the workflow has actually sent it, it calls POST /automation/deliveries with those keys.
Items already recorded are left out (or flagged) on the next run.
"""

import hmac
from datetime import date, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import defer

from app.api.deps import DbSession, OrgId
from app.api.routes.anomalies import ANALYSIS_TYPE, SEVERITY_RANK
from app.api.routes.reports import attachment, summary
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.ratelimit import rate_limit
from app.models import AnalysisRun, AutomationEvent, DataImport, Report, utcnow
from app.services.ai import insights
from app.services.ai.gemini import AiError, get_ai_client
from app.services.analytics import metrics
from app.services.analytics.metrics import Filters
from app.services.anomaly_detection.detector import DetectionConfig, detect
from app.services.organization import data_mix
from app.services.reports.service import CONTENT_TYPES, generate_report


def require_automation_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    expected = get_settings().automation_api_key
    if not expected:
        raise AppError(503, "Automation is disabled: AUTOMATION_API_KEY is not set on the server.",
                       code="automation_disabled")
    if not x_api_key or not hmac.compare_digest(x_api_key.encode(), expected.encode()):
        raise AppError(401, "Missing or invalid X-API-Key.", code="unauthorized")


router = APIRouter(prefix="/automation", tags=["automation"],
                   dependencies=[Depends(require_automation_key), Depends(rate_limit("automation", 30))])

PeriodName = Literal["last_7_days", "last_30_days", "previous_week", "previous_month"]
Anchor = Literal["today", "latest_data"]


def resolve(period: PeriodName, anchor: Anchor, db, org_id: int) -> Filters:
    """Periods end on the anchor day: today (production) or the latest order date (historical/demo data)."""
    end = date.today()
    if anchor == "latest_data":
        end = metrics.filter_options(db, org_id)["date_max"] or end
    if period == "last_7_days":
        return Filters(end - timedelta(days=6), end)
    if period == "last_30_days":
        return Filters(end - timedelta(days=29), end)
    if period == "previous_week":  # last complete Monday-Sunday week before the anchor
        last_sunday = end - timedelta(days=end.weekday() + 1)
        return Filters(last_sunday - timedelta(days=6), last_sunday)
    first_this_month = end.replace(day=1)  # previous complete calendar month
    last_prev = first_this_month - timedelta(days=1)
    return Filters(last_prev.replace(day=1), last_prev)


def delivered(db, org_id: int, workflow: str, keys: list[str]) -> set[str]:
    if not keys:
        return set()
    return set(db.scalars(select(AutomationEvent.item_key).where(
        AutomationEvent.organization_id == org_id, AutomationEvent.workflow == workflow,
        AutomationEvent.item_key.in_(keys))))


def fmt_kpi(k: dict) -> str:
    value = k["value"]
    if value is None:
        shown = "n/a"
    elif k["unit"] == "currency":
        shown = f"${value:,.2f}"
    elif k["unit"] == "percent":
        shown = f"{value:.1f}%"
    else:
        shown = f"{value:,.0f}"
    if k["unit"] == "percent":
        change = "n/a" if k["abs_change"] is None else f"{k['abs_change']:+.1f} pp"
    else:
        change = "n/a" if k["pct_change"] is None else f"{k['pct_change']:+.1f}%"
    return f"{k['label']}: {shown} ({change})"


class SummaryRequest(BaseModel):
    period: PeriodName = "last_7_days"
    anchor: Anchor = "today"
    include_ai: bool = False


@router.post("/kpi-summary")
def kpi_summary(body: SummaryRequest, db: DbSession, org_id: OrgId):
    f = resolve(body.period, body.anchor, db, org_id)
    kpis = metrics.kpis_with_comparison(db, org_id, f)
    drivers = metrics.change_drivers(db, org_id, f, "category")[:3]
    synthetic = data_mix(db, org_id)[0] in ("synthetic", "mixed")
    key = f"{body.period}:{f.start_date.isoformat()}"
    lines = [f"Analyst IQ KPI summary, {f.start_date.isoformat()} to {f.end_date.isoformat()} "
             f"(vs previous {f.days} days)"]
    if synthetic:
        lines.append("Note: synthetic demo data, not real business performance.")
    lines += [fmt_kpi(k) for k in kpis if k["key"] in ("net_revenue", "gross_profit", "gross_margin_pct", "orders",
                                                         "avg_order_value", "return_rate_pct")]
    if drivers:
        lines.append("Largest category movers: " + "; ".join(
            f"{d['label']} {'+' if d['change'] >= 0 else '-'}${abs(float(d['change'])):,.2f}" for d in drivers))
    ai = None
    if body.include_ai:
        try:
            record, cached = insights.generate_insight(
                db, org_id, get_ai_client(), "executive_summary",
                "Write a short executive summary of this period for a weekly email.",
                insights.executive_summary_evidence(db, org_id, f), params={"automation": key})
            ai = {"title": record.output["title"], "summary": record.output["summary"], "cached": cached,
                  "label": "AI interpretation of the verified metrics above"}
        except (AiError, AppError) as exc:  # the deterministic summary still goes out
            ai = {"error": getattr(exc, "code", "ai_error")}
    return {"workflow": "kpi_summary", "delivery_keys": [key],
            "should_notify": not delivered(db, org_id, "kpi_summary", [key]),
            "period": {"start_date": f.start_date, "end_date": f.end_date, "days": f.days},
            "contains_synthetic": synthetic, "kpis": kpis, "message": "\n".join(lines), "ai": ai}


class AnomalyAlertRequest(BaseModel):
    min_severity: Literal["high", "medium", "low"] = "high"
    run_detection: bool = True


@router.post("/anomaly-alerts")
def anomaly_alerts(body: AnomalyAlertRequest, db: DbSession, org_id: OrgId):
    if body.run_detection:
        run = AnalysisRun(organization_id=org_id, analysis_type=ANALYSIS_TYPE, params={"source": "automation"},
                          result=detect(db, org_id, DetectionConfig()))
        db.add(run)
        db.commit()
    else:
        run = db.scalar(select(AnalysisRun).where(AnalysisRun.organization_id == org_id,
                                                  AnalysisRun.analysis_type == ANALYSIS_TYPE)
                        .order_by(AnalysisRun.id.desc()).limit(1))
        if run is None:
            raise AppError(404, "Anomaly detection has not been run yet.")
    wanted = [a for a in run.result.get("anomalies", [])
              if SEVERITY_RANK[a["severity"]] <= SEVERITY_RANK[body.min_severity]]
    done = delivered(db, org_id, "anomaly_alert", [a["key"] for a in wanted])
    new = [a for a in wanted if a["key"] not in done]
    lines = [f"Analyst IQ: {len(new)} new anomal{'y' if len(new) == 1 else 'ies'} "
             f"(severity {body.min_severity} or higher). Statistical deviations, not confirmed problems."]
    for a in new[:10]:
        change = (f"{a['abs_diff']:+.1f} pp" if a["metric"].endswith("_pct")
                  else f"{a['pct_diff']:+.0f}%" if a["pct_diff"] is not None else "")
        lines.append(f"- [{a['severity']}] {a['dimension']} {a['segment_label']}, {a['metric_label']}, "
                     f"{a['period_start']} to {a['period_end']}: {a['observed']:g} vs {a['expected']:g} "
                     f"expected ({change})")
    if len(new) > 10:
        lines.append(f"...and {len(new) - 10} more in the AI Insights page.")
    return {"workflow": "anomaly_alert", "analysis_run_id": run.id, "should_notify": bool(new),
            "delivery_keys": [a["key"] for a in new], "already_delivered": len(done),
            "anomalies": new, "message": "\n".join(lines)}


class AutomationReportRequest(BaseModel):
    type: Literal["executive", "sales", "product", "store", "customer", "profitability"] = "executive"
    format: Literal["pdf", "csv"] = "pdf"
    period: PeriodName = "previous_week"
    anchor: Anchor = "today"


@router.post("/reports")
def scheduled_report(body: AutomationReportRequest, db: DbSession, org_id: OrgId):
    f = resolve(body.period, body.anchor, db, org_id)
    params = {"type": body.type, "format": body.format, "start_date": f.start_date.isoformat(),
              "end_date": f.end_date.isoformat(), "store": [], "category": [], "channel": []}
    # Idempotent per type/format/period: a retried or duplicated schedule reuses the existing file.
    existing = next((r for r in db.scalars(select(Report).options(defer(Report.content)).where(
        Report.organization_id == org_id, Report.report_type == body.type, Report.file_format == body.format,
        Report.requested_by == "automation").order_by(Report.id.desc()).limit(50)) if r.params == params), None)
    record = existing or generate_report(db, org_id, body.type, body.format, f, params, requested_by="automation")
    key = f"report:{record.id}"
    return {"workflow": "scheduled_report", "reused": existing is not None, "report": summary(record),
            "download_path": f"/api/v1/automation/reports/{record.id}/download", "delivery_keys": [key],
            "should_notify": not delivered(db, org_id, "scheduled_report", [key])}


@router.get("/reports/{report_id}/download")
def automation_download(report_id: int, db: DbSession, org_id: OrgId) -> Response:
    record = db.get(Report, report_id)
    if record is None or record.organization_id != org_id:
        raise AppError(404, "Report not found.")
    return attachment(record.content, record.filename, CONTENT_TYPES[record.file_format])


@router.get("/imports/latest")
def latest_import(db: DbSession, org_id: OrgId):
    record = db.scalar(select(DataImport).where(DataImport.organization_id == org_id,
                                                DataImport.status != "processing")
                       .order_by(DataImport.id.desc()).limit(1))
    if record is None:
        return {"workflow": "import_notification", "should_notify": False, "delivery_keys": [], "import": None,
                "message": "No imports yet."}
    key = f"import:{record.id}"
    message = (f"Analyst IQ import #{record.id} ({record.filename}): {record.status}. {record.message or ''} "
               f"Rows accepted {record.rows_accepted:,}, rejected {record.rows_rejected:,}.").strip()
    return {"workflow": "import_notification", "delivery_keys": [key],
            "should_notify": not delivered(db, org_id, "import_notification", [key]),
            "import": {"id": record.id, "filename": record.filename, "status": record.status,
                       "source": record.source, "rows_received": record.rows_received,
                       "rows_accepted": record.rows_accepted, "rows_rejected": record.rows_rejected,
                       "finished_at": record.finished_at, "message": record.message},
            "message": message}


class DeliveryRequest(BaseModel):
    workflow: Literal["kpi_summary", "anomaly_alert", "scheduled_report", "import_notification"]
    item_keys: list[str] = Field(min_length=1, max_length=200)


@router.post("/deliveries")
def record_deliveries(body: DeliveryRequest, db: DbSession, org_id: OrgId):
    """Record that items were delivered. Idempotent: keys already recorded are ignored."""
    rows = [{"organization_id": org_id, "workflow": body.workflow, "item_key": k[:250]} for k in set(body.item_keys)]
    dialect = db.get_bind().dialect.name
    insert_ = postgresql.insert if dialect == "postgresql" else sqlite.insert
    stmt = insert_(AutomationEvent.__table__).on_conflict_do_nothing(
        index_elements=["organization_id", "workflow", "item_key"])
    # Count rows RETURNING actually gives back: driver rowcount is -1 for this statement on psycopg.
    table = AutomationEvent.__table__
    created = sum(len(db.connection().execute(stmt.values(**r, created_at=utcnow()).returning(table.c.id)).all())
                  for r in rows)
    db.commit()
    return {"workflow": body.workflow, "recorded": created, "already_recorded": len(rows) - created}
