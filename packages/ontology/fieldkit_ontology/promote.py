"""Transactional Staging to Ontology Promotion Engine with Lineage and Idempotency."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fieldkit_ontology.models import (
    LineageEdge,
    Part,
    Plant,
    PropertyProvenance,
    PurchaseOrder,
    QualityIncident,
    Supplier,
)


def compute_row_hash(data: dict[str, Any]) -> str:
    """Computes deterministic SHA-256 hash of record payload."""
    payload = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class OntologyPromoter:
    """Promotes resolved staged records from DuckDB into PostgreSQL ontology."""

    def __init__(self, staging_db_path: str | Path) -> None:
        self.db_path = Path(staging_db_path)

    async def promote(
        self,
        session: AsyncSession,
        run_id: str,
    ) -> dict[str, int]:
        """Promotes staged records in a single transactional batch.

        Idempotent: Unchanged records (matching row_hash) are left untouched.
        """
        start_time = datetime.now(UTC)
        if not self.db_path.exists():
            return {"inserted": 0, "updated": 0, "unchanged": 0}

        con = duckdb.connect(str(self.db_path), read_only=True)
        tables = [t[0] for t in con.execute("SHOW TABLES").fetchall()]

        inserted = 0
        updated = 0
        unchanged = 0

        # 1. Promote Canonical Suppliers
        if "stg_canonical_suppliers" in tables:
            rows = con.execute("""
                SELECT canonical_id, company_name, street, city, postal_code, country, lei, provenance
                FROM stg_canonical_suppliers
            """).fetchall()

            for r in rows:
                can_id, name, street, city, postal_code, country, lei, prov_json = r
                props = {
                    "supplier_code": can_id,
                    "name": name,
                    "street": street,
                    "city": city,
                    "postal_code": postal_code,
                    "country": country or "DE",
                    "lei": lei,
                }
                r_hash = compute_row_hash(props)

                existing = (
                    await session.execute(select(Supplier).where(Supplier.natural_key == can_id))
                ).scalar_one_or_none()

                if existing:
                    if existing.row_hash == r_hash:
                        unchanged += 1
                    else:
                        for k, v in props.items():
                            setattr(existing, k, v)
                        existing.row_hash = r_hash
                        existing.updated_run_id = run_id
                        existing.updated_at = datetime.now(UTC)
                        updated += 1
                else:
                    supplier = Supplier(
                        id=uuid.uuid4(),
                        natural_key=can_id,
                        plant=None,
                        row_hash=r_hash,
                        created_run_id=run_id,
                        updated_run_id=run_id,
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                        **props,
                    )
                    session.add(supplier)
                    inserted += 1

                    # Record property provenance
                    if prov_json:
                        try:
                            prov_map = json.loads(prov_json)
                            for prop_name, p_info in prov_map.items():
                                prov_entry = PropertyProvenance(
                                    id=uuid.uuid4(),
                                    object_id=supplier.id,
                                    object_type="Supplier",
                                    property_name=prop_name,
                                    value=str(props.get(prop_name)),
                                    source_id=p_info.get("source_id", "unknown"),
                                    source_row_ref=p_info.get("source_row_ref", "unknown"),
                                    run_id=run_id,
                                    rule_applied=p_info.get("rule", "AUTHORITATIVE"),
                                    recorded_at=datetime.now(UTC),
                                )
                                session.add(prov_entry)
                        except Exception:
                            pass

        # 2. Seed Default Plants
        plants_data = [
            ("DE-HAM", "Werk Hamburg", "Hamburg", "DE"),
            ("DE-STR", "Werk Stralsund", "Stralsund", "DE"),
            ("PL-WRO", "Zakład Wrocław", "Wrocław", "PL"),
        ]
        for p_code, p_name, p_loc, p_country in plants_data:
            existing_plant = (
                await session.execute(select(Plant).where(Plant.natural_key == p_code))
            ).scalar_one_or_none()
            if not existing_plant:
                plant_obj = Plant(
                    id=uuid.uuid4(),
                    natural_key=p_code,
                    plant=p_code,
                    plant_code=p_code,
                    name=p_name,
                    location=p_loc,
                    country=p_country,
                    row_hash=compute_row_hash({"code": p_code, "name": p_name}),
                    created_run_id=run_id,
                    updated_run_id=run_id,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
                session.add(plant_obj)
                inserted += 1

        # 3. Promote Parts
        if "stg_parts" in tables:
            rows = con.execute("""
                SELECT part_number, name, category, cost_eur
                FROM stg_parts
            """).fetchall()
            for r in rows:
                p_num, p_name, p_cat, p_cost = r
                props = {
                    "part_number": p_num,
                    "name": p_name or f"Part {p_num}",
                    "category": p_cat or "General",
                    "unit_of_measure": "PCS",
                    "unit_cost": float(p_cost or 0.0),
                }
                r_hash = compute_row_hash(props)
                existing_part = (
                    await session.execute(select(Part).where(Part.natural_key == p_num))
                ).scalar_one_or_none()
                if existing_part:
                    if existing_part.row_hash == r_hash:
                        unchanged += 1
                    else:
                        for k, v in props.items():
                            setattr(existing_part, k, v)
                        existing_part.row_hash = r_hash
                        existing_part.updated_run_id = run_id
                        existing_part.updated_at = datetime.now(UTC)
                        updated += 1
                else:
                    part = Part(
                        id=uuid.uuid4(),
                        natural_key=p_num,
                        plant=None,
                        row_hash=r_hash,
                        created_run_id=run_id,
                        updated_run_id=run_id,
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                        **props,
                    )
                    session.add(part)
                    inserted += 1

        # 4. Promote Purchase Orders
        if "stg_purchase_orders" in tables:
            rows = con.execute("""
                SELECT po_number, order_date, total_amount, currency, status, plant_code
                FROM stg_purchase_orders
            """).fetchall()

            for r in rows:
                po_num, o_date_str, amount, curr, status, plant_code = r
                o_date = None
                if o_date_str:
                    try:
                        o_date = datetime.strptime(str(o_date_str)[:10], "%Y-%m-%d").date()
                    except Exception:
                        o_date = datetime.now(UTC).date()

                props = {
                    "po_number": po_num,
                    "order_date": o_date,
                    "total_amount": float(amount or 0.0),
                    "currency": curr or "EUR",
                    "status": status or "OPEN",
                }
                r_hash = compute_row_hash(props)

                existing_po = (
                    await session.execute(
                        select(PurchaseOrder).where(PurchaseOrder.natural_key == po_num)
                    )
                ).scalar_one_or_none()

                if existing_po:
                    if existing_po.row_hash == r_hash:
                        unchanged += 1
                    else:
                        for k, v in props.items():
                            setattr(existing_po, k, v)
                        existing_po.row_hash = r_hash
                        existing_po.updated_run_id = run_id
                        existing_po.updated_at = datetime.now(UTC)
                        updated += 1

                else:
                    po = PurchaseOrder(
                        id=uuid.uuid4(),
                        natural_key=po_num,
                        plant=plant_code,
                        row_hash=r_hash,
                        created_run_id=run_id,
                        updated_run_id=run_id,
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                        **props,
                    )
                    session.add(po)
                    inserted += 1

        # 5. Promote Quality Incidents
        if "stg_quality_incidents" in tables:
            rows = con.execute("""
                SELECT incident_id, defect_type, severity, notes_de, notes_en
                FROM stg_quality_incidents
            """).fetchall()
            for r in rows:
                inc_id, defect, sev, notes_de, notes_en = r
                desc = notes_de or notes_en or defect or "Quality defect"
                props = {
                    "incident_number": inc_id,
                    "incident_date": datetime.now(UTC).date(),
                    "severity": sev or "MEDIUM",
                    "description": desc,
                    "resolution_status": "OPEN",
                }
                r_hash = compute_row_hash(props)
                existing_inc = (
                    await session.execute(
                        select(QualityIncident).where(QualityIncident.natural_key == inc_id)
                    )
                ).scalar_one_or_none()
                if existing_inc:
                    if existing_inc.row_hash == r_hash:
                        unchanged += 1
                    else:
                        for k, v in props.items():
                            setattr(existing_inc, k, v)
                        existing_inc.row_hash = r_hash
                        existing_inc.updated_run_id = run_id
                        existing_inc.updated_at = datetime.now(UTC)
                        updated += 1
                else:
                    inc = QualityIncident(
                        id=uuid.uuid4(),
                        natural_key=inc_id,
                        plant="DE-HAM",
                        row_hash=r_hash,
                        created_run_id=run_id,
                        updated_run_id=run_id,
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                        **props,
                    )
                    session.add(inc)
                    inserted += 1

        con.close()

        # 6. Record OpenLineage edge
        end_time = datetime.now(UTC)
        lineage_edge = LineageEdge(
            id=uuid.uuid4(),
            run_id=run_id,
            input_dataset=f"data/staging/{self.db_path.name}",
            transform="staging_to_ontology_promotion",
            output_dataset="postgres/ontology",
            started_at=start_time,
            ended_at=end_time,
            facets={
                "metrics": {
                    "inserted": inserted,
                    "updated": updated,
                    "unchanged": unchanged,
                },
                "spec_version": "1.0.0",
                "producer": "fieldkit-ontology.promote",
            },
        )
        session.add(lineage_edge)

        return {
            "inserted": inserted,
            "updated": updated,
            "unchanged": unchanged,
        }
