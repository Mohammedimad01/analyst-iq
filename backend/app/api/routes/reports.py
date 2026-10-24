from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import defer

from app.api.deps import AnalyticsFilters, DbSession, OrgId
from app.api.routes.insights import FilterBody
from app.core.errors import AppError
from app.core.ratelimit import rate_limit
from app.models import Report
from app.schemas import ReportList, ReportSummary
from app.services.analytics.metrics import Filters
from app.services.reports import builder
from app.services.reports.render import single_table_csv
from app.services.reports.service import CONTENT_TYPES, generate_report

router = APIRouter(tags=["reports"])

ReportType = Literal["executive", "sales", "product", "store", "customer", "profitability"]


class ReportRequest(FilterBody):
    type: ReportType
    format: Literal["pdf", "csv"] = "pdf"


def summary(r: Report) -> dict:
    return {"id": r.id, "report_type": r.report_type, "title": r.title, "file_format": r.file_format,
            "filename": r.filename, "size_bytes": r.size_bytes, "contains_synthetic": r.contains_synthetic,
            "requested_by": r.requested_by, "params": r.params, "created_at": r.created_at,
            "duration_ms": r.duration_ms}


@router.post("/reports/generate", response_model=ReportSummary, status_code=201,
             dependencies=[Depends(rate_limit("report", 10))])
def create_report(body: ReportRequest, db: DbSession, org_id: OrgId):
    if body.start_date is None:
        raise AppError(422, "start_date and end_date are required")
    record = generate_report(db, org_id, body.type, body.format, body.to_filters(),
                             body.model_dump(mode="json"))
    return summary(record)


@router.get("/reports", response_model=ReportList)
def list_reports(db: DbSession, org_id: OrgId, limit: Annotated[int, Query(ge=1, le=50)] = 20,
                 offset: Annotated[int, Query(ge=0)] = 0):
    scope = Report.organization_id == org_id
    total = db.scalar(select(func.count()).select_from(Report).where(scope))
    rows = db.scalars(select(Report).options(defer(Report.content)).where(scope)
                      .order_by(Report.id.desc()).limit(limit).offset(offset))
    return {"total": total, "limit": limit, "offset": offset, "items": [summary(r) for r in rows]}


def attachment(content: bytes, filename: str, content_type: str) -> Response:
    return Response(content, media_type=content_type, headers={
        "Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff"})


@router.get("/reports/{report_id}/download")
def download_report(report_id: int, db: DbSession, org_id: OrgId):
    record = db.get(Report, report_id)
    if record is None or record.organization_id != org_id:
        raise AppError(404, "Report not found.")
    return attachment(record.content, record.filename, CONTENT_TYPES[record.file_format])


# ---------------------------------------------------------------- single-table CSV exports

Dataset = Literal["kpis", "trend", "products", "categories", "stores", "channels", "customers", "customer-segments",
                  "anomalies"]


def export_table(db, org_id: int, dataset: str, f: Filters) -> builder.Table:
    dims = {"products": "product", "categories": "category", "stores": "store", "channels": "channel"}
    if dataset in dims:
        return builder.breakdown_table(db, org_id, f, dims[dataset], dataset, show_key=dataset != "categories")
    if dataset == "kpis":
        return builder.kpi_table(db, org_id, f)
    if dataset == "trend":
        return builder.trend_table(db, org_id, f)
    if dataset == "anomalies":
        return builder.anomaly_table(db, org_id, f)
    _, segments_t, top_t = builder.customer_tables(db, org_id, f)
    return top_t if dataset == "customers" else segments_t


@router.get("/exports/{dataset}.csv", dependencies=[Depends(rate_limit("export", 30))])
def export_csv(dataset: Dataset, db: DbSession, org_id: OrgId, f: AnalyticsFilters):
    table = export_table(db, org_id, dataset, f)
    name = f"analyst-iq-{dataset}-{f.start_date.isoformat()}-to-{f.end_date.isoformat()}.csv"
    return attachment(single_table_csv(table), name, CONTENT_TYPES["csv"])
