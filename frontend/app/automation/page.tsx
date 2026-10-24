"use client";

import { CheckCircle2, CircleSlash } from "lucide-react";

import { useFilters } from "@/components/shell/FiltersProvider";
import { Card, PageHeader } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/States";

const WORKFLOWS = [
  {
    file: "01-weekly-kpi-summary.json",
    name: "Weekly KPI summary",
    schedule: "Mondays 08:00",
    steps: "POST /automation/kpi-summary → send message if should_notify → POST /automation/deliveries",
  },
  {
    file: "02-anomaly-alerts.json",
    name: "Anomaly alerts",
    schedule: "Daily 07:30",
    steps: "POST /automation/anomaly-alerts (high severity) → send only new anomalies → record deliveries",
  },
  {
    file: "03-scheduled-report.json",
    name: "Scheduled PDF report",
    schedule: "1st of the month 07:00",
    steps: "POST /automation/reports (reuses an existing file for the same period) → download → email attachment",
  },
  {
    file: "04-import-notification.json",
    name: "Import notification",
    schedule: "Every 30 minutes",
    steps: "GET /automation/imports/latest → notify once per import → record delivery",
  },
];

export default function AutomationPage() {
  const { workspace } = useFilters();
  return (
    <>
      <PageHeader
        title="Automation"
        description="Scheduled summaries, anomaly alerts and reports run in n8n (self-hosted Community Edition) and call this API."
      />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card title="API status" className="xl:col-span-1">
          {!workspace ? (
            <Skeleton className="h-16" />
          ) : workspace.automation_configured ? (
            <p className="flex items-start gap-2 text-sm text-positive">
              <CheckCircle2 className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              Automation endpoints are enabled. Requests must send the server&apos;s key in the X-API-Key header.
            </p>
          ) : (
            <p className="flex items-start gap-2 text-sm text-ink-2">
              <CircleSlash className="mt-0.5 size-4 shrink-0 text-ink-3" aria-hidden="true" />
              Automation endpoints are disabled. Set <code>AUTOMATION_API_KEY</code> in the API&apos;s environment to enable them.
            </p>
          )}
          <p className="mt-3 text-xs text-ink-3">
            The key never reaches the browser. n8n stores it as a Header Auth credential, not inside workflow files.
          </p>
        </Card>

        <Card title="Workflow templates" description="Importable JSON in automation/workflows" className="xl:col-span-2">
          <ul className="divide-y divide-line">
            {WORKFLOWS.map((w) => (
              <li key={w.file} className="py-3 text-sm">
                <p className="font-medium text-ink">
                  {w.name} <span className="ml-2 text-xs font-normal text-ink-3">{w.schedule}</span>
                </p>
                <p className="mt-0.5 font-mono text-xs text-ink-3">{w.file}</p>
                <p className="mt-1 text-ink-2">{w.steps}</p>
              </li>
            ))}
          </ul>
        </Card>

        <Card title="Set up" className="xl:col-span-3">
          <ol className="list-decimal space-y-1.5 pl-5 text-sm text-ink-2">
            <li>
              Generate a long random key and set <code>AUTOMATION_API_KEY</code> for the API, then restart it.
            </li>
            <li>
              Run n8n locally: <code>npx n8n</code> (or Docker), open <code>http://localhost:5678</code>.
            </li>
            <li>
              Create a <strong>Header Auth</strong> credential named <code>Analyst IQ API</code>: header <code>X-API-Key</code>, value = your key.
            </li>
            <li>
              Set the n8n variable <code>ANALYST_IQ_API_URL</code> (e.g. <code>http://localhost:8000</code>), then import the four JSON files.
            </li>
            <li>Replace each workflow&apos;s &quot;Send notification&quot; node with your channel (email, Slack, Telegram) and activate it.</li>
          </ol>
          <p className="mt-3 text-xs text-ink-3">
            Full instructions, sample payloads and failure handling: <code>automation/README.md</code>. A locally hosted n8n
            only runs while this computer is on.
          </p>
        </Card>
      </div>
    </>
  );
}
