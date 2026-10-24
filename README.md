# Analyst IQ

Retail analytics micro-SaaS: import sales data, validate it row by row, and get verified KPIs and dashboards.

> **Calculate with deterministic analytics. Interpret with AI. Communicate through dashboards.**
> Every number on screen comes from one documented KPI engine and can be traced to source rows.
> Gemini only interprets numbers the engine has already verified, and every number it writes is checked.

**Status:** Milestones 1 (analytics) and 2 (anomalies + AI insights) complete. See [`PROJECT_STATUS.md`](PROJECT_STATUS.md).
The bundled dataset is **synthetic** and labelled as such everywhere.

## What works today

- **Data import** (CSV / Excel): column and type validation, row-level error messages, whole-order acceptance,
  duplicate-file and duplicate-order protection, single-transaction writes, full import history.
- **KPI engine**: net revenue, gross profit, margin, orders, AOV, units, discount / return / cancellation rates,
  with period-over-period comparison — definitions in [`docs/KPI_DEFINITIONS.md`](docs/KPI_DEFINITIONS.md).
- **Dashboards**: Overview, Sales Analytics, Products, Stores & Channels, Data Sources — all driven by the API,
  with shared date / store / category / channel filters, loading, empty, no-match and failure states.
- **Anomaly detection**: interpretable statistical detectors (segment vs rest of business, same-weekday spikes,
  discount gaps, product return spikes, year-over-year). They find all four injected anomalies; methods are in
  [`docs/INSIGHTS.md`](docs/INSIGHTS.md).
- **AI insights (Gemini)**: executive summaries, anomaly explanations and plain-English questions. Questions are
  routed through an allow-list of analyses, and every number is verified against the evidence before it is shown.
  The app works fully without a Gemini key.
- **Synthetic dataset**: 18k orders over 18 months with seasonality and four deliberately injected anomalies.

## Stack

Next.js 16 (App Router) · React 19 · TypeScript (strict) · Tailwind CSS 4 · Recharts · Lucide —
FastAPI · Pydantic 2 · SQLAlchemy 2 · Alembic · pandas — PostgreSQL (Neon) — Google Gemini (`google-genai`) —
n8n in Milestone 3.

## Local setup (Windows, PowerShell)

Requirements: Python 3.11+ (tested on 3.14), Node.js 20+ (tested on 24), npm.

### 1. Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m app.cli seed
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

`seed` applies migrations, generates `sample_data/retail_sample.csv` (fixed seed) and imports it through the
normal import pipeline. Re-running it is safe: the identical file is rejected as a duplicate.

API docs: <http://localhost:8000/docs> · health: <http://localhost:8000/api/v1/health>

### 2. Frontend (second terminal)

```powershell
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>. The frontend calls `http://localhost:8000` unless `NEXT_PUBLIC_API_URL` is set
(see `frontend/.env.example`).

### Database: SQLite fallback vs Neon PostgreSQL

With no configuration the backend uses a local SQLite file (`backend/analyst_iq.db`) — fine for a demo on one
machine. **PostgreSQL is the supported database.** To use Neon:

1. Create a free project at <https://neon.tech> and copy its connection string.
2. Copy `.env.example` to `.env` in the repository root and set `DATABASE_URL=` to that string
   (`postgresql://…?sslmode=require` is accepted as-is). `.env` is git-ignored.
3. From `backend/`: `.venv\Scripts\python -m app.cli seed`, then restart the API.
   The header shows **Connected · PostgreSQL** when it is in use.

### Gemini (optional)

1. Put `GEMINI_API_KEY=...` in the root `.env`.
2. From `backend/`: `.venv\Scripts\python -m app.cli gemini-models` lists models your key can use.
3. Set `GEMINI_MODEL=` to one of them and restart the API. The AI Insights page then enables its buttons.

Free-tier models and limits vary by account and change over time; check Google AI Studio. Limits inside the
app: `AI_MAX_REQUESTS_PER_MINUTE` and `AI_MAX_REQUESTS_PER_DAY`.

### Tests and checks

```powershell
cd backend; .venv\Scripts\python -m pytest -q
cd frontend; npm run typecheck; npm run lint; npm test; npm run build
```

Backend tests use in-memory SQLite. To run the same suite on PostgreSQL, set `TEST_DATABASE_URL` to a
**throwaway** database (tests drop and recreate all tables).

## Project layout

```
backend/   FastAPI app (app/), Alembic migrations, pytest suite
frontend/  Next.js app (app/ pages, components/, lib/ API client + formatting, types/ API contracts)
docs/      architecture, data model, KPI definitions, API contracts, development plan
sample_data/  synthetic dataset docs + a validation demo file
```

## Importing your own file

One row per order line. Required columns: `order_id, order_date, store_id, channel, product_sku, product_name,
category, quantity, unit_price, unit_cost, status`. Dates `YYYY-MM-DD`; channel `in_store|online|marketplace`;
status `completed|cancelled|returned`. Full rules: [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md#import-rules).
Try `sample_data/import_with_errors.csv` to see the validation report.

## Limitations (honest list)

- **No authentication.** Single demo organisation; tenant isolation is designed into the schema but not enforced.
  Do not deploy this build with real customer data.
- Returns are whole-order only; taxes and shipping are not modelled.
- Currency display is fixed to USD.
- Light theme only.
- AI insights are tested against a fake client; a live Gemini run needs your key.
- Reports and n8n automation are not built yet (Milestone 3).
