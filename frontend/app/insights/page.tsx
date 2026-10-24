"use client";

import { AlertTriangle, FileText, Loader2, MessageSquareText, Play, Settings2 } from "lucide-react";
import { useState } from "react";

import { AnomalyItem, SEVERITY } from "@/components/insights/AnomalyList";
import { InsightView } from "@/components/insights/InsightView";
import { AnalyticsGate } from "@/components/shell/AnalyticsGate";
import { Card, PageHeader } from "@/components/ui/Card";
import { ErrorState, Skeleton } from "@/components/ui/States";
import { useApi } from "@/hooks/useApi";
import { ApiError, apiFetch, buildUrl, postJson } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { AnomalyRun, Health, InsightList, InsightRead, Severity } from "@/types/api";

const EXAMPLES = [
  "What changed compared with the previous period?",
  "Which category contributed most to profit?",
  "Which products have declining sales?",
  "Which stores should management investigate?",
  "Why did revenue decline last month?",
];

const dateTime = new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short" });

/** UI filter params (single values) -> request body (lists), as the API expects. */
function filterBody(params: Record<string, string>) {
  const list = (v: string) => (v ? [v] : []);
  return {
    start_date: params.start_date,
    end_date: params.end_date,
    store: list(params.store),
    category: list(params.category),
    channel: list(params.channel),
  };
}

function AiNotConfigured() {
  return (
    <div className="mb-4 flex gap-3 rounded-lg border border-warning/30 bg-warning-soft px-4 py-3 text-sm text-warning" role="status">
      <Settings2 className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <div>
        <p className="font-medium">Gemini is not configured, so AI explanations are switched off.</p>
        <p className="mt-0.5 text-ink-2">
          Add <code>GEMINI_API_KEY</code> and <code>GEMINI_MODEL</code> to <code>.env</code> and restart the API
          (list usable models with <code>python -m app.cli gemini-models</code>). Anomaly detection below works without it.
        </p>
      </div>
    </div>
  );
}

