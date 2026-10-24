"""Reproducible SYNTHETIC retail dataset (fixed seed). Not real company data.

Business rules the generator follows (so every KPI can be traced back):
- Prices and costs are fixed per product; on 2026-01-01 prices rise 3% and Electronics costs rise 5%.
- In-store orders belong to a physical store; online and marketplace orders to the E-commerce Hub.
- Discounts are absolute per line and never exceed quantity × unit price.
- Status: ~3% cancelled, ~4% returned (Apparel ~9%).
- Volume follows weekday and month seasonality plus slow growth.

Deliberate anomalies (for anomaly-detection tests, see sample_data/README.md):
  A1  Store S02 Riverside Mall: in-store orders drop ~70% from 2026-03-09 to 2026-03-22.
  A2  Category Beauty: discounts on most lines at ~30% during May 2026.
  A3  Product ELE-002 Wireless Earbuds Pro: ~35% of orders returned in April 2026.
  A4  Online channel: ~3x normal orders on 2026-02-14 (promotion spike).
"""

import csv
import random
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

SEED = 42
START = date(2025, 1, 1)
END = date(2026, 6, 30)
CENT = Decimal("0.01")

STORES = [  # code, name, region, in-store orders per day (base)
    ("S01", "Downtown Flagship", "North", 7.0),
    ("S02", "Riverside Mall", "South", 5.5),
    ("S03", "Airport Kiosk", "East", 2.5),
    ("S04", "Suburban Plaza", "West", 4.5),
]
ECOM = ("ECOM", "E-commerce Hub", "Online")
ONLINE_PER_DAY = {"online": 7.0, "marketplace": 3.0}

# category: (cost as share of price, return rate, max quantity, [(name, price, popularity)])
CATALOG = {
    "Electronics": (0.74, 0.04, 2, [
        ("Smart Watch S2", 199.00, 3), ("Wireless Earbuds Pro", 129.00, 5), ("Bluetooth Speaker Mini", 49.00, 4),
        ("USB-C Charger 65W", 39.00, 5), ("Noise-Cancel Headphones", 249.00, 2), ("4K Streaming Stick", 59.00, 3),
        ("Portable Power Bank", 35.00, 4)]),
    "Home & Kitchen": (0.58, 0.03, 3, [
        ("Ceramic Cookware Set", 149.00, 2), ("Chef Knife 8in", 69.00, 3), ("French Press 1L", 34.00, 4),
        ("Linen Throw Blanket", 59.00, 3), ("Glass Storage Set", 29.00, 5), ("Electric Kettle", 45.00, 4),
        ("Bamboo Cutting Board", 24.00, 4)]),
    "Apparel": (0.42, 0.09, 3, [
        ("Merino Crew Sweater", 89.00, 3), ("Everyday Chino", 59.00, 4), ("Organic Cotton Tee", 25.00, 6),
        ("Rain Shell Jacket", 129.00, 2), ("Wool Socks 3-Pack", 22.00, 5), ("Leather Belt", 39.00, 3)]),
    "Beauty": (0.38, 0.03, 3, [
        ("Vitamin C Serum", 32.00, 5), ("Daily Moisturizer SPF30", 28.00, 5), ("Clay Face Mask", 19.00, 4),
        ("Argan Hair Oil", 24.00, 3), ("Fragrance Eau de Parfum", 79.00, 2), ("Lip Care Trio", 15.00, 4)]),
    "Sports & Outdoors": (0.60, 0.04, 2, [
        ("Yoga Mat Pro", 49.00, 4), ("Insulated Water Bottle", 29.00, 6), ("Trail Running Shoes", 119.00, 3),
        ("Resistance Band Set", 25.00, 4), ("Camping Lantern", 39.00, 2), ("Daypack 25L", 69.00, 3)]),
    "Grocery & Snacks": (0.76, 0.01, 6, [
        ("Single-Origin Coffee 1kg", 24.00, 6), ("Dark Chocolate Bar", 4.50, 8), ("Mixed Nuts 500g", 12.00, 6),
        ("Matcha Tea Tin", 18.00, 3), ("Olive Oil 750ml", 16.00, 4), ("Protein Bar Box", 27.00, 4)]),
}
CATEGORY_CODES = {"Electronics": "ELE", "Home & Kitchen": "HOM", "Apparel": "APP", "Beauty": "BEA",
                  "Sports & Outdoors": "SPO", "Grocery & Snacks": "GRO"}

MONTH_FACTOR = {1: 0.85, 2: 0.85, 3: 0.95, 4: 1.0, 5: 1.0, 6: 1.0, 7: 1.05, 8: 1.05, 9: 0.95, 10: 1.0,
                11: 1.35, 12: 1.6}
WEEKDAY_FACTOR = (0.9, 0.9, 0.9, 0.95, 1.1, 1.3, 1.15)  # Mon..Sun
CUSTOMER_COUNT = 2400
REGIONS = ("North", "South", "East", "West")

