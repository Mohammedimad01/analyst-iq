# n8n automation

Four importable workflows for **n8n Community Edition** (self-hosted, free). The app works without them.

| File | Schedule | Calls |
|---|---|---|
| `workflows/01-weekly-kpi-summary.json` | Mondays 08:00 | `POST /api/v1/automation/kpi-summary` |
| `workflows/02-anomaly-alerts.json` | Daily 07:30 | `POST /api/v1/automation/anomaly-alerts` |
| `workflows/03-scheduled-report.json` | 1st of month 07:00 | `POST /api/v1/automation/reports` then download |
| `workflows/04-import-notification.json` | Every 30 min | `GET /api/v1/automation/imports/latest` |

Each workflow: **Config** node (API URL, recipients) → HTTP request (60 s timeout, 3 tries 10 s apart) →
**Should notify?** → **Send notification** (email) → **Record delivery** (`POST /api/v1/automation/deliveries`).
HTTP failures go to a *Stop and Error* node, so the execution is marked failed in n8n's history.

**No duplicates:** the API returns `delivery_keys`; the workflow records them only after sending. Recorded items are
not returned (anomalies) or come back with `should_notify: false`. Reports for the same type/format/period are reused.

## Setup

1. API: set `AUTOMATION_API_KEY` (long random string) in `.env` / the host's env vars and restart it.
   Without it every `/automation/*` route returns 503; a wrong or missing key returns 401.
2. Run n8n locally: `npx n8n` (needs Node 20+; uses ~300–500 MB RAM) and open http://localhost:5678.
3. Credentials (n8n → Credentials):
   - **Header Auth** named `Analyst IQ API`: name `X-API-Key`, value = your key.
   - **SMTP** named `SMTP account` (e.g. a Gmail app password) — or replace the email node with Slack/Telegram.
4. Import each JSON (Workflows → Import from file), edit the **Config** node (`notifyTo`, `notifyFrom`; `apiUrl`
   defaults to the deployed API `https://analyst-iq-api.onrender.com` — use `http://localhost:8000` for a local
   API, never with a trailing slash), select the credentials on the HTTP/email nodes, and activate.
5. The KPI summary and report use `"anchor": "latest_data"`: periods are measured back from the newest order in the
   data, which suits historical or uploaded datasets. For live sales data change it to `"today"`.

No keys or passwords are stored in these JSON files; credentials stay in n8n's encrypted store.

## Manual test

```bash
curl -s -X POST https://analyst-iq-api.onrender.com/api/v1/automation/kpi-summary -H "X-API-Key: $AUTOMATION_API_KEY" -H "Content-Type: application/json" -d '{"period":"previous_week","anchor":"latest_data"}'
```

`samples/` holds real responses captured from the API on the synthetic dataset.

## Verification status

The endpoints are covered by automated tests and were called live against Neon. The workflow JSON was validated
structurally (all connections resolve, no secrets) but **has not been executed inside n8n** on this machine.
A local n8n only runs while the computer is on.
