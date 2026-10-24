from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select

from app.api.deps import MAX_RANGE_DAYS, DbSession, OrgId
from app.core.errors import AppError
from app.models import AiInsight, AnalysisRun
from app.schemas import InsightList, InsightRead
from app.services.ai import insights, questions
from app.services.ai.gemini import AiError, JsonModel, get_ai_client
from app.services.ai.grounding import numbers_in
from app.services.analytics import metrics
from app.services.analytics.metrics import Filters

router = APIRouter(prefix="/insights", tags=["insights"])

SUMMARY_TASK = ("Write an executive summary of business performance in the selected period versus the comparison "
                "period: the most important KPI changes, which categories, stores and channels drove them, and any "
                "detected anomalies. Recommend concrete investigations.")
ANOMALY_TASK = ("Explain this statistically detected anomaly to a retail manager: what changed, how large the change "
                "was, which period was affected, what evidence supports it, and what to investigate next. It is a "
                "statistical deviation, not a confirmed business problem.")
QUESTION_TASK = "Answer the user's question using only these facts. If they do not answer it, say so."


def ai_client() -> JsonModel:
    try:
        return get_ai_client()
    except AiError as exc:
        raise AppError(exc.http_status, exc.message, code=exc.code)


AiClient = Annotated[JsonModel, Depends(ai_client)]


