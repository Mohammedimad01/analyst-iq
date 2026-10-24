# API Contracts

Base path: `/api/v1`. Live, authoritative schema: `http://localhost:8000/docs` (OpenAPI generated from the
Pydantic models in `backend/app/schemas/`). This file explains intent; the TypeScript mirror lives in
`frontend/types/api.ts`.

Only implemented endpoints are listed. Planned endpoints are at the bottom and do not exist yet.

## Conventions

- JSON, `snake_case`. Dates are ISO `YYYY-MM-DD`. Money is a JSON number rounded to cents (computed as decimal).
- Ratios are percentages (`42.5` means 42.5 %). A ratio with a zero denominator is `null`, never `0`.
- **Errors** always use one envelope:
  ```json
  { "error": { "code": "validation_error", "message": "end_date must be on or after start_date", "details": [] } }
  ```
  Codes: `validation_error` (422), `not_found` (404), `payload_too_large` (413), `bad_request` (400),
  `database_unavailable` (503), `rate_limited` (429), `internal_error` (500), and the `ai_*` codes in
  [`INSIGHTS.md`](INSIGHTS.md#failure-handling). No stack traces are returned.

### Analytics filter parameters (shared)

| param | type | notes |
|---|---|---|
| `start_date`, `end_date` | date | required by analytics endpoints; inclusive; span ≤ 1096 days |
| `store` | string, repeatable | store codes |
| `category` | string, repeatable | |
| `channel` | `in_store` \| `online` \| `marketplace`, repeatable | |

## Endpoints

### `GET /health`
`{ "status": "ok" | "degraded", "database": "ok" | "unavailable", "database_backend": "postgresql" | "sqlite", "gemini_configured": bool, "version": "0.1.0" }`
Returns 200 even when degraded so monitors can read the body.

### `GET /dashboard/filters`
Options for the filter bar.
`{ "has_data": bool, "date_min": date|null, "date_max": date|null, "stores": [{"code","name"}], "categories": [str], "channels": [str] }`

### `GET /dashboard/overview?<filters>`
```jsonc
{
  "period": {"start_date": "2026-04-01", "end_date": "2026-06-30", "days": 91},
  "comparison_period": {"start_date": "2025-12-31", "end_date": "2026-03-31", "days": 91},
  "kpis": [
    {"key": "net_revenue", "label": "Net Revenue", "value": 123456.78, "previous": 120000.0,
     "abs_change": 3456.78, "pct_change": 2.88, "direction": "up", "sentiment": "positive",
     "unit": "currency", "definition": "Σ(quantity × unit price − discount) for completed orders"}
  ],
  "trend": {"grain": "week", "points": [{"period_start": "2026-03-30", "net_revenue": 0, "gross_profit": 0, "orders": 0, "units": 0, "partial": true}]},
  "by_category": [BreakdownRow], "by_store": [BreakdownRow], "by_channel": [BreakdownRow],
  "top_products": [BreakdownRow]   // top 10 by net revenue
}
```
KPI keys: `net_revenue, gross_profit, gross_margin_pct, orders, avg_order_value, units_sold, gross_sales,
discounts, discount_rate_pct, return_rate_pct, cancellation_rate_pct`.
`unit` is `currency | percent | count`. For `percent` KPIs `abs_change` is in percentage points and
`pct_change` is `null`.

`BreakdownRow`: `{ "key", "label", "net_revenue", "gross_profit", "gross_margin_pct", "units", "orders", "share_pct" }`.

### `GET /analytics/sales?<filters>&grain=day|week|month`
`{ "period", "trend": {...}, "by_category": [...], "by_channel": [...] }` — `grain` optional (auto otherwise).

### `GET /analytics/breakdown/{dimension}?<filters>&sort=&order=&limit=&offset=`
`dimension`: `product | category | store | channel`. `sort`: `net_revenue | gross_profit | gross_margin_pct |
units | orders` (default `net_revenue`), `order`: `asc | desc`, `limit` 1–500 (default 50).
`{ "dimension", "period", "total": int, "limit", "offset", "items": [BreakdownRow] }`

### `POST /data/imports` (multipart, field `file`)
Accepts `.csv` or `.xlsx` up to `MAX_UPLOAD_MB`. Returns **201** with an `ImportRead` whenever an import record
was created — inspect `status`:

- `completed` — accepted rows were committed (rejected rows, if any, are listed in `errors`).
- `rejected` — nothing was written (empty file, missing columns, duplicate file, no valid rows).
- `failed` — the database transaction failed; nothing was written.

Rejected before a record exists: 400 (bad extension / unreadable), 413 (too large).

`ImportRead`: `{ "id", "filename", "status", "rows_received", "rows_accepted", "rows_rejected",
"orders_accepted", "message", "errors": [{"row", "column", "message"}], "started_at", "finished_at", "duration_ms" }`

### `GET /data/imports?limit=&offset=`
`{ "total", "limit", "offset", "items": [ImportRead without errors] }`, newest first.

### `GET /data/imports/{import_id}`
`ImportRead` with errors; 404 if unknown.

### `POST /anomalies/detect`
Body (all optional): `{ "start_date", "end_date", "config": DetectionConfig }`. Runs every detector over complete
periods in the range (default: all data), stores the run in `analysis_runs`, returns **201** `AnomalyRun`:
`{ "id", "created_at", "duration_ms", "data_range", "evaluated_range", "counts": {"high","medium","low"}, "anomalies": [Anomaly] }`

`Anomaly`: `{ "key", "detector", "metric", "metric_label", "dimension", "segment_key", "segment_label", "grain",
"period_start", "period_end", "observed", "expected", "abs_diff", "pct_diff", "z_score", "direction", "severity",
"method", "evidence": {...}, "note" }`. Methods and thresholds: [`INSIGHTS.md`](INSIGHTS.md).

### `GET /anomalies/latest?min_severity=high|medium|low`
Latest stored run, optionally filtered by severity (for notifications). 404 if detection has never run.

### `GET /anomalies/runs?limit=`
Run history: `{ "total", "items": [{ "id", "created_at", "counts", "evaluated_range" }] }`.

### `POST /insights/generate`
`{ "type": "executive_summary", "start_date", "end_date", "store": [], "category": [], "channel": [], "refresh": false }`
or `{ "type": "anomaly_explanation", "anomaly": { "run_id", "key" }, "refresh": false }` → **201** `InsightRead`.

### `POST /insights/query`
`{ "question": "3–500 chars", "start_date"?, "end_date"?, "store", "category", "channel", "refresh": false }` → **201** `InsightRead`.

`InsightRead`: `{ "id", "insight_type", "status", "created_at", "model", "prompt_version", "question", "intent",
"params", "facts": [{ "key", "label", "value", "unit", "display" }], "output": InsightOutput | null,
"validation": { "dropped": [...] }, "error_code", "error_message", "analysis_run_id", "duration_ms", "cached" }`.
AI failures return the error envelope with an AI code (see [`INSIGHTS.md`](INSIGHTS.md#failure-handling)) and
`details: [{ "insight_id" }]` pointing at the stored failed attempt.

### `GET /insights?limit=&offset=` · `GET /insights/{id}`
History (newest first) and a single stored insight.

## Planned (not implemented — do not call)

`POST /reports/generate`, `GET /reports`, `GET /reports/{id}/download`, automation endpoints protected by an API key.