function RecentInsights({ onOpen }: { onOpen: (id: number) => void }) {
  const history = useApi<InsightList>(buildUrl("/insights", { limit: 8 }));
  return (
    <Card title="Recent insights">
      {history.error ? (
        <ErrorState error={history.error} onRetry={history.reload} />
      ) : !history.data ? (
        <Skeleton className="h-20" />
      ) : history.data.items.length === 0 ? (
        <p className="text-sm text-ink-3">No insights generated yet.</p>
      ) : (
        <ul className="divide-y divide-line">
          {history.data.items.map((h) => (
            <li key={h.id} className="flex items-center justify-between gap-3 py-2 text-sm">
              <button
                onClick={() => onOpen(h.id)}
                disabled={h.status === "failed"}
                className="min-w-0 truncate text-left font-medium text-ink hover:text-primary disabled:text-ink-3"
              >
                {h.title ?? h.question ?? "Untitled"}
                {h.status === "failed" && <span className="ml-2 text-xs font-normal">failed · {h.error_code}</span>}
              </button>
              <span className="shrink-0 text-xs text-ink-3">{dateTime.format(new Date(h.created_at))}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function InsightsContent({ params }: { params: Record<string, string> }) {
  const health = useApi<Health>(buildUrl("/health"));
  const latest = useApi<AnomalyRun>(buildUrl("/anomalies/latest"));
  const [historyKey, setHistoryKey] = useState(0);

  const [run, setRun] = useState<AnomalyRun | null>(null);
  const [detecting, setDetecting] = useState(false);
  const [detectError, setDetectError] = useState<ApiError | null>(null);
  const [scope, setScope] = useState<"period" | "all">("period");
  const [showLow, setShowLow] = useState(false);

  const [busy, setBusy] = useState<string | null>(null);
  const [insight, setInsight] = useState<InsightRead | null>(null);
  const [aiError, setAiError] = useState<ApiError | null>(null);
  const [question, setQuestion] = useState("");

  const aiOff = health.data && !health.data.gemini_configured ? "Gemini is not configured" : null;
  const currentRun = run ?? latest.data;

  const runDetection = async () => {
    setDetecting(true);
    setDetectError(null);
    try {
      setRun(await postJson<AnomalyRun>("/anomalies/detect", {}));
    } catch (err) {
      setDetectError(err instanceof ApiError ? err : new ApiError("Detection failed.", 0, "unknown"));
    } finally {
      setDetecting(false);
    }
  };

  const callAi = async (label: string, path: string, body: unknown) => {
    setBusy(label);
    setAiError(null);
    try {
      setInsight(await postJson<InsightRead>(path, body));
    } catch (err) {
      setInsight(null);
      setAiError(err instanceof ApiError ? err : new ApiError("The AI request failed.", 0, "unknown"));
    } finally {
      setBusy(null);
      setHistoryKey((k) => k + 1);
    }
  };

  const openInsight = async (id: number) => {
    setAiError(null);
    try {
      setInsight(await apiFetch<InsightRead>(buildUrl(`/insights/${id}`)));
    } catch (err) {
      setAiError(err instanceof ApiError ? err : new ApiError("Could not open that insight.", 0, "unknown"));
    }
  };

  const visible = (currentRun?.anomalies ?? []).filter((a) => {
    if (!showLow && a.severity === "low") return false;
    if (scope === "all") return true;
    return a.period_end >= params.start_date && a.period_start <= params.end_date;
  });

  return (
    <>
      <PageHeader
        title="AI Insights"
        description="Statistical anomaly detection on your data, explained by Gemini using only verified metrics."
      />
      {aiOff && <AiNotConfigured />}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-5">
        <div className="space-y-4 xl:col-span-3">
          <Card title="Ask a question" description="Answered with approved analyses only — the AI never queries the database directly.">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (question.trim().length >= 3) callAi("question", "/insights/query", { question, ...filterBody(params) });
              }}
            >
              <label htmlFor="question" className="sr-only">Question</label>
              <div className="flex gap-2">
                <input
                  id="question"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  maxLength={500}
                  placeholder="e.g. Which category contributed most to profit?"
                  className="h-9 min-w-0 flex-1 rounded-md border border-line-strong bg-surface px-3 text-sm text-ink placeholder:text-ink-3"
                />
                <button
                  type="submit"
                  disabled={aiOff !== null || busy !== null || question.trim().length < 3}
                  title={aiOff ?? undefined}
                  className="inline-flex shrink-0 items-center gap-1.5 rounded-md bg-primary px-3 text-sm font-medium text-on-primary hover:bg-primary-hover disabled:opacity-50"
                >
                  {busy === "question" ? <Loader2 className="size-4 animate-spin" /> : <MessageSquareText className="size-4" />}
                  Ask
                </button>
              </div>
            </form>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {EXAMPLES.map((q) => (
                <button
                  key={q}
                  onClick={() => setQuestion(q)}
                  className="rounded-full border border-line px-2.5 py-1 text-xs text-ink-2 hover:border-line-strong hover:text-ink"
                >
                  {q}
                </button>
              ))}
            </div>
            <div className="mt-4 flex items-center justify-between gap-3 border-t border-line pt-4">
              <p className="text-sm text-ink-2">
                Executive summary for {formatDate(params.start_date)} – {formatDate(params.end_date)} and the current filters.
              </p>
              <button
                onClick={() => callAi("summary", "/insights/generate", { type: "executive_summary", ...filterBody(params) })}
                disabled={aiOff !== null || busy !== null}
                title={aiOff ?? undefined}
                className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-line-strong px-3 py-1.5 text-sm font-medium text-ink hover:bg-subtle disabled:opacity-50"
              >
                {busy === "summary" ? <Loader2 className="size-4 animate-spin" /> : <FileText className="size-4" />}
                Generate summary
              </button>
            </div>
          </Card>

          {busy && (
            <div className="flex items-center gap-2 rounded-lg border border-line bg-surface p-5 text-sm text-ink-2" role="status">
              <Loader2 className="size-4 animate-spin" /> Computing verified metrics and asking Gemini to interpret them…
            </div>
          )}
          {aiError && !busy && (
            <div className="rounded-lg border border-negative/30 bg-negative-soft px-4 py-3 text-sm" role="alert">
              <p className="flex items-center gap-2 font-medium text-negative">
                <AlertTriangle className="size-4" aria-hidden="true" /> No AI insight was produced
              </p>
              <p className="mt-1 text-ink">{aiError.message}</p>
              <p className="mt-1 text-xs text-ink-3">
                Code: {aiError.code}. Nothing was invented in its place; dashboards and anomaly results are unaffected.
              </p>
            </div>
          )}
          {insight && !busy && <InsightView insight={insight} />}

          <RecentInsights key={historyKey} onOpen={openInsight} />
        </div>

        <div className="xl:col-span-2">
          <Card
            title="Detected anomalies"
            description="Statistical deviations from each segment's own baseline. Not confirmed problems."
            action={
              <button
                onClick={runDetection}
                disabled={detecting}
                className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-on-primary hover:bg-primary-hover disabled:opacity-60"
              >
                {detecting ? <Loader2 className="size-3.5 animate-spin" /> : <Play className="size-3.5" />}
                {currentRun ? "Re-run" : "Run detection"}
              </button>
            }
          >
            {detectError && <ErrorState error={detectError} />}
            {!currentRun && latest.loading && <Skeleton className="h-32" />}
            {!currentRun && latest.error && latest.error.status !== 404 && <ErrorState error={latest.error} onRetry={latest.reload} />}
            {!currentRun && latest.error?.status === 404 && (
              <p className="py-6 text-center text-sm text-ink-3">Detection has not been run yet. Run it to scan the full history.</p>
            )}
            {currentRun && (
              <>
                <div className="flex flex-wrap items-center gap-2 text-xs text-ink-3">
                  <span>Run #{currentRun.id} · {dateTime.format(new Date(currentRun.created_at))}</span>
                  {(["high", "medium", "low"] as Severity[]).map((s) => (
                    <span key={s} className={`rounded-full px-2 py-0.5 font-medium ${SEVERITY[s].className}`}>
                      {currentRun.counts[s] ?? 0} {SEVERITY[s].label.toLowerCase()}
                    </span>
                  ))}
                </div>
                <div className="mt-3 flex flex-wrap gap-3 text-xs text-ink-2">
                  <label className="inline-flex items-center gap-1.5">
                    <input type="radio" name="scope" checked={scope === "period"} onChange={() => setScope("period")} />
                    Selected period
                  </label>
                  <label className="inline-flex items-center gap-1.5">
                    <input type="radio" name="scope" checked={scope === "all"} onChange={() => setScope("all")} />
                    All history
                  </label>
                  <label className="inline-flex items-center gap-1.5">
                    <input type="checkbox" checked={showLow} onChange={(e) => setShowLow(e.target.checked)} />
                    Show low severity
                  </label>
                </div>
                {visible.length === 0 ? (
                  <p className="py-6 text-center text-sm text-ink-3">
                    No anomalies {scope === "period" ? "in the selected period" : "found"}.
                  </p>
                ) : (
                  <ul className="mt-3 space-y-2">
                    {visible.map((a) => (
                      <AnomalyItem
                        key={a.key}
                        anomaly={a}
                        explainDisabled={aiOff}
                        explaining={busy === a.key}
                        onExplain={() =>
                          callAi(a.key, "/insights/generate", { type: "anomaly_explanation", anomaly: { run_id: currentRun.id, key: a.key } })
                        }
                      />
                    ))}
                  </ul>
                )}
              </>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}

export default function InsightsPage() {
  return <AnalyticsGate>{(params) => <InsightsContent params={params} />}</AnalyticsGate>;
}
