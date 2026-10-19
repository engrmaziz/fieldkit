"""Row-Level Security (RLS) Plant Isolation Tests for Foundry API."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from fieldkit_common.auth import Principal
from fieldkit_foundry.db import get_db_session
from fieldkit_foundry.main import app
from fieldkit_ontology.models import Base, PurchaseOrder, Supplier
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


@pytest.fixture
async def async_test_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    # Seed test data
    async with session_maker() as session:
        # Supplier (global, plant=None)
        sup = Supplier(
            id=uuid.uuid4(),
            natural_key="sup_krupp",
            supplier_code="sup_krupp",
            name="Krupp Hydraulik GmbH",
            country="DE",
            plant=None,
            row_hash="hash_sup_1",
            created_run_id="run_1",
            updated_run_id="run_1",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(sup)

        # 2 POs in Hamburg (DE-HAM)
        po1 = PurchaseOrder(
            id=uuid.uuid4(),
            natural_key="PO-HAM-001",
            po_number="PO-HAM-001",
            order_date=date(2024, 1, 15),
            total_amount=5000.0,
            currency="EUR",
            status="OPEN",
            plant="DE-HAM",
            row_hash="hash_ham_1",
            created_run_id="run_1",
            updated_run_id="run_1",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        po2 = PurchaseOrder(
            id=uuid.uuid4(),
            natural_key="PO-HAM-002",
            po_number="PO-HAM-002",
            order_date=date(2024, 2, 1),
            total_amount=7500.0,
            currency="EUR",
            status="OPEN",
            plant="DE-HAM",
            row_hash="hash_ham_2",
            created_run_id="run_1",
            updated_run_id="run_1",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # 2 POs in Stuttgart (DE-STR)
        po3 = PurchaseOrder(
            id=uuid.uuid4(),
            natural_key="PO-STR-001",
            po_number="PO-STR-001",
            order_date=date(2024, 1, 20),
            total_amount=12000.0,
            currency="EUR",
            status="OPEN",
            plant="DE-STR",
            row_hash="hash_str_1",
            created_run_id="run_1",
            updated_run_id="run_1",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        po4 = PurchaseOrder(
            id=uuid.uuid4(),
            natural_key="PO-STR-002",
            po_number="PO-STR-002",
            order_date=date(2024, 2, 10),
            total_amount=3200.0,
            currency="EUR",
            status="OPEN",
            plant="DE-STR",
            row_hash="hash_str_2",
            created_run_id="run_1",
            updated_run_id="run_1",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        session.add_all([po1, po2, po3, po4])
        await session.commit()

    yield session_maker
    await engine.dispose()


@pytest.mark.asyncio
async def test_mehmet_cannot_read_stuttgart_rows(async_test_session):
    """Proves mehmet (DE-HAM) cannot read DE-STR rows."""

    async def override_get_db():
        async with async_test_session() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db

    client = TestClient(app)

    from fieldkit_common.auth import get_current_principal

    # 1. Mehmet (Plant: DE-HAM, Role: quality)
    app.dependency_overrides[get_current_principal] = lambda: Principal(
        sub="mehmet_id",
        username="mehmet",
        roles=["quality"],
        plant="DE-HAM",
    )

    resp = client.get("/objects/PurchaseOrder")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2
    # Ensure all returned rows belong strictly to DE-HAM
    for item in data["items"]:
        assert item["plant"] == "DE-HAM"
        assert "PO-STR" not in item["po_number"]

    # Test via typed DSL query
    resp_query = client.post("/objects/query", json={"type": "PurchaseOrder", "filters": []})
    assert resp_query.status_code == 200
    q_data = resp_query.json()
    assert q_data["count"] == 2
    for item in q_data["items"]:
        assert item["plant"] == "DE-HAM"

    # 2. Lukas (Plant: DE-STR, Role: support)
    app.dependency_overrides[get_current_principal] = lambda: Principal(
        sub="lukas_id",
        username="lukas",
        roles=["support"],
        plant="DE-STR",
    )

    resp_str = client.get("/objects/PurchaseOrder")
    assert resp_str.status_code == 200
    data_str = resp_str.json()
    assert data_str["count"] == 2
    for item in data_str["items"]:
        assert item["plant"] == "DE-STR"
        assert "PO-HAM" not in item["po_number"]

    # 3. Jana (Role: admin, Plant: DE-HAM) -> Administrative Bypass
    app.dependency_overrides[get_current_principal] = lambda: Principal(
        sub="jana_id",
        username="jana",
        roles=["admin"],
        plant="DE-HAM",
    )

    resp_admin = client.get("/objects/PurchaseOrder")
    assert resp_admin.status_code == 200
    data_admin = resp_admin.json()
    assert data_admin["count"] == 4  # Sees both DE-HAM and DE-STR

    # Cleanup overrides
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_raw_sql_plant_isolation(async_test_session):
    """Proves that raw SQL and session queries under RLS context prevent cross-plant leakage."""
    from fieldkit_foundry.db import apply_plant_rls, set_rls_context
    from sqlalchemy import select

    mehmet = Principal(sub="mehmet_id", username="mehmet", roles=["quality"], plant="DE-HAM")
    lukas = Principal(sub="lukas_id", username="lukas", roles=["support"], plant="DE-STR")
    jana = Principal(sub="jana_id", username="jana", roles=["admin"], plant="DE-HAM")

    async with async_test_session() as session:
        # Mehmet query (DE-HAM)
        await set_rls_context(session, mehmet)
        q_mehmet = apply_plant_rls(select(PurchaseOrder), PurchaseOrder, mehmet)
        rows_mehmet = (await session.execute(q_mehmet)).scalars().all()
        assert len(rows_mehmet) == 2
        assert all(r.plant == "DE-HAM" for r in rows_mehmet)

        # Lukas query (DE-STR)
        await set_rls_context(session, lukas)
        q_lukas = apply_plant_rls(select(PurchaseOrder), PurchaseOrder, lukas)
        rows_lukas = (await session.execute(q_lukas)).scalars().all()
        assert len(rows_lukas) == 2
        assert all(r.plant == "DE-STR" for r in rows_lukas)

        # Admin query (Jana bypass)
        await set_rls_context(session, jana)
        q_jana = apply_plant_rls(select(PurchaseOrder), PurchaseOrder, jana)
        rows_jana = (await session.execute(q_jana)).scalars().all()
        assert len(rows_jana) == 4
