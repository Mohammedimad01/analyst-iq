# Analyst IQ: portfolio and résumé kit

Everything here is verified against the code and the live deployment (October 2026). Replace the
`[brackets]` before publishing. Keep the "Honest scope" section in mind: interviewers often probe exactly there.

- **Live demo:** https://analyst-iq-frontend.vercel.app
- **Code:** [GitHub link; the repository is private, so make it public or say "code available on request"]
- **Your role:** Sole developer: product design, data modelling, backend, frontend, AI integration, DevOps

---

## 1. Prompt for updating your portfolio website

Paste this into Claude (or any AI assistant) together with your portfolio's project component or page file:

```text
You are updating my developer/analyst portfolio website. Add a new project as the FIRST (latest) entry,
matching the existing design, components, tone and data structure exactly. Do not restyle anything else.

Use only the facts below. Do not invent metrics, users, clients or business impact.

PROJECT
Name: Analyst IQ
Tagline: AI-assisted retail analytics platform: verified KPIs first, AI interpretation second.
Date: October 2026
Role: Sole developer (product, data model, backend, frontend, AI, DevOps)
Live demo: https://analyst-iq-frontend.vercel.app
Code: [GitHub URL or "available on request"]

SUMMARY
A full-stack retail analytics web app. Businesses upload sales data (CSV or Excel); the platform validates every
row, computes 11 deterministic KPIs, detects statistical anomalies, and uses Google Gemini only to explain
numbers it has already verified. Every AI statement is checked against the computed metrics before display.

KEY FEATURES
- Data import: CSV/XLSX upload with row-level validation, all-or-nothing orders, "replace" or "add" modes,
  duplicate-file protection, full import history
- Dashboards: Overview, Sales, Products, Stores & Channels, Customers; date/store/category/channel filters;
  period-over-period comparison
- Anomaly detection: 5 statistical detectors (segment volume, daily spikes, category discount gaps, product
  return rates, year-over-year revenue) with severity requiring both effect size and significance
- AI insights: executive summaries, anomaly explanations and natural-language questions; numbers verified
  against source metrics, unverifiable statements removed, results cached
- Reports: PDF and CSV exports (executive, sales, product, store, customer, profitability)
- Automation: 4 n8n workflows (weekly KPI email, daily anomaly alerts, monthly PDF report, import notices)
  with API-key auth and duplicate-delivery protection

TECH STACK
Frontend: Next.js (App Router), React, TypeScript (strict), Tailwind CSS, Recharts
Backend: Python, FastAPI, Pydantic, SQLAlchemy 2, Alembic, pandas
Data/AI: PostgreSQL (Neon), Google Gemini
Automation/DevOps: n8n, GitHub Actions CI (PostgreSQL service), Render, Vercel

NUMBERS (all verified)
- 27 REST API endpoints, 10 application pages
- 136 automated tests (121 backend incl. a PostgreSQL suite, 15 frontend); CI runs on every push
- Import of a 35,000-line file cut from over 10 minutes to about 70 seconds on a remote database
- Anomaly tuning cut false positives from 44 flags to 12, with every high-severity flag matching a planted anomaly
- Runs entirely on free tiers (Vercel, Render, Neon, Gemini free tier, self-hosted n8n)

DESIGN NOTES
"Editorial analytics" UI: serif headings, ruled KPI strip, light and dark themes, accessible charts.

Write: a project card (title, tagline, 3 tech tags, demo link) and a project detail section with
Problem, Solution, Architecture (one short paragraph), Key challenges (3 bullets) and Results (3 bullets).
Keep it scannable and recruiter-friendly. Output only the code changes.
```

---

## 2. Ready-to-use portfolio entry

### Analyst IQ: AI-assisted retail analytics

**Verified KPIs first, AI interpretation second.**

**Problem.** Small retailers sit on sales exports but lack the time to analyse them, and generic AI tools
happily invent numbers. They need answers they can trust.

**Solution.** Analyst IQ turns a CSV or Excel export into a live analytics workspace. A deterministic metrics
engine computes the KPIs. Statistical detectors flag what changed. Google Gemini then explains the verified
results in plain English, and every number it writes is checked against the source metrics before anyone sees it.

**Architecture.** Next.js/TypeScript frontend on Vercel; FastAPI/Python API on Render; PostgreSQL on Neon. One
metrics module is the single source of truth for every KPI, used by dashboards, reports, AI prompts and
automation alike. n8n workflows call a key-protected automation API for scheduled emails and reports.

**Key challenges**
- **AI hallucination:** built a grounding layer that extracts every number from the AI output and verifies it
  against the evidence (with rounding tolerance); unverifiable statements are dropped and a failed headline
  rejects the whole insight.