COLUMNS = ("order_id", "line_number", "order_date", "store_id", "store_name", "store_region", "channel",
           "customer_id", "customer_segment", "customer_region", "product_sku", "product_name", "category",
           "quantity", "unit_price", "discount_amount", "unit_cost", "status")


def _money(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def _poisson(rng: random.Random, lam: float) -> int:
    # Knuth's method; lam stays small (< 30) here.
    limit, k, p = pow(2.718281828459045, -lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def _products() -> list[dict]:
    products = []
    for category, (cost_share, return_rate, max_qty, items) in CATALOG.items():
        for i, (name, price, popularity) in enumerate(items, start=1):
            products.append({"sku": f"{CATEGORY_CODES[category]}-{i:03d}", "name": name, "category": category,
                             "price": Decimal(str(price)), "cost_share": Decimal(str(cost_share)),
                             "return_rate": return_rate, "max_qty": max_qty, "weight": popularity})
    return products


def _prices(product: dict, day: date) -> tuple[Decimal, Decimal]:
    price, cost = product["price"], product["price"] * product["cost_share"]
    if day >= date(2026, 1, 1):
        price = price * Decimal("1.03")
        if product["category"] == "Electronics":
            cost = cost * Decimal("1.05") * Decimal("1.03")
        else:
            cost = cost * Decimal("1.03")
    return _money(price), _money(cost)


def generate_rows(seed: int = SEED) -> list[dict]:
    rng = random.Random(seed)
    products = _products()
    weights = [p["weight"] for p in products]
    customers = [(f"C{n:05d}", "business" if rng.random() < 0.15 else "consumer", rng.choice(REGIONS))
                 for n in range(1, CUSTOMER_COUNT + 1)]
    rows: list[dict] = []
    order_seq = 0
    day = START
    while day <= END:
        months_in = (day.year - START.year) * 12 + day.month - 1
        base = MONTH_FACTOR[day.month] * WEEKDAY_FACTOR[day.weekday()] * (1 + 0.008 * months_in)

        streams = []  # (store tuple, channel, expected orders)
        for code, name, region, per_day in STORES:
            factor = 0.3 if code == "S02" and date(2026, 3, 9) <= day <= date(2026, 3, 22) else 1.0  # A1
            streams.append(((code, name, region), "in_store", per_day * base * factor))
        for channel, per_day in ONLINE_PER_DAY.items():
            factor = 3.0 if channel == "online" and day == date(2026, 2, 14) else 1.0  # A4
            streams.append((ECOM, channel, per_day * base * factor))

        for (store_code, store_name, store_region), channel, expected in streams:
            for _ in range(_poisson(rng, expected)):
                order_seq += 1
                walk_in = channel == "in_store" and rng.random() < 0.15
                customer = None if walk_in else customers[min(int(rng.paretovariate(1.2)) - 1, CUSTOMER_COUNT - 1)
                                                          if rng.random() < 0.35 else rng.randrange(CUSTOMER_COUNT)]
                chosen = rng.choices(products, weights=weights, k=rng.choice((1, 1, 1, 2, 2, 3, 4)))
                unique = list({p["sku"]: p for p in chosen}.values())

                status = "completed"
                roll = rng.random()
                if roll < 0.03:
                    status = "cancelled"
                else:
                    return_rate = max(p["return_rate"] for p in unique)
                    if day.year == 2026 and day.month == 4 and any(p["sku"] == "ELE-002" for p in unique):
                        return_rate = 0.35  # A3
                    if rng.random() < return_rate:
                        status = "returned"

                for line_number, product in enumerate(unique, start=1):
                    unit_price, unit_cost = _prices(product, day)
                    quantity = rng.randint(1, product["max_qty"]) if rng.random() < 0.35 else 1
                    gross = unit_price * quantity
                    discount = Decimal("0")
                    discount_chance, discount_pct = 0.22, rng.uniform(0.05, 0.20)
                    if day.month == 11 and 24 <= day.day <= 30:  # Black Friday week
                        discount_chance, discount_pct = 0.6, rng.uniform(0.15, 0.30)
                    if product["category"] == "Beauty" and day.year == 2026 and day.month == 5:  # A2
                        discount_chance, discount_pct = 0.8, rng.uniform(0.25, 0.35)
                    if rng.random() < discount_chance:
                        discount = min(_money(gross * Decimal(str(discount_pct))), gross)
                    rows.append({
                        "order_id": f"SO-{order_seq:06d}", "line_number": line_number,
                        "order_date": day.isoformat(), "store_id": store_code, "store_name": store_name,
                        "store_region": store_region, "channel": channel,
                        "customer_id": customer[0] if customer else "",
                        "customer_segment": customer[1] if customer else "",
                        "customer_region": customer[2] if customer else "",
                        "product_sku": product["sku"], "product_name": product["name"],
                        "category": product["category"], "quantity": quantity, "unit_price": unit_price,
                        "discount_amount": discount, "unit_cost": unit_cost, "status": status,
                    })
        day += timedelta(days=1)
    return rows


def write_csv(path: Path, seed: int = SEED) -> int:
    rows = generate_rows(seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)
