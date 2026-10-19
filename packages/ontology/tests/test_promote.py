"""Tests for transactional, idempotent ontology promotion and lineage tracking."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

import duckdb
import pytest
from fieldkit_ontology.models import (
    Base,
    LineageEdge,
    Part,
    Plant,
    PropertyProvenance,
    PurchaseOrder,
    QualityIncident,
    Supplier,
)
from fieldkit_ontology.promote import OntologyPromoter
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


@pytest.fixture
async def async_db() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield session_factory
    await engine.dispose()


@pytest.fixture
def staged_duckdb(tmp_path: Path) -> Path:
    db_path = tmp_path / "staged.duckdb"
    con = duckdb.connect(str(db_path))

    # 1. Canonical suppliers
    con.execute("""
        CREATE TABLE stg_canonical_suppliers (
            canonical_id VARCHAR,
            cluster_id VARCHAR,
            company_name VARCHAR,
            street VARCHAR,
            city VARCHAR,
            postal_code VARCHAR,
            country VARCHAR,
            lei VARCHAR,
            member_count INTEGER,
            member_ids VARCHAR,
            provenance VARCHAR
        );
        INSERT INTO stg_canonical_suppliers VALUES (
            'sup_101', 'cl_1', 'Krupp Hydraulik GmbH', 'Industriestr. 10', 'Essen', '45127', 'DE', '529900T8BM49AURSDO55', 2, '["erp_1", "plan_1"]',
            '{"name": {"source_id": "gleif_eu", "source_row_ref": "gleif.csv:1", "rule": "GLEIF_AUTHORITATIVE"}}'
        );
    """)

    # 2. Purchase orders
    con.execute("""
        CREATE TABLE stg_purchase_orders (
            po_number VARCHAR,
            order_date VARCHAR,
            total_amount FLOAT,
            currency VARCHAR,
            status VARCHAR,
            plant_code VARCHAR
        );
        INSERT INTO stg_purchase_orders VALUES (
            'PO-2024-001', '2024-01-15', 12500.50, 'EUR', 'OPEN', 'DE-HAM'
        );
    """)

    # 3. Parts
    con.execute("""
        CREATE TABLE stg_parts (
            part_number VARCHAR,
            name VARCHAR,
            category VARCHAR,
            cost_eur FLOAT
        );
        INSERT INTO stg_parts VALUES (
            'HX-101-001', 'Halden Hydraulikventil', 'Hydraulikventile', 450.0
        );
    """)

    # 4. Quality Incidents
    con.execute("""
        CREATE TABLE stg_quality_incidents (
            incident_id VARCHAR,
            po_number VARCHAR,
            defect_type VARCHAR,
            severity VARCHAR,
            notes_de VARCHAR,
            notes_en VARCHAR
        );
        INSERT INTO stg_quality_incidents VALUES (
            'INC-00001', 'PO-2024-001', 'LEAKAGE_PRESSURE_TEST', 'HIGH',
            'Drucktest bei 350 bar fehlgeschlagen.', 'Pressure test failed.'
        );
    """)

    con.close()
    return db_path


@pytest.mark.asyncio
async def test_idempotent_promotion_and_provenance(
    async_db: async_sessionmaker[AsyncSession], staged_duckdb: Path
) -> None:
    promoter = OntologyPromoter(staged_duckdb)

    # 1. First promotion run
    async with async_db() as session:
        metrics1 = await promoter.promote(session, run_id="run_20261017_01")
        await session.commit()

    assert metrics1["inserted"] >= 4
    assert metrics1["updated"] == 0
    assert metrics1["unchanged"] == 0

    # Verify suppliers, plants, parts, incidents, and purchase orders exist
    async with async_db() as session:
        from sqlalchemy import select

        suppliers = (await session.execute(select(Supplier))).scalars().all()
        assert len(suppliers) == 1
        assert suppliers[0].natural_key == "sup_101"
        assert suppliers[0].created_run_id == "run_20261017_01"

        pos = (await session.execute(select(PurchaseOrder))).scalars().all()
        assert len(pos) == 1
        assert pos[0].plant == "DE-HAM"

        parts = (await session.execute(select(Part))).scalars().all()
        assert len(parts) == 1
        assert parts[0].natural_key == "HX-101-001"

        incidents = (await session.execute(select(QualityIncident))).scalars().all()
        assert len(incidents) == 1
        assert incidents[0].natural_key == "INC-00001"

        plants = (await session.execute(select(Plant))).scalars().all()
        assert len(plants) >= 3

        provenance = (await session.execute(select(PropertyProvenance))).scalars().all()
        assert len(provenance) >= 1

        lineage = (await session.execute(select(LineageEdge))).scalars().all()
        assert len(lineage) == 1
        assert lineage[0].run_id == "run_20261017_01"

    # 2. Second promotion run with identical data -> 0 updates, 0 inserts, all unchanged!
    async with async_db() as session:
        metrics2 = await promoter.promote(session, run_id="run_20261017_02")
        await session.commit()

    assert metrics2["inserted"] == 0
    assert metrics2["updated"] == 0
    assert metrics2["unchanged"] >= 4

    # Verify updated_run_id was NOT modified for unchanged records
    async with async_db() as session:
        suppliers = (await session.execute(select(Supplier))).scalars().all()
        assert suppliers[0].updated_run_id == "run_20261017_01"
