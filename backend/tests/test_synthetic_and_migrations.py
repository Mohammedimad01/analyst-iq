from datetime import date, timedelta
from decimal import Decimal

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.config import BACKEND_DIR
from app.demo import synthetic


def test_synthetic_data_is_reproducible_and_consistent():
    rows = synthetic.generate_rows()
    assert rows == synthetic.generate_rows()  # fixed seed
    assert len(rows) > 20_000
    for r in rows:
        gross = r["unit_price"] * r["quantity"]
        assert Decimal("0") <= r["discount_amount"] <= gross
        assert r["unit_cost"] < r["unit_price"]
        assert (r["channel"] == "in_store") == (r["store_id"] != "ECOM")
    assert {r["status"] for r in rows} == {"completed", "cancelled", "returned"}


def test_injected_store_drop_is_present():
    rows = synthetic.generate_rows()

    def s02_orders(start: date, days: int) -> int:
        window = {(start + timedelta(d)).isoformat() for d in range(days)}
        return len({r["order_id"] for r in rows if r["store_id"] == "S02" and r["order_date"] in window})

    anomaly = s02_orders(date(2026, 3, 9), 14)
    baseline = s02_orders(date(2026, 2, 23), 14)
    assert anomaly < baseline * 0.5


def test_migrations_upgrade_and_downgrade(tmp_path):
    url = f"sqlite:///{(tmp_path / 'migrate.db').as_posix()}"
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.attributes["database_url"] = url
    command.upgrade(cfg, "head")
    tables = set(inspect(create_engine(url)).get_table_names())
    assert {"organizations", "stores", "customers", "products", "orders", "order_items", "data_imports"} <= tables
    command.downgrade(cfg, "base")
    assert set(inspect(create_engine(url)).get_table_names()) <= {"alembic_version"}
