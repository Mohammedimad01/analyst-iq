"""Response contracts. Mirrored in frontend/types/api.ts; prose in docs/API_CONTRACTS.md."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, PlainSerializer

# Computed as Decimal, sent as a JSON number (already rounded to cents by the analytics engine).
Num = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "unavailable"]
    database_backend: Literal["postgresql", "sqlite"]
    gemini_configured: bool
    version: str


class Period(BaseModel):
    start_date: date
    end_date: date
    days: int


class Kpi(BaseModel):
    key: str
    label: str
    unit: Literal["currency", "percent", "count"]
    definition: str
    value: Num | None
    previous: Num | None
    abs_change: Num | None
    pct_change: Num | None
    direction: Literal["up", "down", "flat"]
    sentiment: Literal["positive", "negative", "neutral"]


class TrendPoint(BaseModel):
    period_start: date
    net_revenue: Num
    gross_profit: Num
    orders: int
    units: int
    partial: bool


class Trend(BaseModel):
    grain: Literal["day", "week", "month"]
    points: list[TrendPoint]


class BreakdownRow(BaseModel):
    key: str
    label: str
    net_revenue: Num
    gross_profit: Num
    gross_margin_pct: Num | None
    units: int
    orders: int
    share_pct: Num | None


class Overview(BaseModel):
    period: Period
    comparison_period: Period
    kpis: list[Kpi]
    trend: Trend
    by_category: list[BreakdownRow]
    by_store: list[BreakdownRow]
    by_channel: list[BreakdownRow]
    top_products: list[BreakdownRow]


class SalesAnalytics(BaseModel):
    period: Period
    trend: Trend
    by_category: list[BreakdownRow]
    by_channel: list[BreakdownRow]


class BreakdownPage(BaseModel):
    dimension: Literal["product", "category", "store", "channel"]
    period: Period
    total: int
    limit: int
    offset: int
    items: list[BreakdownRow]


class StoreOption(BaseModel):
    code: str
    name: str


class FilterOptions(BaseModel):
    has_data: bool
    date_min: date | None
    date_max: date | None
    stores: list[StoreOption]
    categories: list[str]
    channels: list[str]


class ImportRowError(BaseModel):
    row: int | None
    column: str | None
    message: str


class ImportSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    status: Literal["processing", "completed", "failed", "rejected"]
    rows_received: int
    rows_accepted: int
    rows_rejected: int
    orders_accepted: int
    message: str | None
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None


class ImportRead(ImportSummary):
    errors: list[ImportRowError]


class ImportList(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[ImportSummary]


# ---------------------------------------------------------------- anomalies

Severity = Literal["high", "medium", "low"]


class Anomaly(BaseModel):
    key: str
    detector: str
    metric: str
    metric_label: str
    dimension: Literal["store", "channel", "category", "product", "total"]
    segment_key: str
    segment_label: str
    grain: Literal["day", "week", "month"]
    period_start: date
    period_end: date
    observed: float
    expected: float
    abs_diff: float
    pct_diff: float | None
    z_score: float | None
    direction: Literal["up", "down"]
    severity: Severity
    method: str
    evidence: dict
    note: str


class AnomalyRun(BaseModel):
    id: int
    created_at: datetime
    duration_ms: int | None
    data_range: Period | None
    evaluated_range: Period | None
    counts: dict[str, int]
    anomalies: list[Anomaly]


class AnomalyRunSummary(BaseModel):
    id: int
    created_at: datetime
    counts: dict[str, int]
    evaluated_range: Period | None


class AnomalyRunList(BaseModel):
    total: int
    items: list[AnomalyRunSummary]


# ---------------------------------------------------------------- AI insights

class EvidenceFact(BaseModel):
    key: str
    label: str
    value: float | str | None
    unit: str
    display: str


class InsightRead(BaseModel):
    id: int
    insight_type: Literal["executive_summary", "anomaly_explanation", "question"]
    status: Literal["completed", "failed"]
    created_at: datetime
    model: str
    prompt_version: str
    question: str | None
    intent: dict | None
    params: dict
    facts: list[EvidenceFact]
    output: dict | None
    validation: dict | None
    error_code: str | None
    error_message: str | None
    analysis_run_id: int | None
    duration_ms: int | None
    cached: bool


class InsightSummary(BaseModel):
    id: int
    insight_type: str
    status: str
    created_at: datetime
    title: str | None
    question: str | None
    model: str
    error_code: str | None


class InsightList(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[InsightSummary]
