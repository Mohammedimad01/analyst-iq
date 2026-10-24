"use client";

import { CheckCircle2, FileSpreadsheet, Loader2, UploadCloud, XCircle, AlertTriangle } from "lucide-react";
import Link from "next/link";
import { useRef, useState, type DragEvent } from "react";

import { useFilters } from "@/components/shell/FiltersProvider";
import { Card, PageHeader } from "@/components/ui/Card";
import { ErrorState, Skeleton } from "@/components/ui/States";
import { useApi } from "@/hooks/useApi";
import { ApiError, apiFetch, buildUrl } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import type { ImportList, ImportRead, ImportStatus } from "@/types/api";

const ACCEPT = ".csv,.xlsx";
const REQUIRED = "order_id, order_date, store_id, channel, product_sku, product_name, category, quantity, unit_price, unit_cost, status";
const OPTIONAL = "line_number, discount_amount, customer_id, customer_segment, customer_region, store_name, store_region";

const STATUS_STYLE: Record<ImportStatus, { label: string; className: string; Icon: typeof CheckCircle2 }> = {
  completed: { label: "Completed", className: "bg-positive-soft text-positive", Icon: CheckCircle2 },
  rejected: { label: "Rejected", className: "bg-warning-soft text-warning", Icon: AlertTriangle },
  failed: { label: "Failed", className: "bg-negative-soft text-negative", Icon: XCircle },
  processing: { label: "Processing", className: "bg-subtle text-ink-2", Icon: Loader2 },
};

function StatusPill({ status }: { status: ImportStatus }) {
  const { label, className, Icon } = STATUS_STYLE[status];
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${className}`}>
      <Icon className="size-3" aria-hidden="true" /> {label}
    </span>
  );
}

const dateTime = new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short" });

function ImportResult({ result }: { result: ImportRead }) {
  return (
    <div className="mt-4 rounded-lg border border-line bg-subtle p-4" role="status">
      <div className="flex flex-wrap items-center gap-2">
        <StatusPill status={result.status} />
        <span className="text-sm font-medium text-ink">{result.filename}</span>
      </div>
      <p className="mt-2 text-sm text-ink-2">{result.message}</p>
      <dl className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        {[
          ["Rows received", result.rows_received],
          ["Rows accepted", result.rows_accepted],
          ["Rows rejected", result.rows_rejected],
          ["Orders imported", result.orders_accepted],
        ].map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs text-ink-3">{label}</dt>
            <dd className="tabular font-semibold text-ink">{formatNumber(value as number)}</dd>
          </div>
        ))}
      </dl>
      {result.status === "completed" && (
        <Link href="/" className="mt-3 inline-block text-sm font-medium text-primary hover:text-primary-hover">
          View updated dashboard →
        </Link>
      )}
      {result.errors.length > 0 && (
        <div className="mt-4">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-3">
            Row issues {result.rows_rejected > result.errors.length && `(first ${result.errors.length} shown)`}
          </h3>
          <div className="mt-2 max-h-72 overflow-auto rounded-md border border-line bg-surface">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-surface">
                <tr className="border-b border-line text-left text-xs text-ink-3">
                  <th scope="col" className="px-3 py-1.5 font-medium">Row</th>
                  <th scope="col" className="px-3 py-1.5 font-medium">Column</th>
                  <th scope="col" className="px-3 py-1.5 font-medium">Problem</th>
                </tr>
              </thead>
              <tbody>
                {result.errors.map((e, i) => (
                  <tr key={i} className="border-b border-line/60 last:border-0">
                    <td className="tabular px-3 py-1.5 text-ink-2">{e.row ?? "—"}</td>
                    <td className="px-3 py-1.5 font-mono text-xs text-ink-2">{e.column ?? "—"}</td>
                    <td className="px-3 py-1.5 text-ink">{e.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function Uploader({ onImported, readOnly }: { onImported: () => void; readOnly: boolean }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ImportRead | null>(null);
  const [error, setError] = useState<string | null>(null);

  const choose = (f: File | undefined) => {
    setResult(null);
    setError(null);
    if (!f) return;
    if (!/\.(csv|xlsx)$/i.test(f.name)) {
      setFile(null);
      setError("Only .csv and .xlsx files are supported.");
      return;
    }
    setFile(f);
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    choose(e.dataTransfer.files[0]);
  };

  const upload = async () => {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const body = new FormData();
      body.append("file", file);
      const res = await apiFetch<ImportRead>(buildUrl("/data/imports"), { method: "POST", body });
      setResult(res);
      onImported();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed.");
    } finally {
      setBusy(false);
    }
  };

  if (readOnly) {
    return (
      <Card title="Import sales data">
        <p className="text-sm text-ink-2">
          Uploads are disabled in this deployment (read-only demo). Data is loaded by the operator with{" "}
          <code>python -m app.cli seed</code> or in a local copy of the app.
        </p>
      </Card>
    );
  }

  return (
    <Card title="Import sales data" description="One row per order line. CSV (UTF-8) or Excel .xlsx; dates as YYYY-MM-DD.">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-8 text-center transition-colors ${
          dragging ? "border-primary bg-primary-soft" : "border-line-strong bg-subtle"
        }`}
      >
        {file ? <FileSpreadsheet className="size-7 text-primary" /> : <UploadCloud className="size-7 text-ink-3" />}
        <p className="text-sm text-ink">
          {file ? (
            <>
              <span className="font-medium">{file.name}</span> · {file.size < 1024 ? "<1" : (file.size / 1024).toFixed(0)} KB
            </>
          ) : (
            "Drag a file here, or"
          )}
        </p>
        <input ref={inputRef} type="file" accept={ACCEPT} className="sr-only" id="import-file" onChange={(e) => choose(e.target.files?.[0])} />
        <div className="flex gap-2">
          <label
            htmlFor="import-file"
            className="cursor-pointer rounded-md border border-line-strong bg-surface px-3 py-1.5 text-sm font-medium text-ink hover:bg-page"
          >
            {file ? "Choose another file" : "Browse files"}
          </label>
          {file && (
            <button
              onClick={upload}
              disabled={busy}
              className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-on-primary hover:bg-primary-hover disabled:opacity-60"
            >
              {busy && <Loader2 className="size-3.5 animate-spin" />}
              {busy ? "Validating and importing…" : "Import file"}
            </button>
          )}
        </div>
      </div>
      {error && (
        <p className="mt-3 rounded-md bg-negative-soft px-3 py-2 text-sm text-negative" role="alert">
          {error}
        </p>
      )}
      {result && <ImportResult result={result} />}

      <details className="mt-4 text-sm text-ink-2">
        <summary className="cursor-pointer font-medium text-ink">File format and validation rules</summary>
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li>
            <strong>Required columns:</strong> <code className="text-xs">{REQUIRED}</code>
          </li>
          <li>
            <strong>Optional:</strong> <code className="text-xs">{OPTIONAL}</code>
          </li>
          <li>channel: in_store, online, marketplace · status: completed, cancelled, returned.</li>
          <li>Money uses plain numbers with at most 2 decimals; discount_amount is an absolute amount per line.</li>
          <li>If any line of an order is invalid, the whole order is rejected — orders are never imported partially.</li>
          <li>Orders that already exist are never overwritten; uploading the same file twice is refused.</li>
          <li>Excel formulas and macros are never executed; .xlsm files are not accepted.</li>
        </ul>
      </details>
    </Card>
  );
}