class FilterBody(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    store: list[str] = Field(default_factory=list, max_length=50)
    category: list[str] = Field(default_factory=list, max_length=50)
    channel: list[Literal["in_store", "online", "marketplace"]] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_range(self):
        if (self.start_date is None) != (self.end_date is None):
            raise ValueError("start_date and end_date must be given together")
        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                raise ValueError("end_date must be on or after start_date")
            if (self.end_date - self.start_date).days + 1 > MAX_RANGE_DAYS:
                raise ValueError(f"Date range is limited to {MAX_RANGE_DAYS} days")
        return self

    def to_filters(self, start: date | None = None, end: date | None = None) -> Filters:
        return Filters(start or self.start_date, end or self.end_date, tuple(self.store), tuple(self.category),
                       tuple(self.channel))


class AnomalyRef(BaseModel):
    run_id: int
    key: str = Field(max_length=200)


class GenerateRequest(FilterBody):
    type: Literal["executive_summary", "anomaly_explanation"]
    anomaly: AnomalyRef | None = None
    refresh: bool = False


class QuestionRequest(FilterBody):
    question: str = Field(min_length=3, max_length=500)
    refresh: bool = False


def to_read(record: AiInsight, cached: bool = False) -> dict:
    return {"id": record.id, "insight_type": record.insight_type, "status": record.status,
            "created_at": record.created_at, "model": record.model, "prompt_version": record.prompt_version,
            "question": record.question, "intent": record.intent, "params": record.params,
            "facts": record.evidence.get("facts", []), "output": record.output, "validation": record.validation,
            "error_code": record.error_code, "error_message": record.error_message,
            "analysis_run_id": record.analysis_run_id, "duration_ms": record.duration_ms, "cached": cached}


def _anomaly_evidence(db, org_id: int, ref: AnomalyRef) -> dict:
    run = db.get(AnalysisRun, ref.run_id)
    if run is None or run.organization_id != org_id:
        raise AppError(404, "Anomaly run not found.")
    anomaly = next((a for a in run.result.get("anomalies", []) if a["key"] == ref.key), None)
    if anomaly is None:
        raise AppError(404, "Anomaly not found in that run.")
    facts = insights.anomaly_facts(anomaly, "anomaly")
    # Context: the same segment's KPIs in the affected period vs the period before it (where filterable).
    filter_arg = {"store": "stores", "channel": "channels", "category": "categories"}.get(anomaly["dimension"])
    if filter_arg:
        f = Filters(date.fromisoformat(anomaly["period_start"]), date.fromisoformat(anomaly["period_end"]),
                    **{filter_arg: (anomaly["segment_key"],)})
        facts += insights.period_facts(f, "context_period")
        facts += [x for x in insights.kpi_facts(db, org_id, f)
                  if x["key"].split(".")[1] in ("net_revenue", "orders", "discount_rate_pct", "return_rate_pct")]
    return {"facts": facts, "analysis_run_id": run.id}


@router.post("/generate", response_model=InsightRead, status_code=201)
def generate(body: GenerateRequest, db: DbSession, org_id: OrgId, client: AiClient):
    if body.type == "executive_summary":
        if body.start_date is None:
            raise AppError(422, "start_date and end_date are required for an executive summary")
        evidence = insights.executive_summary_evidence(db, org_id, body.to_filters())
        task = SUMMARY_TASK
    else:
        if body.anomaly is None:
            raise AppError(422, "anomaly (run_id and key) is required for an anomaly explanation")
        evidence = _anomaly_evidence(db, org_id, body.anomaly)
        task = ANOMALY_TASK
    record, cached = insights.generate_insight(db, org_id, client, body.type, task, evidence,
                                               params=body.model_dump(mode="json", exclude={"refresh"}),
                                               refresh=body.refresh)
    return to_read(record, cached)


@router.post("/query", response_model=InsightRead, status_code=201)
def ask(body: QuestionRequest, db: DbSession, org_id: OrgId, client: AiClient):
    options = metrics.filter_options(db, org_id)
    if not options["has_data"]:
        raise AppError(422, "There is no sales data to answer questions about yet.")
    params = body.model_dump(mode="json", exclude={"refresh", "question"})  # the question has its own column
    question = " ".join(body.question.split())

    # Reuse the intent of an identical earlier question so repeats cost no model call.
    # params are compared in Python: PostgreSQL's json type has no equality operator.
    candidates = [] if body.refresh else db.scalars(select(AiInsight).where(
        AiInsight.organization_id == org_id, AiInsight.insight_type == "question",
        AiInsight.status == "completed", func.lower(AiInsight.question) == question.lower())
        .order_by(AiInsight.id.desc()).limit(20))
    previous = next((c for c in candidates if c.params == params), None)
    if previous is not None and previous.intent:
        intent = questions.QuestionIntent.model_validate(previous.intent)
    else:
        insights.check_rate_limit(db, org_id)
        try:
            intent = questions.parse_intent(client, question)
        except AiError as exc:
            failed = AiInsight(organization_id=org_id, insight_type="question", status="failed", cache_key="-",
                               question=question, params=params, evidence={}, model=client.model,
                               prompt_version=insights.PROMPT_VERSION, error_code=exc.code, error_message=exc.message)
            db.add(failed)
            db.commit()
            raise AppError(exc.http_status, exc.message, code=exc.code, details=[{"insight_id": failed.id}])

    selected = body.to_filters() if body.start_date else None
    start, end = questions.resolve_period(intent.period, selected, options["date_min"], options["date_max"])
    f = body.to_filters(start, end)
    if intent.intent == "unsupported":
        record = AiInsight(organization_id=org_id, insight_type="question", status="completed", cache_key="-",
                           question=question, params=params, intent=intent.model_dump(), evidence={"facts": []},
                           output=questions.unsupported_output(intent), validation={"dropped": []},
                           model="rules", prompt_version=insights.PROMPT_VERSION)
        db.add(record)
        db.commit()
        return to_read(record)

    evidence = questions.build_evidence(db, org_id, intent, f)
    record, cached = insights.generate_insight(
        db, org_id, client, "question", QUESTION_TASK, evidence, params=params, question=question,
        intent=intent.model_dump(), refresh=body.refresh, extra_numbers=[v for v, _ in numbers_in(question)])
    return to_read(record, cached)


@router.get("", response_model=InsightList)
def list_insights(db: DbSession, org_id: OrgId, limit: Annotated[int, Query(ge=1, le=50)] = 20,
                  offset: Annotated[int, Query(ge=0)] = 0):
    scope = AiInsight.organization_id == org_id
    total = db.scalar(select(func.count()).select_from(AiInsight).where(scope))
    rows = db.scalars(select(AiInsight).where(scope).order_by(AiInsight.id.desc()).limit(limit).offset(offset))
    return {"total": total, "limit": limit, "offset": offset,
            "items": [{"id": r.id, "insight_type": r.insight_type, "status": r.status, "created_at": r.created_at,
                       "title": (r.output or {}).get("title"), "question": r.question, "model": r.model,
                       "error_code": r.error_code} for r in rows]}


@router.get("/{insight_id}", response_model=InsightRead)
def get_insight(insight_id: int, db: DbSession, org_id: OrgId):
    record = db.get(AiInsight, insight_id)
    if record is None or record.organization_id != org_id:
        raise AppError(404, "Insight not found.")
    return to_read(record)
