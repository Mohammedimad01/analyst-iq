# Architecture

Analyst IQ is a **modular monolith**: one Next.js frontend, one FastAPI backend, one PostgreSQL database.
Optional add-ons (Gemini, n8n) sit at the edges and the core keeps working when they are absent.

```
Browser ──HTTP/JSON──▶ Next.js (frontend/)  ──fetch──▶ FastAPI (backend/)  ──SQLAlchemy──▶ PostgreSQL (Neon)
                        UI only, no secrets              validation, KPIs,                  source of truth
                                                         ingestion, AI calls
                                                              │
                                                              ├──▶ Gemini API      (optional; app works without it)
n8n (local, optional) ──authenticated HTTP──────────────────▶┘                     (Milestone 3, optional)
```

## Principle

> Calculate with deterministic analytics. Interpret with AI. Communicate through dashboards and reports.

- Every number shown in the UI comes from `backend/app/services/analytics/metrics.py`. There is exactly one
  implementation of each KPI; endpoints call it, they never re-implement it.
- Gemini receives compact, already-verified aggregates and only writes prose around them. Every number it
  writes is checked against those facts before it is stored or shown. It never generates SQL and never sees
  credentials.

## Backend layout (`backend/app`)

| Module | Responsibility |
|---|---|
| `main.py` | App factory: CORS, request logging, error handlers, router registration. |
| `core/config.py` | Environment-based settings (`.env` in repo root). Normalises Neon URLs for psycopg. |
| `core/errors.py` | One JSON error envelope for every failure; no stack traces leak to clients. |
| `db/` | Engine/session factory and the declarative `Base`. |
| `models/` | SQLAlchemy ORM tables (see `DATA_MODEL.md`). |
| `schemas/` | Pydantic request/response contracts (see `API_CONTRACTS.md`). |
| `services/ingestion/` | CSV/XLSX parsing, row validation, order-level atomic acceptance, transactional writes. |
| `services/analytics/` | Filters, KPI definitions, trends and breakdowns (see `KPI_DEFINITIONS.md`). |
| `services/anomaly_detection/` | Statistical detectors: pure functions over pandas frames plus one data loader. |
| `services/ai/gemini.py` | The only module that calls Gemini: timeouts, error mapping, one controlled retry. |
| `services/ai/grounding.py` | Evidence facts and the number check applied to every model output. |
| `services/ai/insights.py` | Evidence builders, prompt, validation, caching, rate limits, persistence. |
| `services/ai/questions.py` | Natural-language questions → allow-listed intents → existing analytics functions. |
| `api/routes/` | Thin HTTP layer: parse params → call service → return schema. |

`services/reports/` arrives with Milestone 3. Detection and AI details: [`INSIGHTS.md`](INSIGHTS.md).

## Database portability

Queries are written with SQLAlchemy Core expressions (parameterised, no string-built SQL). The one
dialect-specific piece — truncating a date to week/month — lives in a single helper. This lets the same code run on:

- **PostgreSQL / Neon** — the supported database for any shared or deployed use.
- **SQLite** — automatic fallback when `DATABASE_URL` is empty, and the default for the automated test suite
  (fast, isolated, zero infrastructure). Set `TEST_DATABASE_URL` to run the identical tests on PostgreSQL.

## Frontend layout (`frontend/`)

| Path | Responsibility |
|---|---|
| `app/` | App Router pages: Overview, Sales, Products, Stores & Channels, AI Insights, Data Sources. |
| `components/` | Shell (sidebar, header), UI primitives, chart wrappers. |
| `lib/api.ts` | Typed API client — the only place that knows the backend URL. |
| `lib/format.ts` | Currency/percent/number formatting. |
| `types/api.ts` | TypeScript mirror of the backend response schemas. |
| `hooks/` | Data fetching with loading / error / empty states. |

The browser only talks to FastAPI. Database credentials and the Gemini key exist only on the server.

## Security posture (Milestone 1)

- **No authentication yet.** The app runs as a single synthetic demo organisation. Every row carries
  `organization_id` so tenant isolation can be enforced later, but it is **not** enforced today. Do not expose
  this build to the internet with real customer data.
- Uploads: extension allow-list (`.csv`, `.xlsx`), size cap, row cap, no macro formats, formulas are never
  evaluated (openpyxl reads cached cell values only).
- All filters are validated by Pydantic and bound as SQL parameters.
- CORS restricted to `CORS_ORIGINS`.
- Errors return a generic message plus an error code; details go to server logs without secrets.

## Hardware / cost

Designed for an 8 GB Windows laptop: two processes (uvicorn + Next dev server), no Docker, no local LLM.
All services used have free tiers; their limits change, see `DEVELOPMENT_PLAN.md`.
