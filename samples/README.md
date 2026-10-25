# Sample upload files

Synthetic, upload-ready datasets for **Data Sources → Import** (no real customers or businesses). Each is a
different business and period, so the dashboard visibly changes when you import one with "Replace existing data".

| File | Business | Period | Orders | Lines |
|---|---|---|---|---|
| `northwind_electronics_jul-dec_2025.csv` | Electronics chain, 4 stores, in-store/online/marketplace, holiday spike late Nov–Dec | Jul–Dec 2025 | 2,580 | 4,219 |
| `green_leaf_grocery_jan-jun_2026.xlsx` | Grocery chain, 3 stores, in-store/online, steady growth | Jan–Jun 2026 | 3,537 | 12,956 |

Both use every required and optional column (see the "File format and validation rules" section on the Data
Sources page) and pass validation with 0 rejected rows. About 3% of orders are cancelled and 5% returned, so those
rates show real values.
