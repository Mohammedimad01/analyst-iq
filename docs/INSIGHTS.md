# Anomaly Detection and AI Insights

> Detect with statistics. Explain with AI. Never let the model produce a number the engine did not compute.

Code: `backend/app/services/anomaly_detection/detector.py`, `backend/app/services/ai/`.
Tests: `backend/tests/test_anomalies.py`, `backend/tests/test_ai.py`.

## 1. Anomaly detection

All detectors are interpretable and run in about a second on 18 months of data. They only judge **complete
periods** (a partial first/last week or month is never compared), and baselines use **earlier periods only**.

| Detector | Grain | Segments | Compares | Flags when (defaults) |
|---|---|---|---|---|
| `segment_volume_week` | week | stores, channels | completed orders vs **rest of business**: expected = median(segment ÷ rest, previous 8 weeks) × rest this week | ≥ 35 % off, \|z\| ≥ 4, expected ≥ 15 orders, **and** ≥ 17.5 % off its own 8-week median in the same direction |
| `segment_spike_daily` | day | channels | orders vs median of the **same weekday** over the previous 8 weeks | ≥ 75 % off, Poisson \|z\| ≥ 4, expected ≥ 5, **and** confirmed vs rest of business (\|z\| ≥ 3, same sign) |
| `category_discount_weekly` | week | categories | category discount rate − rest-of-business rate, vs its median gap (8 weeks) | gap widens by ≥ 8 pp and weekly gross ≥ $1,000 |
| `product_returns_monthly` | month | products | share of orders containing the product that were returned, vs pooled previous 6 months | ≥ +10 pp, binomial z ≥ 3, ≥ 20 orders that month |
| `total_revenue_yoy` | week | whole business | net revenue vs the same week 52 weeks earlier (complete weeks only) | ≥ 40 % off |

### Why "rest of business"

Seasonality (December, Black Friday, weekends) lifts every segment together. Comparing a segment with everyone
else cancels that out without a seasonal model. Two corrections make it statistically honest:

- The z-score includes the noise of the rest-of-business count — `z = (o − e) / √(e·(1 + r))` — otherwise a
  dominant segment (in-store ≈ 65 % of orders) looks anomalous whenever the small remainder dips.
- The segment must also move against **its own** history in the same direction, otherwise one store's drop makes
  the other stores look like spikes (the "mirror" effect).

### Severity

`high` needs size **and** significance: |z| ≥ 6, or ≥ 60 % off with |z| ≥ 4.5. `medium`: ≥ 45 % off or |z| ≥ 4.5.
Percentage-point detectors: high ≥ 15 pp, medium ≥ 10 pp. Severity ranks statistical strength; it is not a
business-impact score.

### Validation on the synthetic dataset (automated test)

| Injected anomaly | Detected as |
|---|---|
| A1 Riverside Mall orders ×0.3, 9–22 Mar 2026 | both weeks, **high** (−80 %, −83 %) |
| A2 Beauty discounts May 2026 | 5 weeks overlapping May; 3 **high**, 2 medium (24 % vs ~3 % expected) |
| A3 Wireless Earbuds Pro returns Apr 2026 | **medium** (17.5 % vs 4.2 %, z = 5.2) |
| A4 Online orders ×3 on 14 Feb 2026 | **high** (+153 %) |

Everything else flagged: 3 medium items, 0 high (two single-day Online swings, one product-returns month). Black
Friday week and December produce no alerts. The test fails if any non-injected item becomes `high` or more
than 3 appear.

### Not detected (yet)

Category volume (orders span several categories, so "rest of business" is not a clean split), margin erosion
(Electronics cost rise on 1 Jan 2026 is gradual, not a break), store-level daily spikes (counts too small).

## 2. AI insights (Gemini)

```
KPI engine / detector ──► evidence pack (named facts) ──► Gemini (structured JSON) ──► validation ──► stored ──► UI
                                     ▲                                                    │
                                     └──────────── every number must match a fact ◄───────┘
```

