"""AI insights: build verified evidence, ask Gemini to interpret it, validate, persist.

The model never sees raw rows or customer identifiers — only the named facts built here from the KPI engine and
the anomaly detector. Its output is checked by grounding.unverified_numbers before anything is saved or shown.
"""

import hashlib
import json
import logging
import time
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models import AiInsight, AnalysisRun
from app.services.ai.gemini import AiError, JsonModel, call_with_retry
from app.services.ai.grounding import allowed_values, fact, unverified_numbers
from app.services.analytics import metrics
from app.services.analytics.metrics import Filters

log = logging.getLogger("analyst_iq.ai")
PROMPT_VERSION = "2026-10-1"
LIMITS = {"observed_facts": 8, "possible_explanations": 5, "recommended_investigations": 5,
          "information_needed": 5, "limitations": 5}


# ---------------------------------------------------------------- output contract

class ObservedFact(BaseModel):
    statement: str
    evidence_key: str


class Investigation(BaseModel):
    action: str
    reason: str


class InsightOutput(BaseModel):
    """Schema Gemini must fill. Facts, hypotheses and next steps are kept apart on purpose."""
    title: str
    summary: str
    answerable: bool
    observed_facts: list[ObservedFact]
    possible_explanations: list[str]
    recommended_investigations: list[Investigation]
    information_needed: list[str]
    limitations: list[str]


SYSTEM_PROMPT = """You are the analytics assistant inside Analyst IQ, a retail analytics product.
You interpret VERIFIED facts computed by a deterministic analytics engine. You never calculate.

Rules:
1. Use only the facts provided. Every number you write must come from a fact's "display" value (rounding is fine).
   Do not compute differences, ratios, totals or forecasts that are not in the facts.
2. Each observed_fact states one verified fact and cites exactly one evidence_key from the facts list.
3. possible_explanations are hypotheses. Phrase them as possibilities ("may", "could"), never as established causes.
   Correlation is not causation.
4. An anomaly is a statistical deviation, not a confirmed problem. Never call anything fraud.
5. recommended_investigations are concrete checks a manager could run, each with a reason tied to the facts.
6. If the facts cannot answer the request, set answerable to false and say what data is missing in
   information_needed. Do not guess.
7. The data is synthetic demo data. Be concise: title at most 12 words, summary at most 3 sentences."""


# ---------------------------------------------------------------- evidence builders

def period_facts(f: Filters, prefix: str = "period") -> list[dict]:
    prev = f.previous_period()
    return [fact(f"{prefix}.current", "Selected period", f"{f.start_date.isoformat()} to {f.end_date.isoformat()}"),
            fact(f"{prefix}.comparison", "Comparison period (previous equal-length period)",
                 f"{prev.start_date.isoformat()} to {prev.end_date.isoformat()}"),
            fact(f"{prefix}.days", "Days in each period", f.days, "count")]


def kpi_facts(db: Session, org_id: int, f: Filters) -> list[dict]:
    out = []
    for k in metrics.kpis_with_comparison(db, org_id, f):
        unit = {"currency": "currency", "percent": "percent", "count": "count"}[k["unit"]]
        out += [fact(f"kpi.{k['key']}.current", f"{k['label']} (selected period)", k["value"], unit),
                fact(f"kpi.{k['key']}.previous", f"{k['label']} (comparison period)", k["previous"], unit)]
        if k["unit"] == "percent":
            out.append(fact(f"kpi.{k['key']}.change_pp", f"{k['label']} change", k["abs_change"], "pp"))
        else:
            out += [fact(f"kpi.{k['key']}.change", f"{k['label']} absolute change", k["abs_change"], unit),
                    fact(f"kpi.{k['key']}.change_pct", f"{k['label']} % change", k["pct_change"], "percent")]
    return out


def driver_facts(db: Session, org_id: int, f: Filters, dimension: str, top: int = 5) -> list[dict]:
    out = []
    for r in metrics.change_drivers(db, org_id, f, dimension)[:top]:
        key = f"{dimension}.{r['key']}"
        label = r["label"] if dimension != "channel" else r["key"].replace("_", "-")
        out += [fact(f"{key}.net_revenue", f"{label} net revenue (selected period)", r["net_revenue"], "currency"),
                fact(f"{key}.previous_net_revenue", f"{label} net revenue (comparison period)",
                     r["previous_net_revenue"], "currency"),
                fact(f"{key}.change", f"{label} net revenue change", r["change"], "currency"),
                fact(f"{key}.change_pct", f"{label} net revenue % change", r["change_pct"], "percent"),
                fact(f"{key}.share_of_total_change", f"{label} share of total revenue change",
                     r["share_of_total_change_pct"], "percent"),
                fact(f"{key}.gross_margin_pct", f"{label} gross margin (selected period)", r["gross_margin_pct"],
                     "percent")]
    return out


