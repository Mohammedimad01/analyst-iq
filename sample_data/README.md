# Sample data — SYNTHETIC

Everything here is generated. It is **not** real company performance and must never be presented as such.

| File | How it is made | Purpose |
|---|---|---|
| `retail_sample.csv` | `python -m app.cli generate` (from `backend/`), fixed seed 42, not committed | ~18k orders / 35k lines, Jan 2025 – Jun 2026 |
| `import_with_errors.csv` | hand-written, committed | demo of row-level validation in the Data Sources page |

## Shape of `retail_sample.csv`

- 4 physical stores (S01–S04) for `in_store`; `ECOM` E-commerce Hub for `online` and `marketplace`.
- 38 products in 6 categories with different margins (Grocery ~24 %, Beauty ~62 %).
- Seasonality: Nov ×1.35, Dec ×1.6, weekends higher; ~0.8 %/month growth.
- ~3 % cancelled, ~4 % returned (Apparel ~9 %). ~22 % of lines discounted; Black Friday week heavier.
- 1 Jan 2026: prices +3 %; Electronics costs +5 % on top (visible margin squeeze).

## Deliberately injected anomalies

| Id | What | When | Expected signal |
|---|---|---|---|
| A1 | Store S02 Riverside Mall in-store orders ×0.3 | 2026-03-09 → 2026-03-22 | store revenue / order drop |
| A2 | Beauty: 80 % of lines discounted 25–35 % | May 2026 | discount-rate spike, margin drop |
| A3 | ELE-002 Wireless Earbuds Pro return rate 35 % | April 2026 | product return-rate spike |
| A4 | Online orders ×3 | 2026-02-14 | one-day positive revenue spike |

These are used to test anomaly detection (Milestone 2).

## `import_with_errors.csv`

Contains 4 valid orders and these deliberate problems: a negative quantity, a non-ISO date, an unknown channel,
a discount larger than the line value, and an order whose lines disagree on the store. Expect 4 orders
accepted and the rest rejected with row-level messages.
