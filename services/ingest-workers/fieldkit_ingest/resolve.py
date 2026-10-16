"""Supplier Entity Resolution Pipeline Step.

Connects packages/er with services/ingest-workers:
- Extracts staged suppliers from DuckDB staging tables (stg_erp_vendors, stg_planning_de_ham, etc.)
- Normalizes records and generates match keys
- Clusters duplicate supplier representations
- Applies hierarchical survivorship (GLEIF authoritative > ERP > completeness)
- Writes resolved canonical suppliers with provenance into stg_canonical_suppliers
"""

from __future__ import annotations

import json
from typing import Any

import duckdb
from fieldkit_er.normalize import create_match_key
from fieldkit_er.survivorship import RawSupplierRecord, merge_cluster_into_canonical

from fieldkit_ingest.staging import StagingStore


def resolve_staged_suppliers(staging: StagingStore, run_id: str) -> dict[str, Any]:
    con = duckdb.connect(str(staging.db_path))

    # Read records from all available supplier staging tables
    tables = [t[0] for t in con.execute("SHOW TABLES").fetchall()]
    raw_records: list[RawSupplierRecord] = []

    # 1. ERP Vendors
    if "stg_erp_vendors" in tables:
        rows = con.execute("""
            SELECT vendor_id, company_name, street, city, postal_code, country
            FROM stg_erp_vendors
        """).fetchall()
        for r in rows:
            v_id, name, street, city, postcode, country = r
            raw_records.append(
                RawSupplierRecord(
                    id=f"erp_{v_id}",
                    source_id="erp_vendors",
                    source_row_ref=f"erp_vendors.csv:{v_id}",
                    run_id=run_id,
                    company_name=name,
                    street=street,
                    city=city,
                    postal_code=postcode,
                    country=country,
                )
            )

    # 2. Planning Excel (Hamburg)
    if "stg_planning_de_ham" in tables:
        rows = con.execute("""
            SELECT supplier_name, plant
            FROM stg_planning_de_ham
        """).fetchall()
        for idx, r in enumerate(rows):
            name, plant = r
            raw_records.append(
                RawSupplierRecord(
                    id=f"plan_ham_{idx}",
                    source_id="planning_de_ham",
                    source_row_ref=f"planning_de_ham.xlsx:row_{idx}",
                    run_id=run_id,
                    company_name=name,
                    city="Hamburg",
                    country="DE",
                )
            )

    # 3. Planning Excel (Stuttgart)
    if "stg_planning_de_str" in tables:
        rows = con.execute("""
            SELECT supplier_name, plant
            FROM stg_planning_de_str
        """).fetchall()
        for idx, r in enumerate(rows):
            name, plant = r
            raw_records.append(
                RawSupplierRecord(
                    id=f"plan_str_{idx}",
                    source_id="planning_de_str",
                    source_row_ref=f"planning_de_str.xlsx:row_{idx}",
                    run_id=run_id,
                    company_name=name,
                    city="Stuttgart",
                    country="DE",
                )
            )

    if not raw_records:
        return {"total_raw": 0, "canonical_count": 0, "clusters_count": 0}

    # Group into clusters by match_key
    clusters: dict[str, list[RawSupplierRecord]] = {}
    for rec in raw_records:
        m_key = create_match_key(rec.company_name or "", rec.postal_code or rec.city or "")
        clusters.setdefault(m_key, []).append(rec)

    canonical_rows: list[dict[str, Any]] = []
    for cluster_id, recs in clusters.items():
        canonical = merge_cluster_into_canonical(cluster_id, recs)
        canonical_rows.append(
            {
                "canonical_id": canonical.canonical_id,
                "cluster_id": canonical.cluster_id,
                "company_name": canonical.company_name,
                "street": canonical.street,
                "city": canonical.city,
                "postal_code": canonical.postal_code,
                "country": canonical.country,
                "lei": canonical.lei,
                "member_count": len(canonical.member_ids),
                "member_ids": json.dumps(canonical.member_ids),
                "provenance": json.dumps(
                    {
                        k: {
                            "source_id": v.source_id,
                            "source_row_ref": v.source_row_ref,
                            "rule": v.rule_applied,
                        }
                        for k, v in canonical.provenance.items()
                    }
                ),
            }
        )

    staging.write_records("stg_canonical_suppliers", canonical_rows)

    return {
        "total_raw": len(raw_records),
        "canonical_count": len(canonical_rows),
        "clusters_count": len(clusters),
    }