- **False alarms:** the first anomaly detector raised 44 flags on test data. Variance-corrected z-scores,
  two-test agreement for daily spikes and an own-history check (to stop one segment's drop "mirroring" as
  another's rise) brought it to 12, with every high-severity flag a real planted event.
- **Import speed:** ORM bulk inserts split into tiny batches whenever nullable columns changed, taking over 10
  minutes for 35,000 lines on a remote database. Switching to Core bulk inserts brought it to about 70 seconds.

**Results**
- Live, working product: 10 pages, 27 API endpoints, CSV/PDF reports and 4 automation workflows
- 136 automated tests with CI against a real PostgreSQL database on every push
- Zero hosting cost: built and deployed entirely on free tiers

**Stack:** Next.js · React · TypeScript · Tailwind · Recharts · FastAPI · Python · pandas · SQLAlchemy ·
PostgreSQL · Google Gemini · n8n · GitHub Actions

---

## 3. Résumé / CV bullets

Pick the version that matches the role. Use 3–4 bullets; the first line is the project heading.

**Analyst IQ: AI-Assisted Retail Analytics Platform** | Next.js, FastAPI, PostgreSQL, Gemini, n8n | Oct 2026 |
[Live demo link]

**For Data Analyst / BI roles**
- Built a retail analytics platform that turns CSV/Excel sales exports into 11 validated KPIs, 5 interactive
  dashboards and PDF/CSV reports, with period-over-period comparison and store, category and channel filters.
- Designed 5 statistical anomaly detectors (variance-corrected z-scores, binomial tests, YoY on complete weeks),
  cutting false positives from 44 to 12 flags while catching every planted anomaly.
- Automated weekly KPI emails, daily anomaly alerts and monthly PDF reports with n8n, using idempotent delivery
  so retries never send duplicates.

**For Analytics Engineer / Data Engineer roles**
- Engineered a validated ingestion pipeline (pandas, SQLAlchemy 2, PostgreSQL) with row-level error reporting,
  all-or-nothing orders and atomic "replace dataset" imports; cut a 35k-line import from 10+ min to ~70 s.
- Centralised all KPI logic in one deterministic metrics module (Decimal money, explicit null handling) reused
  by dashboards, reports, AI prompts and the automation API.
- Shipped CI on GitHub Actions running 136 tests, including a PostgreSQL integration suite and Alembic migration
  checks, deployed on Render, Vercel and Neon at zero cost.

**For Full-Stack / AI Engineer roles**
- Built a full-stack analytics SaaS prototype (Next.js, TypeScript, FastAPI, PostgreSQL) with 27 REST
  endpoints, 10 pages, light/dark themes and 136 automated tests in CI.
- Integrated Google Gemini behind a grounding layer that verifies every AI-generated number against computed
  metrics, drops unverifiable claims, caches by evidence hash and enforces database-backed rate limits.
- Hardened the API with key-based automation auth (constant-time comparison), CSV formula-injection protection,
  security headers, upload limits and a read-only deployment mode.

---

## 4. Short versions

**One line (portfolio card / LinkedIn headline project):**
Analyst IQ: retail analytics platform where AI explains only numbers it can verify. Next.js, FastAPI,
PostgreSQL, Gemini, n8n.

**LinkedIn post / "Featured" description (~70 words):**
I built Analyst IQ, an AI-assisted retail analytics platform. Upload a sales file and it validates every row,
computes KPIs, flags statistical anomalies and asks Google Gemini to explain them. Each AI-written number is
checked against the real metrics before it is shown. It includes PDF/CSV reports, n8n automations and 136
automated tests, and runs entirely on free tiers. Live demo: https://analyst-iq-frontend.vercel.app

---

## 5. Interview talking points

1. **Why "verified KPIs first"?** LLMs are good at explaining but unreliable at arithmetic, so the system
   computes, verifies and only then asks the model to interpret, with no numbers trusted from the model.
2. **Hardest bug:** the PostgreSQL test suite hung in CI because a test fixture held a session open, blocking
   `TRUNCATE`. Fixed the fixture lifecycle and added a lock timeout so it fails fast instead of hanging.
3. **A statistics decision:** comparing a segment with "the rest of the business" creates a mirror effect: when
   one channel drops, the others look like they spiked. An own-history agreement check removed those false alarms.
4. **A trade-off:** it is a single-organisation deployment without login. Multi-tenant auth was deliberately left
   out of scope, and queries are already organisation-scoped to make adding it straightforward.

## Honest scope (do not overclaim)

- Single organisation, **no user login**: not a multi-tenant SaaS. Say "SaaS prototype" or "analytics platform".
- Demo data is **synthetic** (generated with planted events), not a real company's data.
- No real users or business results yet: present outcomes as engineering results, not revenue impact.
- The live API is on a free tier and sleeps when idle, so the first load can take about a minute.