function History() {
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<number | null>(null);
  const list = useApi<ImportList>(buildUrl("/data/imports", { limit: 10, offset }));
  const detail = useApi<ImportRead>(selected === null ? null : buildUrl(`/data/imports/${selected}`));

  return (
    <Card title="Import history" description="Every attempt is recorded, including rejected and failed imports.">
      {list.error ? (
        <ErrorState error={list.error} onRetry={list.reload} />
      ) : !list.data ? (
        <Skeleton className="h-40" />
      ) : list.data.total === 0 ? (
        <p className="py-6 text-center text-sm text-ink-3">No imports yet.</p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-3">
                  <th scope="col" className="py-2 pr-3 font-medium">File</th>
                  <th scope="col" className="py-2 pr-3 font-medium">Status</th>
                  <th scope="col" className="py-2 pr-3 text-right font-medium">Accepted</th>
                  <th scope="col" className="py-2 pr-3 text-right font-medium">Rejected</th>
                  <th scope="col" className="py-2 font-medium">Started</th>
                </tr>
              </thead>
              <tbody>
                {list.data.items.map((item) => (
                  <tr key={item.id} className={`border-b border-line/70 last:border-0 ${selected === item.id ? "bg-primary-soft" : "hover:bg-subtle"}`}>
                    <td className="py-2 pr-3">
                      <button onClick={() => setSelected(item.id === selected ? null : item.id)} className="text-left font-medium text-ink hover:text-primary">
                        #{item.id} {item.filename}
                      </button>
                    </td>
                    <td className="py-2 pr-3">
                      <StatusPill status={item.status} />
                    </td>
                    <td className="tabular py-2 pr-3 text-right text-ink-2">{formatNumber(item.rows_accepted)}</td>
                    <td className="tabular py-2 pr-3 text-right text-ink-2">{formatNumber(item.rows_rejected)}</td>
                    <td className="py-2 text-ink-2">{dateTime.format(new Date(item.started_at))}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {list.data.total > 10 && (
            <div className="mt-3 flex justify-end gap-2 text-sm">
              <button className="rounded-md border border-line-strong px-3 py-1 disabled:opacity-40" disabled={offset === 0} onClick={() => setOffset(offset - 10)}>
                Previous
              </button>
              <button className="rounded-md border border-line-strong px-3 py-1 disabled:opacity-40" disabled={offset + 10 >= list.data.total} onClick={() => setOffset(offset + 10)}>
                Next
              </button>
            </div>
          )}
          {selected !== null && (detail.data ? <ImportResult result={detail.data} /> : detail.error ? <ErrorState error={detail.error} /> : <Skeleton className="mt-4 h-24" />)}
        </>
      )}
    </Card>
  );
}

export default function DataSourcesPage() {
  const { reloadOptions, workspace } = useFilters();
  const [reloadToken, setReloadToken] = useState(0);
  return (
    <>
      <PageHeader title="Data Sources" description="Upload sales files. Every row is validated before anything is written." />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Uploader
          readOnly={workspace?.read_only ?? false}
          onImported={() => {
            reloadOptions();
            setReloadToken((n) => n + 1);
          }}
        />
        <History key={reloadToken} />
      </div>
      <p className="mt-4 text-xs text-ink-3">
        Demo dataset: run <code>python -m app.cli seed</code> in <code>backend/</code> to load the synthetic sample (Jan 2025 – Jun 2026).
      </p>
    </>
  );
}
