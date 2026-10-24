# Project Status

_Last updated: 2026-10-24 — completion session (uncommitted, awaiting review)._

| Area | Status |
|---|---|
| Analytics foundation (M1) | ✅ verified on **Neon PostgreSQL** |
| Anomalies + grounded AI (M2) | ✅ verified with **live Gemini** (`gemini-3.5-flash-lite`) |
| Customers, reports/exports, automation API, n8n, security, deployment config (M3/M4) | ✅ implemented and tested; n8n not executed; nothing deployed |

## Verified this session (evidence)

- **Neon**: free project `analyst-iq` (us-east-1, PG 17) + separate `analyst_iq_test` database created via MCP.
  Migrations 0001–0004 applied; seed imported 18,076 orders / 35,205 lines in 70 s.
- **KPIs on PostgreSQL** equal the independent pandas figures: net revenue $324,648.99, profit $117,031.47,
  2,710 orders, AOV $119.80, Riverside Mall $60,486.01. Weekly buckets Monday-aligned. Detection on PG: same 6 high flags.
- **Gemini live**: executive summary, anomaly explanation (A1) and a question all completed, 0 statements dropped by the
  number check; repeat request served from cache. `gemini-2.5-flash` is closed to new users (404); `gemini-3.8-flash`
  returned 503 "high demand" at test time.
- **Reports**: executive/customer PDFs and profitability CSV generated from Neon; PDF checked visually.
- **Automation**: all endpoints called live with the key; no key → 401.

## Tests (actual results)

| Check | Result |
|---|---|
| Backend `pytest -q` (SQLite) | **119 passed, 2 skipped** (`--postgres` migration test, `--live-gemini` test) |
| Backend `pytest -q --postgres` (Neon test DB) | **not completed**: started, then stopped to save time (each test pays ~230 ms round trips; ~20+ min). CI runs it against a Postgres service container. |
| `pytest --live-gemini` | not run as a test; same flows verified manually above |
| Frontend `npm test` | **15 passed** (6 unit + 9 component) |
| `npm run typecheck`, `npm run lint` | clean |
| `npm run build` | success, 11 routes |
| n8n workflows | structurally validated only, not run in n8n |

## Fixed this session

- Gemini key was in tracked `.env.example` → moved to git-ignored `.env`, placeholder restored (never committed).
- Import over a remote DB took >10 min (ORM bulk insert split batches on NULLs) → Core batch inserts, 70 s.
- Imports killed mid-run stayed "processing" forever → auto-marked failed after 1 h.
- PostgreSQL GROUP BY with bound parameters (workspace) → grouped on raw column.
- `gemini-models` CLI closed its HTTP client early; 404 errors now include Google's replacement hint.
- Hardcoded "Demo Retail Co" / "Synthetic demo data" header → real org name and data mix from `/workspace`.

## Added

Customer analytics + page; concentration (products, customers); Reports page, 6 report types (PDF via fpdf2, CSV),
9 CSV exports with formula-injection protection; Automation, Settings pages; `/automation/*` (X-API-Key,
constant-time compare, two-step delivery de-duplication, idempotent reports); 4 n8n workflows + samples;
rate limits on upload/detect/report/export/automation; security headers; `/docs` off in production;
`READ_ONLY_MODE`; migrations 0003 (import source) and 0004 (reports, automation_events);
`render.yaml`; `.github/workflows/ci.yml`; `pytest --postgres` / `--live-gemini`.

## Known limitations

- **No authentication; single organisation.** Queries are org-scoped (tested) but anyone reaching the app sees its data.
  Use `READ_ONLY_MODE=true` and synthetic data for public demos.
- Synthetic generator gives customer C00001 ~20% of identified revenue (Pareto bug). Fixing needs a re-seed of Neon
  (delete + reload) — awaiting your OK.
- In-memory rate limits are per process. Free Render sleeps after 15 min (≈1 min cold start); Neon suspends after 5 min idle.
- Vercel Hobby is for personal, non-commercial use.

## Your next steps

1. Review the diff, then commit and push (not done).
2. Run `cd backend; .venv\Scripts\python -m pytest -q --postgres` once (≈20–30 min) or let CI do it.
3. Deploy (not done): Render → New → Blueprint (this repo), fill the `sync: false` env vars; Vercel → import repo,
   root `frontend`, set `NEXT_PUBLIC_API_URL` to the Render URL; then set `CORS_ORIGINS` on Render to the Vercel URL.
4. Optionally run n8n (`npx n8n`) and import `automation/workflows/*.json` (see `automation/README.md`).
