# Analyst IQ — Design

**World: editorial analytics.** A management report you can operate. Calm paper and ink, serif headline figures,
charts presented as captioned figures, hairline rules instead of floating cards. Mode: *Operate* — scanability and
consistency first; character lives in type, rules and numerals.

## Tokens (frontend/app/globals.css)

| Role | Light | Dark |
|---|---|---|
| page (paper) | `#f6f4ef` | `#141311` |
| surface | `#fffefb` | `#1c1a17` |
| subtle | `#efece5` | `#23211d` |
| rule / rule-strong | `#e2ddd2` / `#cfc8ba` | `#2f2c27` / `#3d3a33` |
| ink / ink-2 / ink-3 | `#1a1916` / `#4e4a42` / `#6f6a60` | `#ece8e0` / `#bdb7ab` / `#8f897d` |
| accent (actions, series 1) | `#1f4f86` | `#86aee0` |
| series 2 | `#b4532a` | `#d9824f` |
| positive / negative / warning | `#2d6a3e` / `#a33a30` / `#8a5a00` | `#7fbf8e` / `#e48a80` / `#d6a64a` |

Theme follows the OS, overridable with the header toggle (`data-theme` on `<html>`, remembered per browser).

## Type

- **Newsreader** (serif): page titles, KPI figures, figure titles. Tabular, lining numerals for figures.
- **IBM Plex Sans**: interface, tables, labels. `font-variant-numeric: tabular-nums` on every number column.
- **IBM Plex Mono**: codes only (SKUs, customer codes, env vars).

## Rules

- Panels are ruled frames (1px rule, 8px radius, no shadow). Never nest frames.
- KPIs sit in one ruled strip (`KpiStrip`), not separate cards.
- One accent. Status colours only mean good/bad/warning and always come with text or an icon.
- No gradients, glass, eyebrows above headings, or decorative sparklines.
