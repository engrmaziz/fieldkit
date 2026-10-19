"""Integration tests for property-level lineage provenance and OpenLineage edge retrieval."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from fieldkit_common.auth import Principal, get_current_principal
from fieldkit_foundry.db import get_db_session
from fieldkit_foundry.main import app
from fieldkit_ontology.models import Base, LineageEdge, PropertyProvenance, Supplier
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


@pytest.fixture
async def lineage_test_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    sup_id = uuid.uuid4()
    run_id = "run_20261018_ingest"

    async with session_maker() as session:
        sup = Supplier(
            id=sup_id,
            natural_key="sup_bosch",
            supplier_code="sup_bosch",
            name="Robert Bosch GmbH",
            country="DE",
            plant=None,
            row_hash="h_bosch",
            created_run_id=run_id,
            updated_run_id=run_id,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        prov_1 = PropertyProvenance(
            id=uuid.uuid4(),
            object_id=sup_id,
            object_type="Supplier",
            property_name="name",
            value="Robert Bosch GmbH",
            source_id="gleif_eu",
            source_row_ref="gleif.csv:10492",
            run_id=run_id,
            rule_applied="GLEIF_AUTHORITATIVE",
            recorded_at=datetime.now(UTC),
        )

        edge = LineageEdge(
            id=uuid.uuid4(),
            run_id=run_id,
            input_dataset=f"data/staging/{run_id}.duckdb",
            transform="staging_to_ontology_promotion",
            output_dataset="postgres/ontology",
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC),
            facets={"producer": "fieldkit-ontology"},
        )

        session.add_all([sup, prov_1, edge])
        await session.commit()

    yield {
        "session_maker": session_maker,
        "sup_id": str(sup_id),
        "run_id": run_id,
    }

    await engine.dispose()


@pytest.mark.asyncio
async def test_get_property_lineage_endpoint(lineage_test_session):
    data = lineage_test_session

    async def override_get_db():
        async with data["session_maker"]() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_current_principal] = lambda: Principal(
        sub="jana_id",
        username="jana",
        roles=["admin"],
        plant="DE-HAM",
    )

    client = TestClient(app)

    # 1. Query lineage for property 'name'
    resp = client.get(f"/lineage/Supplier/{data['sup_id']}/name")
    assert resp.status_code == 200
    res_data = resp.json()

    assert res_data["object_type"] == "Supplier"
    assert res_data["object_id"] == data["sup_id"]
    assert res_data["property_name"] == "name"
    assert res_data["current_value"] == "Robert Bosch GmbH"
    assert res_data["provenance_count"] == 1

    entry = res_data["history"][0]
    assert entry["source_id"] == "gleif_eu"
    assert entry["rule_applied"] == "GLEIF_AUTHORITATIVE"

    assert len(res_data["transforms"]) == 1
    assert res_data["transforms"][0]["run_id"] == data["run_id"]

    # 2. Query non-existent object returns 404
    fake_id = str(uuid.uuid4())
    resp_404 = client.get(f"/lineage/Supplier/{fake_id}/name")
    assert resp_404.status_code == 404

    app.dependency_overrides.clear()
