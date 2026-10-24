"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

import { useApi } from "@/hooks/useApi";
import { buildUrl, type ApiError } from "@/lib/api";
import { addDays } from "@/lib/format";
import type { FilterOptions, Workspace } from "@/types/api";

export type RangePreset = "30d" | "90d" | "365d" | "all" | "custom";

export const PRESET_LABELS: Record<RangePreset, string> = {
  "30d": "Last 30 days",
  "90d": "Last 90 days",
  "365d": "Last 12 months",
  all: "All data",
  custom: "Custom range",
};
const PRESET_DAYS: Partial<Record<RangePreset, number>> = { "30d": 30, "90d": 90, "365d": 365 };

export interface DateRange {
  start: string;
  end: string;
}

interface FiltersState {
  /** Organisation, data source and feature flags (GET /workspace); null while loading or on error. */
  workspace: Workspace | null;
  options: FilterOptions | null;
  optionsError: ApiError | null;
  optionsLoading: boolean;
  reloadOptions: () => void;
  preset: RangePreset;
  range: DateRange | null;
  setPreset: (preset: RangePreset) => void;
  setCustomRange: (range: DateRange) => void;
  store: string;
  setStore: (code: string) => void;
  category: string;
  setCategory: (category: string) => void;
  channel: string;
  setChannel: (channel: string) => void;
  /** Query params shared by every analytics request, or null until a range is known. */
  params: Record<string, string> | null;
}

const FiltersContext = createContext<FiltersState | null>(null);

/** Presets are anchored to the latest date in the data (not today), so historical datasets stay usable. */
export function presetRange(preset: RangePreset, options: FilterOptions): DateRange | null {
  if (!options.date_min || !options.date_max) return null;
  const days = PRESET_DAYS[preset];
  if (!days) return { start: options.date_min, end: options.date_max };
  const start = addDays(options.date_max, -(days - 1));
  return { start: start < options.date_min ? options.date_min : start, end: options.date_max };
}

export function FiltersProvider({ children }: { children: ReactNode }) {
  const { data: options, error, loading, reload: reloadFilters } = useApi<FilterOptions>(buildUrl("/dashboard/filters"));
  const { data: workspace, reload: reloadWorkspace } = useApi<Workspace>(buildUrl("/workspace"));
  const [preset, setPresetState] = useState<RangePreset>("90d");
  const [customRange, setCustomRangeState] = useState<DateRange | null>(null);
  // shortcut: one value per dimension in the UI although the API accepts several; add multi-select when asked.
  const [store, setStore] = useState("");
  const [category, setCategory] = useState("");
  const [channel, setChannel] = useState("");

  const value = useMemo<FiltersState>(() => {
    const range = preset === "custom" ? customRange : options ? presetRange(preset, options) : null;
    return {
      workspace,
      options,
      optionsError: error,
      optionsLoading: loading,
      // After an import both the filter options and the data-source labels change.
      reloadOptions: () => {
        reloadFilters();
        reloadWorkspace();
      },
      preset,
      range,
      setPreset: (next) => {
        if (next === "custom" && !customRange && options) setCustomRangeState(presetRange(preset, options));
        setPresetState(next);
      },
      setCustomRange: (next) => {
        setCustomRangeState(next);
        setPresetState("custom");
      },
      store,
      setStore,
      category,
      setCategory,
      channel,
      setChannel,
      params: range
        ? { start_date: range.start, end_date: range.end, store, category, channel }
        : null,
    };
  }, [workspace, options, error, loading, reloadFilters, reloadWorkspace, preset, customRange, store, category, channel]);

  return <FiltersContext.Provider value={value}>{children}</FiltersContext.Provider>;
}

export function useFilters(): FiltersState {
  const ctx = useContext(FiltersContext);
  if (!ctx) throw new Error("useFilters must be used inside <FiltersProvider>");
  return ctx;
}
