// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AnomalyItem } from "@/components/insights/AnomalyList";
import { InsightView } from "@/components/insights/InsightView";
import { KpiCard } from "@/components/ui/KpiCard";
import { ErrorState, NoMatchState } from "@/components/ui/States";
import { ApiError } from "@/lib/api";
import { dataBadge } from "@/lib/workspace";
import type { Anomaly, InsightRead, Kpi } from "@/types/api";

afterEach(cleanup);

const kpi = (over: Partial<Kpi>): Kpi => ({
  key: "net_revenue", label: "Net Revenue", unit: "currency", definition: "Sum of net line values.", value: 1234.5,
  previous: 1000, abs_change: 234.5, pct_change: 23.45, direction: "up", sentiment: "positive", ...over,
});

describe("KpiCard", () => {
  it("shows value, change, comparison and the calculation", () => {
    render(<KpiCard kpi={kpi({})} />);
    expect(screen.getByText("$1,235")).toBeTruthy();
    expect(screen.getByText(/\+23\.5%/)).toBeTruthy();
    expect(screen.getByText("vs $1,000")).toBeTruthy();
    expect(screen.getByRole("tooltip").textContent).toBe("Sum of net line values.");
  });

  it("states sentiment in text, so a rising return rate is not presented as good", () => {
    render(<KpiCard kpi={kpi({ key: "return_rate_pct", label: "Return Rate", unit: "percent", value: 6, previous: 5, abs_change: 1, pct_change: null, sentiment: "negative" })} />);
    expect(screen.getByText(/unfavourable/)).toBeTruthy();
    expect(screen.getByText(/\+1\.0 pp/)).toBeTruthy();
  });
});

describe("states", () => {
  it("error state shows the API message, says no figures are shown, and retries", () => {
    const retry = vi.fn();
    render(<ErrorState error={new ApiError("Cannot reach the API", 0, "network_error")} onRetry={retry} />);
    expect(screen.getByRole("alert").textContent).toContain("Cannot reach the API");
    expect(screen.getByText(/No figures are shown/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("database errors are named as such", () => {
    render(<ErrorState error={new ApiError("down", 503, "database_unavailable")} />);
    expect(screen.getByText("Database unavailable")).toBeTruthy();
  });

  it("no-match state explains how to recover", () => {
    render(<NoMatchState />);
    expect(screen.getByText(/Widen the range or clear a filter/)).toBeTruthy();
  });
});

const insight: InsightRead = {
  id: 1, insight_type: "executive_summary", status: "completed", created_at: "2026-10-24T10:00:00Z",
  model: "gemini-test", prompt_version: "v", question: null, intent: null, params: {}, analysis_run_id: null,
  duration_ms: 10, cached: true, error_code: null, error_message: null,
  facts: [{ key: "kpi.net_revenue.current", label: "Net Revenue (selected period)", value: 78, unit: "currency", display: "$78.00" }],
  output: {
    title: "January performance", summary: "Net revenue was $78.00.", answerable: true,
    observed_facts: [{ statement: "Net revenue was $78.00.", evidence_key: "kpi.net_revenue.current" }],
    possible_explanations: ["Category X may have sold more."],
    recommended_investigations: [{ action: "Review X pricing", reason: "It drove the change." }],
    information_needed: [], limitations: ["Synthetic data."],
  },
  validation: { dropped: [{ field: "observed_facts", text: "x", reason: "numbers not in evidence" }] },
};

describe("InsightView", () => {
  it("separates verified facts from hypotheses and shows the evidence value", () => {
    render(<InsightView insight={insight} />);
    expect(screen.getByText("AI interpretation of verified metrics")).toBeTruthy();
    expect(screen.getByText(/hypotheses, not confirmed/)).toBeTruthy();
    expect(screen.getAllByText("$78.00").length).toBeGreaterThan(0);
    expect(screen.getByText(/cached — no new AI call/)).toBeTruthy();
    expect(screen.getByText(/1 AI statement was removed/)).toBeTruthy();
  });

  it("labels rule-based answers and unanswerable questions", () => {
    render(<InsightView insight={{ ...insight, model: "rules", validation: { dropped: [] }, output: { ...insight.output!, answerable: false } }} />);
    expect(screen.getByText("Rule-based answer")).toBeTruthy();
    expect(screen.getByText(/cannot fully answer this/)).toBeTruthy();
  });
});

const anomaly: Anomaly = {
  key: "k", detector: "segment_volume_week", metric: "orders", metric_label: "Completed orders", dimension: "store",
  segment_key: "S02", segment_label: "Riverside Mall", grain: "week", period_start: "2026-03-09", period_end: "2026-03-15",
  observed: 8, expected: 39.7, abs_diff: -31.7, pct_diff: -79.9, z_score: -4.5, direction: "down", severity: "high",
  method: "m", evidence: {}, note: "Statistical anomaly",
};

describe("AnomalyItem", () => {
  it("names severity in text and disables AI with the reason when Gemini is off", () => {
    render(<AnomalyItem anomaly={anomaly} onExplain={() => {}} explainDisabled="Gemini is not configured" explaining={false} />);
    expect(screen.getByText("High")).toBeTruthy();
    expect(screen.getByText("(-80%)")).toBeTruthy();
    const button = screen.getByRole("button", { name: /explain with ai/i }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(button.title).toBe("Gemini is not configured");
  });
});

describe("dataBadge", () => {
  it("always labels synthetic data and leaves real data undecorated", () => {
    expect(dataBadge("synthetic")?.label).toBe("Synthetic demo data");
    expect(dataBadge("mixed")?.label).toBe("Includes synthetic demo data");
    expect(dataBadge("none")?.label).toBe("No data yet");
    expect(dataBadge("imported")).toBeNull();
  });
});
