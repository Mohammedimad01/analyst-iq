# Data Model

## Assumptions (decided, not discovered — change them deliberately)

1. **Grain.** One source row = one order line. An order has one store, one channel, one optional customer, one status.
2. **Order status** is one of `completed`, `cancelled`, `returned`.
   - `returned` means the **whole order** was returned. Partial returns are not modelled in Milestone 1.
   - Status is the latest known state at import time. Status changes are not re-imported (see rule 7).
3. **Money** is stored as `NUMERIC(12,2)` and handled as `Decimal` in Python. No floats in storage.
4. **Taxes and shipping are not part of the data model.** Prices are pre-tax item prices; no shipping lines.
   Columns with those names in an upload are ignored.
5. **Discounts** are an absolute amount per line (`discount_amount`), not a percentage.
6. **Cost** is snapshotted on each line (`unit_cost`) so later product cost changes never rewrite history.
7. **Immutability.** An order number that already exists is never overwritten. Re-importing it is rejected as a
   duplicate. Corrections require an explicit future "adjustment" feature, not silent replacement.
8. **Dates.** `orders.order_date` is the **business date in the store's local time**, exactly as the source
   provides it. All period filters use this date and are inclusive on both ends.
   Audit timestamps (`created_at`, import times) are timezone-aware UTC.
9. **Customers** carry only a code, a segment and a region. No names, emails or addresses.
10. **Tenancy.** Every business table has `organization_id`. Milestone 1 runs a single demo organisation and does
    **not** yet enforce isolation in queries beyond that single id.

## Tables

### organizations
| column | type | notes |
|---|---|---|
| id | int PK | |
| name | varchar(200) | |
| slug | varchar(100) | unique |
| created_at | timestamptz | |

### stores
| column | type | notes |
|---|---|---|
| id | int PK | |
| organization_id | FK → organizations | |
| store_code | varchar(50) | unique per organisation |
| name | varchar(200) | |
| region | varchar(100) null | |

### customers
| column | type | notes |
|---|---|---|
| id | int PK | |
| organization_id | FK | |
| customer_code | varchar(50) | unique per organisation |
| segment | varchar(50) null | e.g. `consumer`, `business` |
| region | varchar(100) null | |

### products
| column | type | notes |
|---|---|---|
| id | int PK | |
| organization_id | FK | |
| sku | varchar(64) | unique per organisation |
| name | varchar(200) | |
| category | varchar(100) | indexed |

### orders
| column | type | notes |
|---|---|---|
| id | int PK | |
| organization_id | FK | |
| order_number | varchar(64) | unique per organisation — duplicate guard |
| order_date | date | indexed with organisation |
| store_id | FK → stores | indexed |
| customer_id | FK → customers, null | |
| channel | varchar(20) | check: `in_store`, `online`, `marketplace` |
| status | varchar(20) | check: `completed`, `cancelled`, `returned` |
| import_id | FK → data_imports, null | lineage: which file created this order |
| created_at | timestamptz | |

### order_items
| column | type | notes |
|---|---|---|
| id | int PK | |
| order_id | FK → orders, cascade | indexed |
| line_number | int | unique with `order_id` |
| product_id | FK → products | indexed |
| quantity | int | check `> 0` |
| unit_price | numeric(12,2) | check `>= 0` |
| discount_amount | numeric(12,2) | check `>= 0` and `<= quantity × unit_price` |
| unit_cost | numeric(12,2) | check `>= 0`, snapshot at sale time |

### data_imports
| column | type | notes |
|---|---|---|
| id | int PK | |
| organization_id | FK | |
| filename | varchar(255) | original name, display only |
| file_sha256 | char(64) | indexed; identical re-upload of a completed file is rejected |
| status | varchar(20) | `processing`, `completed`, `failed`, `rejected` |
| rows_received / rows_accepted / rows_rejected | int | |
| errors | JSON | first 200 row-level errors `{row, column, message}` |
| message | text null | summary or failure reason |
| started_at / finished_at | timestamptz | |
| duration_ms | int null | |

### analysis_runs (migration 0002)
| column | type | notes |
|---|---|---|
| id | int PK | |
| organization_id | FK | indexed with type and time |
| analysis_type | varchar(50) | `anomaly_detection` |
| params | JSON | date range and detector thresholds used |
| result | JSON | full anomaly list, counts, evaluated range; history is never rewritten |
| created_at / duration_ms | | |

### ai_insights (migration 0002)
| column | type | notes |
|---|---|---|
| id | int PK | |
| organization_id | FK | indexed with created_at |
| insight_type | varchar(30) | check: `executive_summary`, `anomaly_explanation`, `question` |
| status | varchar(20) | check: `completed`, `failed`; failed attempts are kept for audit and rate limits |
| cache_key | char(64) | indexed; sha256 of type + prompt version + model + evidence + question |
| question / intent | text / JSON | for natural-language questions |
| params | JSON | filters or anomaly reference |
| evidence | JSON | the exact facts sent to the model (supporting metric references) |
| output | JSON null | validated `InsightOutput` |
| validation | JSON null | statements dropped by the grounding check |
| model / prompt_version | varchar | model id from `GEMINI_MODEL`, or `rules` for rule-based answers |
| error_code / error_message | | for failed attempts |
| analysis_run_id | FK null | anomaly run the evidence came from |
| created_at / duration_ms | | |

## Planned tables

| table | milestone | purpose |
|---|---|---|
| `reports` | 3 | type, period, filters, generated file reference |
| `users` | later | only together with real authentication |

## Import rules

- Required columns: `order_id, order_date, store_id, channel, product_sku, product_name, category, quantity,
  unit_price, unit_cost, status`. Optional: `line_number, discount_amount, customer_id, customer_segment,
  customer_region, store_name, store_region`. Header matching is case-insensitive and trims spaces.
- **An order is accepted or rejected as a whole.** If any of its lines is invalid, or its lines disagree on
  order-level fields (date, store, channel, customer, status), every line of that order is rejected with a reason.
- Dimension rows (stores, products, customers) are created on first sight. Existing ones are not renamed by later
  files (rule 7 applies to reference data too).
- All accepted rows are written in **one transaction**. If it fails, nothing is written and the import is marked
  `failed`.
