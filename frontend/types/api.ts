// Mirror of backend/app/schemas/__init__.py. Keep in sync with the API (docs/API_CONTRACTS.md).

export type Channel = "in_store" | "online" | "marketplace";
export type Grain = "day" | "week" | "month";
export type Dimension = "product" | "category" | "store" | "channel";
export type SortKey = "net_revenue" | "gross_profit" | "gross_margin_pct" | "units" | "orders";

export interface Health {
  status: "ok" | "degraded";
  database: "ok" | "unavailable";
  database_backend: "postgresql" | "sqlite";
  gemini_configured: boolean;
  version: string;
}

export interface Period {
  start_date: string;
  end_date: string;
  days: number;
}

export interface Kpi {
  key: string;
  label: string;
  unit: "currency" | "percent" | "count";
  definition: string;
  value: number | null;
  previous: number | null;
  abs_change: number | null;
  pct_change: number | null;
  direction: "up" | "down" | "flat";
  sentiment: "positive" | "negative" | "neutral";
}

export interface TrendPoint {
  period_start: string;
  net_revenue: number;
  gross_profit: number;
  orders: number;
  units: number;
  partial: boolean;
}

export interface Trend {
  grain: Grain;
  points: TrendPoint[];
}

export interface BreakdownRow {
  key: string;
  label: string;
  net_revenue: number;
  gross_profit: number;
  gross_margin_pct: number | null;
  units: number;
  orders: number;
  share_pct: number | null;
}

export interface Overview {
  period: Period;
  comparison_period: Period;
  kpis: Kpi[];
  trend: Trend;
  by_category: BreakdownRow[];
  by_store: BreakdownRow[];
  by_channel: BreakdownRow[];
  top_products: BreakdownRow[];
}

export interface SalesAnalytics {
  period: Period;
  trend: Trend;
  by_category: BreakdownRow[];
  by_channel: BreakdownRow[];
}

export interface Concentration {
  top_fraction_pct: number;
  top_count: number;
  item_count: number;
  share_pct: number | null;
}

export interface BreakdownPage {
  dimension: Dimension;
  period: Period;
  concentration: Concentration;
  total: number;
  limit: number;
  offset: number;
  items: BreakdownRow[];
}

export interface FilterOptions {
  has_data: boolean;
  date_min: string | null;
  date_max: string | null;
  stores: { code: string; name: string }[];
  categories: string[];
  channels: Channel[];
}

export type ImportStatus = "processing" | "completed" | "failed" | "rejected";

export interface ImportSummary {
  id: number;
  filename: string;
  status: ImportStatus;
  rows_received: number;
  rows_accepted: number;
  rows_rejected: number;
  orders_accepted: number;
  message: string | null;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
}

export interface ImportRead extends ImportSummary {
  errors: { row: number | null; column: string | null; message: string }[];
}

export interface ImportList {
  total: number;
  limit: number;
  offset: number;
  items: ImportSummary[];
}

export interface ApiErrorBody {
  error: { code: string; message: string; details: unknown[] };
}

// ---------------------------------------------------------------- anomalies

export type Severity = "high" | "medium" | "low";

export interface Anomaly {
  key: string;
  detector: string;
  metric: string;
  metric_label: string;
  dimension: "store" | "channel" | "category" | "product" | "total";
  segment_key: string;
  segment_label: string;
  grain: Grain;
  period_start: string;
  period_end: string;
  observed: number;
  expected: number;
  abs_diff: number;
  pct_diff: number | null;
  z_score: number | null;
  direction: "up" | "down";
  severity: Severity;
  method: string;
  evidence: Record<string, unknown>;
  note: string;
}

export interface AnomalyRun {
  id: number;
  created_at: string;
  duration_ms: number | null;
  data_range: Period | null;
  evaluated_range: Period | null;
  counts: Partial<Record<Severity, number>>;
  anomalies: Anomaly[];
}

// ---------------------------------------------------------------- AI insights

export type InsightType = "executive_summary" | "anomaly_explanation" | "question";

export interface EvidenceFact {
  key: string;
  label: string;
  value: number | string | null;
  unit: string;
  display: string;
}

export interface InsightOutput {
  title: string;
  summary: string;
  answerable: boolean;
  observed_facts: { statement: string; evidence_key: string }[];
  possible_explanations: string[];
  recommended_investigations: { action: string; reason: string }[];
  information_needed: string[];
  limitations: string[];
}

export interface InsightRead {
  id: number;
  insight_type: InsightType;
  status: "completed" | "failed";
  created_at: string;
  model: string;
  prompt_version: string;
  question: string | null;
  intent: Record<string, unknown> | null;
  params: Record<string, unknown>;
  facts: EvidenceFact[];
  output: InsightOutput | null;
  validation: { dropped: { field: string; text: string; reason: string }[] } | null;
  error_code: string | null;
  error_message: string | null;
  analysis_run_id: number | null;
  duration_ms: number | null;
  cached: boolean;
}

export interface InsightList {
  total: number;
  limit: number;
  offset: number;
  items: {
    id: number;
    insight_type: InsightType;
    status: "completed" | "failed";
    created_at: string;
    title: string | null;
    question: string | null;
    model: string;
    error_code: string | null;
  }[];
}

// ---------------------------------------------------------------- workspace, customers, reports

export type DataKind = "none" | "synthetic" | "imported" | "mixed";

export interface Workspace {
  organization_name: string;
  data_kind: DataKind;
  synthetic_orders: number;
  imported_orders: number;
  last_import: {
    id: number;
    filename: string;
    status: string;
    source: "upload" | "synthetic_demo";
    finished_at: string | null;
  } | null;
  database_backend: "postgresql" | "sqlite";
  read_only: boolean;
  ai_configured: boolean;
  ai_model: string | null;
  automation_configured: boolean;
  single_organization: boolean;
}

export interface CustomerAnalytics {
  period: Period;
  kpis: Kpi[];
  trend: {
    grain: Grain;
    points: { period_start: string; active_customers: number; new_customers: number; partial: boolean }[];
  };
  segments: { segment: string; customers: number; orders: number; net_revenue: number; share_pct: number | null }[];
  top_customers: { customer_code: string; net_revenue: number; orders: number; share_pct: number | null }[];
  concentration: Concentration;
  history_days_before_period: number;
  warnings: string[];
}

export type ReportType = "executive" | "sales" | "product" | "store" | "customer" | "profitability";

export interface ReportSummary {
  id: number;
  report_type: ReportType;
  title: string;
  file_format: "pdf" | "csv";
  filename: string;
  size_bytes: number;
  contains_synthetic: boolean;
  requested_by: string;
  params: Record<string, unknown>;
  created_at: string;
  duration_ms: number | null;
}

export interface ReportList {
  total: number;
  limit: number;
  offset: number;
  items: ReportSummary[];
}
