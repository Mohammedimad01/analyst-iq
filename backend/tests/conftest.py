"""Tests run on in-memory SQLite by default.

  pytest --postgres      run the same suite on TEST_DATABASE_URL (from .env). Every table in that database is
                         emptied between tests, so it must be a throwaway database, never the app's DATABASE_URL.
  pytest --live-gemini   also run tests marked live_gemini against the real API (uses quota; needs GEMINI_* set).
"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models as m
from app.core.config import get_settings
from app.db.session import Base, get_db
from app.main import app


def pytest_addoption(parser):
    parser.addoption("--postgres", action="store_true", help="run against TEST_DATABASE_URL (PostgreSQL)")
    parser.addoption("--live-gemini", action="store_true", help="run tests that call the real Gemini API")


def pytest_configure(config):
    config.addinivalue_line("markers", "live_gemini: calls the real Gemini API (opt-in with --live-gemini)")
    config.addinivalue_line("markers", "postgres_only: needs --postgres")


def pytest_collection_modifyitems(config, items):
    skips = {"live_gemini": (config.getoption("--live-gemini"), "needs --live-gemini"),
             "postgres_only": (config.getoption("--postgres"), "needs --postgres")}
    for item in items:
        for marker, (enabled, reason) in skips.items():
            if marker in item.keywords and not enabled:
                item.add_marker(pytest.mark.skip(reason=reason))


@pytest.fixture(scope="session")
def engine(request):
    if request.config.getoption("--postgres"):
        settings = get_settings()
        url = settings.test_database_url
        if not url:
            pytest.exit("--postgres needs TEST_DATABASE_URL in .env", returncode=2)
        if url == settings.database_url or url == settings.database_url_direct:
            pytest.exit("TEST_DATABASE_URL must not be the application database", returncode=2)
        # A lock wait becomes a test error after 30 s instead of hanging the run.
        engine = create_engine(url, pool_pre_ping=True, connect_args={"options": "-c lock_timeout=30000"})
    else:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def reset_tables(engine) -> None:
    """Empty every table. One TRUNCATE on PostgreSQL: dropping/recreating per test is too slow over the network."""
    with engine.begin() as conn:
        if conn.dialect.name == "postgresql":
            names = ", ".join(t.name for t in Base.metadata.sorted_tables)
            conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
        else:
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(table.delete())


@pytest.fixture
def db(engine) -> Session:
    reset_tables(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    yield session
    session.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def org_id(db) -> int:
    from app.services.organization import get_demo_org_id
    return get_demo_org_id(db)


def add_order(db, org_id, number, day, store, channel, status, lines, customer=None):
    """lines: [(product, quantity, unit_price, discount, unit_cost)]"""
    order = m.Order(organization_id=org_id, order_number=number, order_date=day, store_id=store.id,
                    customer_id=customer.id if customer else None, channel=channel, status=status)
    for i, (product, qty, price, disc, cost) in enumerate(lines, start=1):
        order.items.append(m.OrderItem(line_number=i, product_id=product.id, quantity=qty,
                                       unit_price=Decimal(price), discount_amount=Decimal(disc),
                                       unit_cost=Decimal(cost)))
    db.add(order)


@pytest.fixture
def kpi_data(db, org_id):
    """Hand-calculable dataset. Expected values are derived in tests/test_metrics.py."""
    s1 = m.Store(organization_id=org_id, store_code="S1", name="Store One", region="North")
    s2 = m.Store(organization_id=org_id, store_code="S2", name="Store Two", region="South")
    p1 = m.Product(organization_id=org_id, sku="P1", name="Widget", category="X")
    p2 = m.Product(organization_id=org_id, sku="P2", name="Gadget", category="Y")
    db.add_all([s1, s2, p1, p2])
    db.flush()
    add_order(db, org_id, "O1", date(2025, 1, 10), s1, "in_store", "completed",
              [(p1, 2, "10.00", "2.00", "6.00"), (p2, 1, "20.00", "0", "15.00")])
    add_order(db, org_id, "O2", date(2025, 1, 15), s2, "online", "completed", [(p1, 3, "10.00", "0", "6.00")])
    add_order(db, org_id, "O3", date(2025, 1, 20), s1, "in_store", "cancelled", [(p2, 5, "20.00", "0", "15.00")])
    add_order(db, org_id, "O4", date(2025, 1, 25), s2, "online", "returned", [(p1, 1, "10.00", "0", "6.00")])
    add_order(db, org_id, "O5", date(2024, 12, 20), s1, "in_store", "completed", [(p1, 1, "10.00", "0", "6.00")])
    add_order(db, org_id, "O6", date(2025, 2, 1), s1, "in_store", "completed", [(p2, 1, "20.00", "0", "15.00")])
    add_order(db, org_id, "O7", date(2025, 1, 31), s1, "in_store", "completed", [(p1, 1, "10.00", "0", "6.00")])
    db.commit()
    return org_id


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    from app.core import ratelimit

    ratelimit.reset()
    yield
    ratelimit.reset()