### Evidence pack

A flat list of `{key, label, value, unit, display}` facts, e.g.
`kpi.net_revenue.current = 324648.99 ("$324,648.99")`, `category.Beauty.change_pct`, `anomaly.observed`.
Only aggregates: no order numbers, no customer identifiers. The full pack is stored with the insight and shown in the UI
("Evidence sent to the AI").

### Output contract (`InsightOutput`, validated with Pydantic)

`title`, `summary`, `answerable`, `observed_facts[{statement, evidence_key}]`, `possible_explanations[]`
(hypotheses), `recommended_investigations[{action, reason}]`, `information_needed[]`, `limitations[]`.

### Grounding check (`services/ai/grounding.py`)

1. Every number in the text is parsed (`$324,649`, `12.3%`, `$325K`, `-80 pp`; dates, years, IDs like `ELE-002`
   and bare counts ≤ 10 are ignored).
2. It must match a fact value within the rounding the writer used: `$325K` may stand for 324,648.99,
   `12.9%` may **not** stand for 12.33.
3. A fact citing an unknown `evidence_key`, or any list item with an unmatched number, is **dropped** and listed
   in `validation.dropped`; the UI says how many were removed.
4. If the **title or summary** fails, the whole insight is rejected (`ai_ungrounded`) and nothing is shown.

### Questions in plain English

1. Gemini maps the question onto `QuestionIntent` — enums only: `kpi_overview | ranking | change_drivers |
   anomalies | unsupported`, dimension, metric, direction, period.
2. Pydantic rejects anything outside the enums (an attempted `run_sql` intent fails validation).
3. Periods such as "last month" resolve against the **data's** latest date, not today.
4. The matching analytics function runs (breakdown, change drivers, KPI comparison, latest anomalies).
5. Gemini interprets that evidence under the same grounding check.
6. `unsupported` (marketing spend, inventory, demographics…) returns a rule-based answer with no second call.

The model never writes SQL, never sees credentials, and cannot widen the filters the user selected.

### Failure handling

| Situation | Code | HTTP | Retried |
|---|---|---|---|
| Key/model not set | `ai_not_configured` | 503 | — |
| Invalid key / no permission | `ai_auth_failed` | 503 | no |
| Model not available to the key | `ai_model_not_found` | 503 | no |
| Provider rate limit / quota (429) | `ai_rate_limited` | 429 | no |
| Provider 5xx | `ai_provider_error` | 502 | once |
| Timeout (`GEMINI_TIMEOUT_SECONDS`) | `ai_timeout` | 504 | once |
| Network error | `ai_network_error` | 502 | once |
| Not valid JSON / wrong shape | `ai_invalid_response` | 502 | no |
| Empty / blocked response | `ai_empty_response` | 502 | no |
| Numbers not in evidence (title/summary) | `ai_ungrounded` | 502 | no |
| App limit reached | `rate_limited` | 429 | — |

SDK retries are switched off (`HttpRetryOptions(attempts=1)`), so the one retry above is the only one.
Failed attempts are stored (with the code) for audit and count toward the limits. Dashboards and anomaly
detection never depend on Gemini.

### Cost controls

- **Caching**: the key is a hash of type + prompt version + model + evidence + question. The same evidence returns the
  stored insight with `cached: true` and makes no API call. New data changes the evidence, which regenerates the insight.
- Repeated questions reuse the stored intent, which saves the classification call.
- Limits from stored attempts (survive restarts): `AI_MAX_REQUESTS_PER_MINUTE` (5), `AI_MAX_REQUESTS_PER_DAY` (100).
- Nothing is generated on page load; every AI call is an explicit button press.

### Choosing a model

`GEMINI_MODEL` is never hardcoded. Run `python -m app.cli gemini-models` (backend/) to list models that support
`generateContent` for your key, and check current free-tier limits in Google AI Studio.
