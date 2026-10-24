# Project Status

_Last updated: 2026-10-24, end of the Milestone 2 session._

| Milestone | Status |
|---|---|
| 1 — Analytics foundation | ✅ complete on SQLite; PostgreSQL run pending a `DATABASE_URL` |
| 2 — Anomalies + AI insights | ✅ built and tested with a fake Gemini client; **live Gemini call pending a key** |
| 3 — Reports + n8n automation | not started |
| 4 — Auth, hardening, deployment | not started |

## Milestone 2: what was built

- **Anomaly detection** (`services/anomaly_detection/detector.py`) has five interpretable detectors. Each run is stored in `analysis_runs`.
  - API: `POST /anomalies/detect`, `GET /anomalies/latest?min_severity=`, `GET /anomalies/runs`.
- **Gemini integration** (`services/ai/`) uses the `google-genai` SDK. Timeouts are configurable, there is exactly one retry for transient errors only, and every provider failure maps to a stable error code.
- **Grounding check**: every number in the AI output must match a verified fact.
  - An unmatched fact or list item is dropped, and the drop is recorded.
  - An unmatched number in the title or summary rejects the whole insight.
- **Insight types**:
  - Executive summary.
  - Anomaly explanation.
  - Plain-English questions, routed through an allow-list of 5 intents. The model never writes SQL; a question that needs data we don't have gets a rule-based "can't answer" reply.
- **Cost controls**: results are cached by evidence hash (a repeat request makes 0 API calls), the intent of a repeated question is reused, and there are per-minute and per-day limits. Nothing is generated on page load.
- **AI Insights page**:
  - The anomaly list has severity shown as icon + label, the method, and an "Explain with AI" button.
  - There is a question box with examples and an executive summary button.
  - The insight view separates facts, hypotheses, investigations and gaps, and shows the evidence sent to the AI.
  - Recent history is listed, and a clear notice appears when Gemini isn't configured.
- `python -m app.cli gemini-models` lists the models your key can use.

## Tests executed (actual results)

| Check | Result |
|---|---|
| Backend `pytest -q` | **93 passed**, 0 warnings (was 47) |
| Frontend `npm test` | 6 passed |
| `npm run typecheck`, `npm run lint` | clean |
| `npm run build` | success, 7 static routes incl. `/insights` |

New backend tests:
- **Anomaly detection (15).** Recall on A1–A4. A precision bound: no high-severity flag outside the injected anomalies, and at most 3 others. No alert on Black Friday. Plus unit tests for seasonality cancelling, the mirror effect, partial periods, YoY with a partial comparison week, the two-test daily spike, and minimum return volume. Plus API persistence and validation.
- **AI (31).** Grounding: kept facts, dropped facts and a rejected summary. Every provider failure code. Retry happens exactly once and never on 429. The app rate limit, while cached results stay available. Caching with no second call. Anomaly explanation evidence. The question intent flow and intent reuse. Unsupported questions make no second call. A `run_sql` intent is rejected. Period resolution, the number verifier, and real SDK exceptions mapped to codes.
- **Change drivers (1)**, hand-calculated.

## Verified in the browser (local SQLite, no Gemini key)

| Check | Result |
|---|---|
| Run detection from the UI | ✅ run stored. For the last 90 days it shows A2 (Beauty discounts, 3 high + 2 medium weeks), A3 (Earbuds returns), and 1 medium Online day |
| `GET /anomalies/latest?min_severity=high` | ✅ exactly the 6 injected high items: A1 ×2, A2 ×3, A4 |
| AI without a key | ✅ notice shown, AI buttons disabled, API returns 503 `ai_not_configured`, dashboards unaffected |
| Mobile, 375 px | ✅ no horizontal scroll |
| An insight from a real Gemini response, as shown in the UI | ⏳ **not verified**: needs a key. The rendering component is type-checked only |

## Acceptance test progress (brief §16)

| Step | Status |
|---|---|
| 1–9, 15: run, import, persist, verify KPIs, filter, restart | ✅ (Milestone 1) |
| 3: PostgreSQL connectivity | ⏳ no `DATABASE_URL` yet |
| 10–11: generate an AI insight that cites real metrics | ⏳ built and tested with a fake client; live call needs a key |
| 12: AI failure path without breaking the dashboard | ✅ |
| 13: detect an injected anomaly | ✅ all four |
| 14: generate and download a report | ⏳ Milestone 3 |

## Configuration still needed (yours)

1. **Gemini**: set `GEMINI_API_KEY` in `.env`, run `python -m app.cli gemini-models` from `backend/`, and set
   `GEMINI_MODEL` to one listed. Then restart the API. Check your account's free-tier limits in Google AI Studio.
2. **Neon**: set `DATABASE_URL`, then run `python -m app.cli seed`. Migration 0002 is applied automatically.
3. **Git**: nothing is committed yet.

## Decisions made this milestone

- Compare each segment with the **rest of the business** to cancel seasonality, rather than fit a seasonal model.
  The z-score includes the variance of the rest. An own-history check is also required, so one segment's drop
  doesn't make the others look like spikes (the "mirror" effect).
- Severity needs **size and significance**, so small-count swings stay at medium.
- **Number-level grounding**, not just prompt instructions. Prompts can be ignored; the check can't.
- **Two Gemini calls per new question** (classify, then interpret). Repeats reuse the stored intent.
- Failed AI attempts are stored, so audits and rate limits see them.
- Category volume, margin-erosion and store-level daily detectors are deliberately left out (see `docs/INSIGHTS.md`).

## Known issues / limitations

- 3 medium-severity statistical flags on the synthetic data are not injected anomalies. This is expected from
  Poisson tails, and the UI labels them as unconfirmed.
- The AI output has not been exercised against the real Gemini API yet.
- Rate limits count stored attempts per organisation. No per-user limits exist, because there is no authentication.
- Milestone 1 limitations still apply: no auth, single demo org, SQLite run only.

## Next concrete task

1. Add a Gemini key and run one executive summary, one anomaly explanation and one question end to end.
   Record the result here.
2. Milestone 3: report generation (executive, sales, product, store, profitability) from the same KPI engine,
   with CSV export first, then API-key-protected endpoints and the n8n workflows that call
   `/anomalies/detect` and `/anomalies/latest?min_severity=high`.
