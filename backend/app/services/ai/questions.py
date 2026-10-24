"""Natural-language questions through an allow-list of intents.

1. Gemini maps the question onto QuestionIntent (enums only — it cannot name tables, columns or SQL).
2. Python validates the intent and resolves the period against the data's own date range.
3. A predefined analytics function computes the evidence.
4. Gemini interprets the evidence (insights.generate_insight), with the usual number checks.
"""

from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.services.ai import insights
from app.services.ai.gemini import AiError, JsonModel, call_with_retry
from app.services.ai.grounding import fact
from app.services.analytics import metrics
from app.services.analytics.metrics import Filters

Intent = Literal["kpi_overview", "ranking", "change_drivers", "anomalies", "unsupported"]
PeriodChoice = Literal["selected_range", "last_30_days", "last_month", "last_quarter", "year_to_date", "all_time"]

AVAILABLE_DATA = ("orders and order lines with dates, stores, sales channels, product categories, quantities, "
                  "prices, discounts, unit costs and order status (completed, cancelled, returned)")


class QuestionIntent(BaseModel):
    intent: Intent
    dimension: Literal["category", "store", "channel", "product"] | None
    metric: Literal["net_revenue", "gross_profit", "gross_margin_pct", "units", "orders"] | None
    direction: Literal["top", "bottom"] | None
    period: PeriodChoice
    reason: str


INTENT_PROMPT = f"""Classify a retail analytics question into one approved analysis. Do not answer it.
Available data: {AVAILABLE_DATA}. Not available: marketing spend, traffic, inventory, staffing, weather,
customer demographics, competitor data.

intents:
- kpi_overview: overall performance or "what changed" for the whole selection.
- ranking: which items are best/worst by a metric (needs dimension, metric, direction).
- change_drivers: why something rose or fell, or which items are declining/growing (needs dimension;
  default category).
- anomalies: unusual changes or what management should investigate.
- unsupported: needs data that is not available, or is not about this sales data.
period: use selected_range unless the question names a period ("last month", "this year", ...).
dimension/metric/direction: null when not relevant."""


def resolve_period(choice: PeriodChoice, selected: Filters | None, data_min: date, data_max: date) -> tuple[date, date]:
    if choice == "selected_range" and selected is not None:
        return selected.start_date, selected.end_date
    if choice == "last_30_days":
        return max(data_min, data_max - timedelta(days=29)), data_max
    if choice in ("last_month", "last_quarter"):
        last_full = data_max if (data_max + timedelta(days=1)).day == 1 else data_max.replace(day=1) - timedelta(days=1)
        start = last_full.replace(day=1)
        for _ in range(2 if choice == "last_quarter" else 0):
            start = (start - timedelta(days=1)).replace(day=1)
        return max(data_min, start), last_full
    if choice == "year_to_date":
        return max(data_min, data_max.replace(month=1, day=1)), data_max
    return data_min, data_max  # all_time, or selected_range without a selection


def build_evidence(db: Session, org_id: int, intent: QuestionIntent, f: Filters) -> dict:
    facts = insights.period_facts(f) + insights.filter_facts(f)
    run_id = None
    if intent.intent == "kpi_overview":
        facts += insights.kpi_facts(db, org_id, f)
    elif intent.intent == "ranking":
        dimension, metric = intent.dimension or "category", intent.metric or "net_revenue"
        rows = metrics.sort_rows(metrics.breakdown(db, org_id, f, dimension), metric, intent.direction != "bottom")
        facts.append(fact("ranking", "Ranking", f"{dimension} by {metric}, "
                                                f"{'lowest' if intent.direction == 'bottom' else 'highest'} first"))
        unit = "percent" if metric == "gross_margin_pct" else "count" if metric in ("units", "orders") else "currency"
        for i, r in enumerate(rows[:5], start=1):
            facts += [fact(f"rank_{i}.name", f"Rank {i}", r["label"]),
                      fact(f"rank_{i}.{metric}", f"Rank {i} {metric}", r[metric], unit),
                      fact(f"rank_{i}.net_revenue", f"Rank {i} net revenue", r["net_revenue"], "currency"),
                      fact(f"rank_{i}.share_pct", f"Rank {i} share of net revenue", r["share_pct"], "percent")]
        facts.append(fact("ranking.count", f"Number of {dimension} groups with sales", len(rows), "count"))
    elif intent.intent == "change_drivers":
        facts += [x for x in insights.kpi_facts(db, org_id, f) if x["key"].startswith("kpi.net_revenue")]
        facts += insights.driver_facts(db, org_id, f, intent.dimension or "category", top=8)
    elif intent.intent == "anomalies":
        run_id, found = insights.latest_anomalies(db, org_id, f, limit=6, dimension=intent.dimension)
        for i, a in enumerate(found, start=1):
            facts += insights.anomaly_facts(a, f"anomaly_{i}")
        facts.append(fact("anomalies.count", "Anomalies in this period", len(found), "count") if run_id
                     else fact("anomalies", "Anomaly detection", "not run yet"))
    return {"facts": facts, "analysis_run_id": run_id}


def parse_intent(client: JsonModel, question: str) -> QuestionIntent:
    raw = call_with_retry(client, INTENT_PROMPT, f"Question: {question}", QuestionIntent)
    try:
        return QuestionIntent.model_validate_json(raw)
    except ValidationError:
        raise AiError("ai_invalid_response", "Gemini could not map the question to a supported analysis.", 502)


def unsupported_output(intent: QuestionIntent) -> dict:
    """Deterministic answer: no second model call and nothing invented."""
    return {"title": "This question can't be answered from the available data",
            "summary": intent.reason, "answerable": False, "observed_facts": [], "possible_explanations": [],
            "recommended_investigations": [],
            "information_needed": ["Data beyond the sales records (for example marketing spend, inventory or "
                                   "customer demographics), if the question depends on it."],
            "limitations": [f"Analyst IQ currently holds {AVAILABLE_DATA}."]}