def anomaly_facts(a: dict, prefix: str) -> list[dict]:
    unit = "percent" if a["metric"].endswith("_pct") else "currency" if a["metric"] == "net_revenue" else "count"
    out = [fact(f"{prefix}.what", "Anomaly", f"{a['metric_label']} for {a['dimension']} {a['segment_label']}"),
           fact(f"{prefix}.period", "Affected period", f"{a['period_start']} to {a['period_end']}"),
           fact(f"{prefix}.observed", "Observed value", a["observed"], unit),
           fact(f"{prefix}.expected", "Baseline / expected value", a["expected"], unit),
           fact(f"{prefix}.abs_diff", "Difference from baseline", a["abs_diff"], unit),
           fact(f"{prefix}.pct_diff", "% difference from baseline", a["pct_diff"], "percent"),
           fact(f"{prefix}.severity", "Statistical severity", a["severity"]),
           fact(f"{prefix}.method", "Detection method", a["method"])]
    if a.get("z_score") is not None:
        out.append(fact(f"{prefix}.z_score", "z-score", a["z_score"], "number"))
    for k, v in a.get("evidence", {}).items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out.append(fact(f"{prefix}.evidence.{k}", k.replace("_", " "), v, "number"))
        elif isinstance(v, str):
            out.append(fact(f"{prefix}.evidence.{k}", k.replace("_", " "), v))
    return out


def latest_anomalies(db: Session, org_id: int, f: Filters | None = None, limit: int = 5,
                     dimension: str | None = None) -> tuple[int | None, list[dict]]:
    run = db.scalar(select(AnalysisRun).where(AnalysisRun.organization_id == org_id,
                                              AnalysisRun.analysis_type == "anomaly_detection")
                    .order_by(AnalysisRun.id.desc()).limit(1))
    if run is None:
        return None, []
    items = run.result.get("anomalies", [])
    if f is not None:
        items = [a for a in items if a["period_end"] >= f.start_date.isoformat()
                 and a["period_start"] <= f.end_date.isoformat()]
    if dimension:
        items = [a for a in items if a["dimension"] == dimension]
    return run.id, items[:limit]


def filter_facts(f: Filters) -> list[dict]:
    parts = [("store", f.stores), ("category", f.categories), ("channel", f.channels)]
    applied = "; ".join(f"{name}: {', '.join(values)}" for name, values in parts if values) or "none (whole business)"
    return [fact("filters", "Filters applied", applied)]


def executive_summary_evidence(db: Session, org_id: int, f: Filters) -> dict:
    facts = period_facts(f) + filter_facts(f) + kpi_facts(db, org_id, f)
    for dimension in ("category", "store", "channel"):
        facts += driver_facts(db, org_id, f, dimension, top=4)
    run_id, anomalies = latest_anomalies(db, org_id, f)
    for i, a in enumerate(anomalies, start=1):
        facts += anomaly_facts(a, f"anomaly_{i}")
    if run_id is None:
        facts.append(fact("anomalies", "Anomaly detection", "not run yet"))
    return {"facts": facts, "analysis_run_id": run_id}


# ---------------------------------------------------------------- generation

