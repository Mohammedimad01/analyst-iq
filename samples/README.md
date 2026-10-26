# Sample upload files

Synthetic, upload-ready datasets for **Data Sources → Import** (no real customers or businesses). Each is a
different business and period, so the dashboard visibly changes when you import one with "Replace existing data".

| File | Business | Period | Orders | Lines |
|---|---|---|---|---|
| `northwind_electronics_jul-dec_2025.csv` | Electronics chain, 4 stores, in-store/online/marketplace, holiday spike late Nov–Dec | Jul–Dec 2025 | 2,580 | 4,219 |
| `green_leaf_grocery_jan-jun_2026.xlsx` | Grocery chain, 3 stores, in-store/online, steady growth | Jan–Jun 2026 | 3,537 | 12,956 |
| `urban_thread_apparel_jan-sep_2026.csv` / `.xlsx` (same data) | Apparel chain, 4 stores, 28 products, seasonal ranges | Jan–Sep 2026 | 10,220 | 18,151 |

### Urban Thread: built-in business events

The apparel file contains four events that the anomaly detector finds (verified: 6 high, 6 medium flags, all
tied to these events):

| Event | When | What the data shows |
|---|---|---|
| Website outage | 11–17 May 2026 | Online orders collapse for one week |
| Summer clearance | 20–30 Jun 2026 | 30–50% discounts on Dresses and Footwear, order volume up |
| Roadworks at Northpoint (UT03) | 3–30 Aug 2026 | That store's orders fall about 60% |
| Faulty batch of Midi Wrap Dress (UT-012) | Jul–Sep 2026 | Return rate far above the rest of the range |

It also has seasonality (summer lines peak May–Aug, outerwear in Jan–Feb and Sep), busier Fri–Sun trading and
gentle month-on-month growth.

Both use every required and optional column (see the "File format and validation rules" section on the Data
Sources page) and pass validation with 0 rejected rows. About 3% of orders are cancelled and 5% returned, so those
rates show real values.
