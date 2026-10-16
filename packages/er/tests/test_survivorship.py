"""Tests for Hierarchical Supplier Survivorship and Lineage Provenance."""

from __future__ import annotations

from fieldkit_er.survivorship import (
    CanonicalSupplier,
    RawSupplierRecord,
    merge_cluster_into_canonical,
)


def test_gleif_wins_authoritative() -> None:
    records = [
        RawSupplierRecord(
            id="erp_001",
            source_id="erp_vendors",
            source_row_ref="erp_vendors.csv:1",
            run_id="run_100",
            company_name="MUELLER HYDRAULIK GMBH",
            street="Hauptstr. 10",
            city="Hamburg",
            postal_code="20095",
            country="DE",
        ),
        RawSupplierRecord(
            id="gleif_001",
            source_id="gleif_eu",
            source_row_ref="gleif_eu.parquet:50",
            run_id="run_100",
            company_name="Müller Hydraulik GmbH",
            street="Hauptstraße 10",
            city="Hamburg",
            postal_code="20095",
            country="DE",
            lei="529900T8BM49AURSDO55",
        ),
    ]

    canonical: CanonicalSupplier = merge_cluster_into_canonical("cluster_1", records)

    # GLEIF authoritative values win for name, LEI, and street
    assert canonical.company_name == "Müller Hydraulik GmbH"
    assert canonical.lei == "529900T8BM49AURSDO55"
    assert canonical.provenance["company_name"].source_id == "gleif_eu"
    assert canonical.provenance["company_name"].rule_applied == "GLEIF_AUTHORITATIVE"
    assert set(canonical.member_ids) == {"erp_001", "gleif_001"}


def test_newest_erp_wins_when_no_gleif() -> None:
    records = [
        RawSupplierRecord(
            id="excel_001",
            source_id="planning_de_ham",
            source_row_ref="planning_de_ham.xlsx:5",
            run_id="run_101",
            company_name="MUELLER HYDR.",
            city="Hamburg",
            country="DE",
        ),
        RawSupplierRecord(
            id="erp_002",
            source_id="erp_vendors",
            source_row_ref="erp_vendors.csv:42",
            run_id="run_101",
            company_name="Mueller Hydraulik GmbH",
            city="Hamburg",
            postal_code="20095",
            country="DE",
        ),
    ]

    canonical: CanonicalSupplier = merge_cluster_into_canonical("cluster_2", records)

    # ERP wins over Excel
    assert canonical.company_name == "Mueller Hydraulik GmbH"
    assert canonical.provenance["company_name"].source_id == "erp_vendors"
    assert canonical.provenance["company_name"].rule_applied == "NEWEST_ERP"


def test_fallback_to_most_complete() -> None:
    # GLEIF record has missing street, but ERP record has street
    records = [
        RawSupplierRecord(
            id="gleif_002",
            source_id="gleif_eu",
            source_row_ref="gleif_eu.parquet:10",
            run_id="run_102",
            company_name="Krupp Stahl AG",
            street=None,  # Missing street in golden record
            city="Essen",
            postal_code="45127",
            country="DE",
            lei="96950012345678901234",
        ),
        RawSupplierRecord(
            id="erp_003",
            source_id="erp_vendors",
            source_row_ref="erp_vendors.csv:99",
            run_id="run_102",
            company_name="KRUPP STAHL",
            street="Altendorfer Str. 103",
            city="Essen",
            postal_code="45127",
            country="DE",
        ),
    ]

    canonical: CanonicalSupplier = merge_cluster_into_canonical("cluster_3", records)

    # GLEIF wins for company_name, but street falls back to ERP
    assert canonical.company_name == "Krupp Stahl AG"
    assert canonical.street == "Altendorfer Str. 103"
    assert canonical.provenance["street"].source_id == "erp_vendors"
