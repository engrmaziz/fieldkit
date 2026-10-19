"""Integration tests for ontology neighbor graph traversal and RLS boundary enforcement."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from fieldkit_common.auth import Principal, get_current_principal
from fieldkit_foundry.db import get_db_session
from fieldkit_foundry.main import app
from fieldkit_ontology.models import Base, Certificate, PurchaseOrder, Shipment, Supplier
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


@pytest.fixture
async def seeded_graph_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    sup_id = uuid.uuid4()
    po_ham_id = uuid.uuid4()
    po_str_id = uuid.uuid4()
    ship_id = uuid.uuid4()
    cert_id = uuid.uuid4()

    async with session_maker() as session:
        # Supplier (global)
        sup = Supplier(
            id=sup_id,
            natural_key="SUP-MUELLER",
            supplier_code="SUP-MUELLER",
            name="Müller Hydraulik GmbH",
            country="DE",
            plant=None,
            row_hash="h_sup",
            created_run_id="run_1",
            updated_run_id="run_1",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # PO in Hamburg linked to Supplier
        po_ham = PurchaseOrder(
            id=po_ham_id,
            natural_key="PO-HAM-901",
            po_number="PO-HAM-901",
            order_date=date(2024, 3, 1),
            total_amount=15000.0,
            currency="EUR",
            status="OPEN",
            plant="DE-HAM",
            supplier_id=sup_id,
            row_hash="h_po_ham",
            created_run_id="run_1",
            updated_run_id="run_1",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # PO in Stuttgart linked to Supplier
        po_str = PurchaseOrder(
            id=po_str_id,
            natural_key="PO-STR-902",
            po_number="PO-STR-902",
            order_date=date(2024, 3, 5),
            total_amount=8500.0,
            currency="EUR",
            status="OPEN",
            plant="DE-STR",
            supplier_id=sup_id,
            row_hash="h_po_str",
            created_run_id="run_1",
            updated_run_id="run_1",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Certificate linked to Supplier
        cert = Certificate(
            id=cert_id,
            natural_key="CERT-9001-MUELLER",
            certificate_number="CERT-9001-MUELLER",
            standard="ISO 9001",
            issuer="TÜV Süd",
            valid_from=date(2023, 1, 1),
            valid_to=date(2026, 1, 1),
            supplier_id=sup_id,
            plant=None,
            row_hash="h_cert",
            created_run_id="run_1",
            updated_run_id="run_1",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        # Shipment linked to Hamburg PO
        ship = Shipment(
            id=ship_id,
            natural_key="SHIP-HAM-001",
            shipment_number="SHIP-HAM-001",
            delivery_date=date(2024, 3, 15),
            status="DELIVERED",
            plant="DE-HAM",
            po_id=po_ham_id,
            row_hash="h_ship",
            created_run_id="run_1",
            updated_run_id="run_1",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        session.add_all([sup, po_ham, po_str, cert, ship])
        await session.commit()

    yield {
        "session_maker": session_maker,
        "sup_id": str(sup_id),
        "po_ham_id": str(po_ham_id),
        "po_str_id": str(po_str_id),
        "ship_id": str(ship_id),
        "cert_id": str(cert_id),
    }

    await engine.dispose()


@pytest.mark.asyncio
async def test_neighbors_traversal_and_rls(seeded_graph_session):
    data = seeded_graph_session

    async def override_get_db():
        async with data["session_maker"]() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db

    # 1. Mehmet (Plant: DE-HAM) queries Supplier neighbors
    app.dependency_overrides[get_current_principal] = lambda: Principal(
        sub="mehmet_id",
        username="mehmet",
        roles=["quality"],
        plant="DE-HAM",
    )

    client = TestClient(app)
    resp = client.get(f"/objects/Supplier/{data['sup_id']}/neighbors?depth=1")
    assert resp.status_code == 200
    res_data = resp.json()

    # Must see Hamburg PO and Certificate, but NOT Stuttgart PO
    po_numbers = [
        n["object"].get("po_number") for n in res_data["neighbors"] if "po_number" in n["object"]
    ]
    assert "PO-HAM-901" in po_numbers
    assert "PO-STR-902" not in po_numbers  # RLS plant isolation held across links!

    # 2. Depth 2 traversal: from Shipment -> PO -> Supplier
    resp_depth2 = client.get(f"/objects/Shipment/{data['ship_id']}/neighbors?depth=2")
    assert resp_depth2.status_code == 200
    d2_data = resp_depth2.json()
    depths = [n["depth"] for n in d2_data["neighbors"]]
    target_types = [n["target_type"] for n in d2_data["neighbors"]]
    assert 1 in depths
    assert 2 in depths
    assert "PurchaseOrder" in target_types
    assert "Supplier" in target_types

    # 3. Depth > 2 rejection
    resp_invalid_depth = client.get(f"/objects/Supplier/{data['sup_id']}/neighbors?depth=3")
    assert resp_invalid_depth.status_code == 422 or resp_invalid_depth.status_code == 400

    app.dependency_overrides.clear()
