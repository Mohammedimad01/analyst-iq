# KPI Definitions

Single implementation: `backend/app/services/analytics/metrics.py`. Tests with hand-calculated expectations:
`backend/tests/test_metrics.py`.

## Recognition policy

| Order status | Counts toward sales, profit, units, AOV? | Used for |
|---|---|---|
| `completed` | **Yes** | all revenue KPIs |
| `returned` | No (revenue is reversed in full) | return rate |
| `cancelled` | No (never fulfilled) | cancellation rate |

Taxes and shipping are not in the data model, so no KPI includes them.

## Line-level building blocks

```
line_gross     = quantity × unit_price
line_discount  = discount_amount
line_net       = line_gross − line_discount
line_cogs      = quantity × unit_cost          (cost snapshot on the line)
```

All sums are over **lines**; order counts use `COUNT(DISTINCT order_id)` so joining items never double-counts orders.

## KPIs (over the filtered period, recognised = completed orders)

| KPI | Formula | Zero-denominator | Good direction |
|---|---|---|---|
| Gross Sales | Σ line_gross (recognised) | — | up |
| Discounts | Σ line_discount (recognised) | — | neutral |
| **Net Revenue** | Σ line_net (recognised) | — | up |
| COGS | Σ line_cogs (recognised) | — | neutral |
| **Gross Profit** | Net Revenue − COGS | — | up |
| **Gross Margin %** | Gross Profit ÷ Net Revenue × 100 | `null` | up |
| **Orders** | distinct recognised orders | — | up |
| **Average Order Value** | Net Revenue ÷ Orders | `null` | up |
| **Units Sold** | Σ quantity (recognised) | — | up |
| Discount Rate % | Discounts ÷ Gross Sales × 100 | `null` | **down** |
| Return Rate % | returned orders ÷ (completed + returned orders) × 100 | `null` | **down** |
| Cancellation Rate % | cancelled orders ÷ all orders × 100 | `null` | **down** |

## Period comparison

- The comparison period is the **immediately preceding period of equal length** (e.g. 1–31 Mar vs 29 Jan–28 Feb
  for a 31-day range). Same filters apply to both.
- `abs_change = current − previous`.
- `pct_change = (current − previous) ÷ |previous| × 100`; `null` when previous is 0 or `null`.
- For percentage KPIs (margin, rates) the change is reported in **percentage points** (`pct_change` is `null`).
- `direction` is the sign of the change (`up`/`down`/`flat`). `sentiment` combines direction with the KPI's good
  direction, so a rising return rate is shown as **negative**.

## Breakdowns and trends

- **By category / store / channel / product:** Net Revenue, Gross Profit, Gross Margin %, Units, Orders and share
  of total Net Revenue for the filtered period. A product-level order count counts an order once per product it
  contains, so product order counts do not sum to total orders.
- **Trend:** Net Revenue, Gross Profit, Orders and Units per period bucket. Buckets: `day`, `week` (ISO week,
  Monday start) or `month`. The API picks `day` for ranges ≤ 45 days, `week` for ≤ 210 days, otherwise `month`,
  unless a grain is requested. Buckets with no sales are returned as zero, not omitted, so charts do not
  interpolate across gaps. The first and last buckets can be partial periods and are flagged.

## Filters

`start_date`, `end_date` (inclusive, required together, max span 3 years), `store` (codes), `category`, `channel`.
Every KPI, trend and breakdown in one response uses the same filter object.
Filters apply at **line level**: with `category=Apparel`, revenue includes only Apparel lines, and an order counts
toward Orders (and AOV) if it contains at least one Apparel line. Filtering by order status is not
offered: status is part of the KPI definitions above, so filtering it would silently change their meaning.

## Not calculated (the data cannot support them reliably)

Customer lifetime value, marketing ROI, inventory/stock-outs, net profit after operating costs, partial-return
rates.
