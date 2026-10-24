"""Tests run on in-memory SQLite by default. Set TEST_DATABASE_URL to run the same suite on PostgreSQL
(use a throwaway database: every test drops and recreates all tables)."""

import os
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models as m
from app.core.config import Settings
from app.db.session import Base, get_db
from app.main import app


def _make_test_engine():
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        return create_engine(Settings(database_url=url).database_url)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    return engine


@pytest.fixture(scope="session")
def engine():
    return _make_test_engine()


@pytest.fixture
def db(engine) -> Session:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
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