def _cache_key(kind: str, model: str, evidence: dict, question: str | None) -> str:
    payload = json.dumps([kind, PROMPT_VERSION, model, evidence["facts"], (question or "").strip().lower()],
                         sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def check_rate_limit(db: Session, org_id: int) -> None:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    scope = (AiInsight.organization_id == org_id, AiInsight.model != "rules")
    last_minute = db.scalar(select(func.count()).select_from(AiInsight)
                            .where(*scope, AiInsight.created_at >= now - timedelta(minutes=1)))
    last_day = db.scalar(select(func.count()).select_from(AiInsight)
                         .where(*scope, AiInsight.created_at >= now - timedelta(days=1)))
    if last_minute >= settings.ai_max_requests_per_minute or last_day >= settings.ai_max_requests_per_day:
        raise AppError(429, "AI request limit reached for now. Cached insights are still available; try again later.",
                       code="rate_limited")


def validate_output(raw: str, facts: list[dict], extra_numbers: list[float] = ()) -> tuple[dict, dict]:
    """Parse, enforce the schema, and drop or reject anything with numbers that are not in the evidence."""
    try:
        output = InsightOutput.model_validate_json(raw)
    except ValidationError:
        raise AiError("ai_invalid_response", "Gemini returned a response that does not match the expected format.",
                      502)
    allowed = allowed_values(facts, extra_numbers)
    keys = {f["key"] for f in facts}
    for field in ("title", "summary"):
        bad = unverified_numbers(getattr(output, field), allowed)
        if bad:
            raise AiError("ai_ungrounded", f"The AI {field} contained numbers not found in the verified metrics "
                                           f"({', '.join(f'{b:g}' for b in bad[:3])}), so it was discarded.", 502)
    dropped: list[dict] = []
    kept_facts = []
    for item in output.observed_facts:
        bad = unverified_numbers(item.statement, allowed)
        if item.evidence_key not in keys or bad:
            reason = "unknown evidence key" if item.evidence_key not in keys else "numbers not in evidence"
            dropped.append({"field": "observed_facts", "text": item.statement, "reason": reason})
        else:
            kept_facts.append(item)
    output.observed_facts = kept_facts

    def keep(field: str, items: list, text_of) -> list:
        kept = []
        for item in items:
            if unverified_numbers(text_of(item), allowed):
                dropped.append({"field": field, "text": text_of(item), "reason": "numbers not in evidence"})
            else:
                kept.append(item)
        return kept[:LIMITS[field]]

    output.possible_explanations = keep("possible_explanations", output.possible_explanations, str)
    output.recommended_investigations = keep("recommended_investigations", output.recommended_investigations,
                                             lambda i: f"{i.action} {i.reason}")
    output.information_needed = keep("information_needed", output.information_needed, str)
    output.limitations = keep("limitations", output.limitations, str)
    output.observed_facts = output.observed_facts[:LIMITS["observed_facts"]]
    return output.model_dump(), {"dropped": dropped, "numbers_checked": True}


def generate_insight(db: Session, org_id: int, client: JsonModel, kind: str, task: str, evidence: dict,
                     params: dict, question: str | None = None, intent: dict | None = None,
                     refresh: bool = False, extra_numbers: list[float] = ()) -> tuple[AiInsight, bool]:
    """Returns (insight, from_cache). Failed attempts are stored and then raised as AppError."""
    cache_key = _cache_key(kind, client.model, evidence, question)
    if not refresh:
        cached = db.scalar(select(AiInsight).where(
            AiInsight.organization_id == org_id, AiInsight.cache_key == cache_key, AiInsight.status == "completed")
            .order_by(AiInsight.id.desc()).limit(1))
        if cached is not None:
            return cached, True
    check_rate_limit(db, org_id)

    prompt = (f"Task: {task}\n" + (f"User question: {question}\n" if question else "")
              + "Verified facts (JSON list; cite evidence_key from 'key', copy numbers from 'display'):\n"
              + json.dumps([{k: f[k] for k in ("key", "label", "display")} for f in evidence["facts"]], indent=1))
    record = AiInsight(organization_id=org_id, insight_type=kind, cache_key=cache_key, question=question,
                       params=params, intent=intent, evidence=evidence, model=client.model,
                       prompt_version=PROMPT_VERSION, analysis_run_id=evidence.get("analysis_run_id"))
    started = time.perf_counter()
    try:
        raw = call_with_retry(client, SYSTEM_PROMPT, prompt, InsightOutput)
        record.output, record.validation = validate_output(raw, evidence["facts"], extra_numbers)
        record.status = "completed"
    except AiError as exc:
        record.status, record.error_code, record.error_message = "failed", exc.code, exc.message
        log.warning("insight generation failed: %s", exc.code)
    record.duration_ms = int((time.perf_counter() - started) * 1000)
    db.add(record)
    db.commit()
    if record.status == "failed":
        raise AppError(_status_for(record.error_code), record.error_message, code=record.error_code,
                       details=[{"insight_id": record.id}])
    return record, False


def _status_for(code: str) -> int:
    return {"ai_rate_limited": 429, "ai_timeout": 504, "ai_auth_failed": 503, "ai_model_not_found": 503,
            "ai_not_configured": 503}.get(code, 502)
