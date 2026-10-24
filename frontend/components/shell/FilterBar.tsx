"use client";

import { CalendarRange } from "lucide-react";

import { PRESET_LABELS, useFilters, type RangePreset } from "@/components/shell/FiltersProvider";
import { channelLabel, formatDate } from "@/lib/format";

const selectClass =
  "h-8 rounded-md border border-line bg-surface px-2 text-[13px] text-ink hover:border-line-strong disabled:opacity-50";

export function FilterBar() {
  const f = useFilters();
  const options = f.options;
  if (!options?.has_data) return null;

  return (
    <div className="flex flex-wrap items-center gap-2 border-t border-line px-4 py-2 md:px-8" aria-label="Filters" role="group">
      <CalendarRange className="size-4 text-ink-3" aria-hidden="true" />
      <label className="sr-only" htmlFor="range-preset">Date range</label>
      <select
        id="range-preset"
        className={selectClass}
        value={f.preset}
        onChange={(e) => f.setPreset(e.target.value as RangePreset)}
      >
        {(Object.keys(PRESET_LABELS) as RangePreset[]).map((p) => (
          <option key={p} value={p}>
            {PRESET_LABELS[p]}
          </option>
        ))}
      </select>

      {f.preset === "custom" && f.range ? (
        <span className="flex items-center gap-1.5 text-sm">
          <label className="sr-only" htmlFor="range-start">Start date</label>
          <input
            id="range-start"
            type="date"
            className={selectClass}
            value={f.range.start}
            min={options.date_min ?? undefined}
            max={f.range.end}
            onChange={(e) => e.target.value && f.setCustomRange({ start: e.target.value, end: f.range!.end })}
          />
          <span className="text-ink-3">to</span>
          <label className="sr-only" htmlFor="range-end">End date</label>
          <input
            id="range-end"
            type="date"
            className={selectClass}
            value={f.range.end}
            min={f.range.start}
            max={options.date_max ?? undefined}
            onChange={(e) => e.target.value && f.setCustomRange({ start: f.range!.start, end: e.target.value })}
          />
        </span>
      ) : (
        f.range && (
          <span className="tabular text-xs text-ink-3">
            {formatDate(f.range.start)} – {formatDate(f.range.end)}
          </span>
        )
      )}

      <span className="mx-1 hidden h-5 w-px bg-line sm:block" />

      <label className="sr-only" htmlFor="filter-store">Store</label>
      <select id="filter-store" className={selectClass} value={f.store} onChange={(e) => f.setStore(e.target.value)}>
        <option value="">All stores</option>
        {options.stores.map((s) => (
          <option key={s.code} value={s.code}>
            {s.name}
          </option>
        ))}
      </select>

      <label className="sr-only" htmlFor="filter-category">Category</label>
      <select id="filter-category" className={selectClass} value={f.category} onChange={(e) => f.setCategory(e.target.value)}>
        <option value="">All categories</option>
        {options.categories.map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </select>

      <label className="sr-only" htmlFor="filter-channel">Channel</label>
      <select id="filter-channel" className={selectClass} value={f.channel} onChange={(e) => f.setChannel(e.target.value)}>
        <option value="">All channels</option>
        {options.channels.map((c) => (
          <option key={c} value={c}>
            {channelLabel(c)}
          </option>
        ))}
      </select>

      {(f.store || f.category || f.channel) && (
        <button
          className="text-xs font-medium text-primary hover:text-primary-hover"
          onClick={() => {
            f.setStore("");
            f.setCategory("");
            f.setChannel("");
          }}
        >
          Clear filters
        </button>
      )}

      <span className="ml-auto hidden text-xs text-ink-3 lg:inline">
        Data through {options.date_max ? formatDate(options.date_max) : "—"}
      </span>
    </div>
  );
}
