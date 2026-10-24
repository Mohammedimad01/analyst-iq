import { AlertTriangle, CheckCircle2, HelpCircle, Lightbulb, Search, ShieldCheck, Sparkles } from "lucide-react";
import type { ReactNode } from "react";

import type { InsightRead } from "@/types/api";

const TYPE_LABEL = { executive_summary: "Executive summary", anomaly_explanation: "Anomaly explanation", question: "Question" };
const dateTime = new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short" });

function Section({ icon, title, hint, children }: { icon: ReactNode; title: string; hint?: string; children: ReactNode }) {
  return (
    <section className="mt-4">
      <h3 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-ink-2">
        {icon}
        {title}
        {hint && <span className="font-normal normal-case tracking-normal text-ink-3">· {hint}</span>}
      </h3>
      <div className="mt-2">{children}</div>
    </section>
  );
}

export function InsightView({ insight }: { insight: InsightRead }) {
  const out = insight.output;
  if (!out) return null;
  const facts = new Map(insight.facts.map((f) => [f.key, f]));
  const dropped = insight.validation?.dropped ?? [];
  const ruleBased = insight.model === "rules";

  return (
    <article className="rounded-xl border border-line bg-surface p-5" aria-label="AI insight">
      <div className="flex flex-wrap items-center gap-2 text-xs text-ink-3">
        <span className="inline-flex items-center gap-1 rounded-full bg-primary-soft px-2 py-0.5 font-medium text-primary">
          <Sparkles className="size-3" aria-hidden="true" />
          {ruleBased ? "Rule-based answer" : "AI interpretation of verified metrics"}
        </span>
        <span>{TYPE_LABEL[insight.insight_type]}</span>
        <span>·</span>
        <span>{dateTime.format(new Date(insight.created_at))}</span>
        {!ruleBased && (
          <>
            <span>·</span>
            <span className="font-mono">{insight.model}</span>
          </>
        )}
        {insight.cached && <span className="rounded bg-subtle px-1.5 py-0.5">cached — no new AI call</span>}
      </div>
      {insight.question && <p className="mt-3 text-sm text-ink-2">“{insight.question}”</p>}
      <h2 className="mt-2 text-lg font-semibold tracking-tight text-ink">{out.title}</h2>
      <p className="mt-1 text-sm leading-relaxed text-ink">{out.summary}</p>

      {!out.answerable && (
        <p className="mt-3 flex gap-2 rounded-md bg-warning-soft px-3 py-2 text-sm text-warning">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          The available data cannot fully answer this. See what is missing below.
        </p>
      )}

      {out.observed_facts.length > 0 && (
        <Section icon={<CheckCircle2 className="size-3.5 text-positive" />} title="Observed facts" hint="each tied to a verified metric">
          <ul className="space-y-2">
            {out.observed_facts.map((f, i) => {
              const ev = facts.get(f.evidence_key);
              return (
                <li key={i} className="text-sm text-ink">
                  {f.statement}
                  {ev && (
                    <span className="ml-2 inline-flex rounded bg-subtle px-1.5 py-0.5 align-middle text-[11px] text-ink-2" title={f.evidence_key}>
                      {ev.label}: <span className="tabular ml-1 font-medium">{ev.display}</span>
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </Section>
      )}

      {out.possible_explanations.length > 0 && (
        <Section icon={<Lightbulb className="size-3.5 text-warning" />} title="Possible explanations" hint="hypotheses, not confirmed">
          <ul className="list-disc space-y-1 pl-5 text-sm text-ink-2">
            {out.possible_explanations.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </Section>
      )}

      {out.recommended_investigations.length > 0 && (
        <Section icon={<Search className="size-3.5 text-primary" />} title="Recommended investigations">
          <ul className="space-y-2 text-sm">
            {out.recommended_investigations.map((r, i) => (
              <li key={i}>
                <span className="font-medium text-ink">{r.action}</span>
                <span className="text-ink-2"> — {r.reason}</span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {out.information_needed.length > 0 && (
        <Section icon={<HelpCircle className="size-3.5 text-ink-3" />} title="Needs more information">
          <ul className="list-disc space-y-1 pl-5 text-sm text-ink-2">
            {out.information_needed.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </Section>
      )}

      {out.limitations.length > 0 && (
        <Section icon={<AlertTriangle className="size-3.5 text-ink-3" />} title="Limitations">
          <ul className="list-disc space-y-1 pl-5 text-sm text-ink-3">
            {out.limitations.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </Section>
      )}

      <footer className="mt-5 border-t border-line pt-3 text-xs text-ink-3">
        <p className="flex items-center gap-1.5">
          <ShieldCheck className="size-3.5 text-positive" aria-hidden="true" />
          Every number above was checked against the verified metrics before display.
          {dropped.length > 0 &&
            ` ${dropped.length} AI statement${dropped.length > 1 ? "s were" : " was"} removed because ${
              dropped.length > 1 ? "their" : "its"
            } numbers or references did not match.`}
        </p>
        {insight.facts.length > 0 && (
          <details className="mt-2">
            <summary className="cursor-pointer font-medium text-ink-2">Evidence sent to the AI ({insight.facts.length} facts)</summary>
            <div className="mt-2 max-h-64 overflow-auto rounded-md border border-line">
              <table className="w-full text-xs">
                <tbody>
                  {insight.facts.map((f) => (
                    <tr key={f.key} className="border-b border-line/60 last:border-0">
                      <td className="px-2 py-1 text-ink-2">{f.label}</td>
                      <td className="tabular px-2 py-1 text-right font-medium text-ink">{f.display}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        )}
      </footer>
    </article>
  );
}
