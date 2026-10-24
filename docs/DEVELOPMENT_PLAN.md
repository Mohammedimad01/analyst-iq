# Development Plan

Ordered by what the business user needs first. Each milestone ends with passing tests and an updated
`PROJECT_STATUS.md`.

## Milestone 1 — Analytics foundation (done — see PROJECT_STATUS.md)

- [x] Docs: architecture, data model, KPI definitions, API contracts
- [x] FastAPI app: config, DB session, error envelope, logging, health
- [x] Schema + Alembic migration
- [x] Synthetic dataset generator (fixed seed, injected anomalies) → `sample_data/`
- [x] Import pipeline (CSV/XLSX, validation, order-level atomicity, duplicate guards, one transaction)
- [x] KPI engine + period comparison + trends + breakdowns, tested with hand-calculated data
- [x] Frontend shell + Overview, Sales, Products, Stores & Channels, Data Sources pages on real API data
- [x] Type check, lint, build, backend test suite green

## Milestone 2 — Insights (done — see PROJECT_STATUS.md)

- [x] Anomaly detection (segment vs rest of business, same-weekday spikes, discount gap, product returns, YoY)
- [x] Verified against injected anomalies A1–A4 with a precision bound (automated test)
- [x] `analysis_runs`, `ai_insights` tables (migration 0002)
- [x] Gemini client (`google-genai`): timeouts, one controlled retry, structured JSON validated with Pydantic
- [x] Grounding check: every number in AI output must match a verified fact
- [x] Executive summary, anomaly explanation, NL questions via an allow-list of intents (no model SQL)
- [x] Caching, persisted history, per-minute/day limits, AI Insights page; dashboard unaffected when Gemini is down
- [ ] Live run against Gemini with a real key (needs `GEMINI_API_KEY` / `GEMINI_MODEL`)

## Milestone 3 — Reports and automation

- Report generation (executive, sales, product, store, profitability) from the same KPI engine
- CSV export, then PDF
- API-key protected automation endpoints
- n8n workflow JSON (scheduled summary, import notification, anomaly alert) without embedded secrets

## Milestone 4 — Hardening and deployment

- Authentication and enforced organisation scoping (only then claim multi-tenancy)
- Rate limiting on upload and AI endpoints
- Deploy: Vercel (frontend), Render (API), Neon (DB) — after verifying each provider's current free-tier terms

## Free-tier facts to verify before relying on them

| Service | What to check | Why it matters |
|---|---|---|
| Neon | storage cap, compute auto-suspend, connection limits | cold-start latency on first request after idle |
| Gemini API | which models the key can use, requests/minute and /day | AI features must degrade gracefully at quota |
| Render free web service | sleep after inactivity, monthly hours | first API call after sleep can take tens of seconds |
| Vercel hobby | non-commercial use terms | portfolio use is the intended case |

None of these are assumed to be permanent or identical across accounts.
