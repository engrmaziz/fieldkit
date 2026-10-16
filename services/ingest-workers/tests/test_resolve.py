"""Tests for supplier entity resolution staging step."""

from __future__ import annotations

from pathlib import Path

from fieldkit_ingest.resolve import resolve_staged_suppliers
from fieldkit_ingest.staging import StagingStore


def test_resolve_staged_suppliers(tmp_path: Path) -> None:
    staging = StagingStore(run_id="test_run_123", staging_dir=tmp_path)
    db_file = staging.db_path

    # Seed staged vendors
    erp_records = [
        {
            "vendor_id": "V-101",
            "company_name": "Krupp Hydraulik GmbH",
            "street": "Industriestrasse 10",
            "city": "Essen",
            "postal_code": "45127",
            "country": "DE",
        },
        {
            "vendor_id": "V-102",
            "company_name": "Mannesmann Rohrbau AG",
            "street": "Kruppstrasse 5",
            "city": "Duesseldorf",
            "postal_code": "40213",
            "country": "DE",
        },
    ]
    planning_records = [
        {
            "supplier_name": "Krupp Hydraulik",
            "plant": "Hamburg",
        }
    ]

    staging.write_records("stg_erp_vendors", erp_records)
    staging.write_records("stg_planning_de_ham", planning_records)

    metrics = resolve_staged_suppliers(staging, run_id="test_run_123")

    assert metrics["total_raw"] == 3
    assert metrics["canonical_count"] >= 1
    assert metrics["clusters_count"] >= 1

    # Verify stg_canonical_suppliers exists in staging
    import duckdb

    con = duckdb.connect(str(db_file))
    res = con.execute("SELECT count(*) FROM stg_canonical_suppliers").fetchone()
    assert res is not None
    assert res[0] == metrics["canonical_count"]
