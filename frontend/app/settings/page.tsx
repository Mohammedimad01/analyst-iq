"use client";

import type { ReactNode } from "react";

import { useFilters } from "@/components/shell/FiltersProvider";
import { Card, PageHeader } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/States";
import { API_URL } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import type { DataKind } from "@/types/api";

const DATA_KIND: Record<DataKind, string> = {
  none: "No data loaded",
  synthetic: "Synthetic demo data only",
  imported: "Imported data only",
  mixed: "Imported data mixed with synthetic demo data",
};

function Row({ label, value, how }: { label: string; value: ReactNode; how: string }) {
  return (
    <tr className="border-b border-line/70 last:border-0 align-top">
      <th scope="row" className="py-2.5 pr-4 text-left font-medium text-ink">{label}</th>
      <td className="py-2.5 pr-4 text-ink-2">{value}</td>
      <td className="py-2.5 text-xs text-ink-3">{how}</td>
    </tr>
  );
}

export default function SettingsPage() {
  const { workspace: w } = useFilters();
  return (
    <>
      <PageHeader
        title="Settings"
        description="How this deployment is configured. Values come from server environment variables, so changes are made there, not in the browser."
      />
      <Card>
        {!w ? (
          <Skeleton className="h-48" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-3">
                  <th scope="col" className="py-2 pr-4 font-medium">Setting</th>
                  <th scope="col" className="py-2 pr-4 font-medium">Current value</th>
                  <th scope="col" className="py-2 font-medium">How to change</th>
                </tr>
              </thead>
              <tbody>
                <Row label="Organisation" value={w.organization_name} how="ORGANIZATION_NAME (used when the organisation is first created)" />
                <Row
                  label="Data source"
                  value={
                    <>
                      {DATA_KIND[w.data_kind]}
                      <span className="block text-xs text-ink-3">
                        {formatNumber(w.imported_orders)} imported orders · {formatNumber(w.synthetic_orders)} synthetic orders
                        {w.last_import && ` · last import #${w.last_import.id} (${w.last_import.filename}, ${w.last_import.status})`}
                      </span>
                    </>
                  }
                  how="Data Sources page, or python -m app.cli seed for the demo dataset"
                />
                <Row
                  label="Database"
                  value={w.database_backend === "postgresql" ? "PostgreSQL" : "SQLite (local fallback, development only)"}
                  how="DATABASE_URL (Neon pooled URL); DATABASE_URL_DIRECT for migrations"
                />
                <Row
                  label="AI insights"
                  value={w.ai_configured ? `On · ${w.ai_model}` : "Off"}
                  how="GEMINI_API_KEY and GEMINI_MODEL (list models: python -m app.cli gemini-models)"
                />
                <Row label="Automation API" value={w.automation_configured ? "On" : "Off"} how="AUTOMATION_API_KEY" />
                <Row label="Uploads" value={w.read_only ? "Disabled (read-only deployment)" : "Enabled"} how="READ_ONLY_MODE" />
                <Row label="API address" value={<code className="text-xs">{API_URL}</code>} how="NEXT_PUBLIC_API_URL (frontend build)" />
              </tbody>
            </table>
          </div>
        )}
      </Card>
      <Card className="mt-4" title="Access and tenancy">
        <p className="text-sm text-ink-2">
          This is a <strong>single-organisation deployment without user accounts</strong>. Every query is scoped to one
          organisation, but there is no login, so anyone who can reach the app can see its data. Use synthetic or
          non-sensitive data for public demos, and turn on <code>READ_ONLY_MODE</code> there.
        </p>
      </Card>
    </>
  );
}
