"""Unit tests for CsvConnector: encoding and delimiter detection."""

from pathlib import Path

import pytest
from fieldkit_ingest.connectors.base import IngestContext
from fieldkit_ingest.connectors.csv_connector import CsvConnector


@pytest.mark.asyncio
async def test_latin1_umlaut_roundtrip(tmp_path: Path) -> None:
    """Verifies that German umlauts encoded in Latin-1 are preserved cleanly."""
    csv_file = tmp_path / "vendors_latin1.csv"
    # Write Latin-1 with umlauts and semicolon delimiter
    raw_content = "vendor_id;company_name;city\nERP-001;M\xfcller Hydraulik GmbH;M\xfcnchen\n"
    csv_file.write_bytes(raw_content.encode("latin-1"))

    connector = CsvConnector(csv_file)
    ctx = IngestContext(run_id="test_run", source_name="test_csv")

    batches = [b async for b in connector.extract(ctx)]
    assert len(batches) == 1
    records = batches[0].records
    assert len(records) == 1
    assert records[0]["vendor_id"] == "ERP-001"
    assert records[0]["company_name"] == "M\xfcller Hydraulik GmbH"
    assert records[0]["city"] == "M\xfcnchen"
    assert batches[0].metadata["delimiter"] == ";"


@pytest.mark.asyncio
async def test_utf8_comma_delimiter(tmp_path: Path) -> None:
    """Verifies UTF-8 and comma delimiter detection."""
    csv_file = tmp_path / "parts_utf8.csv"
    csv_file.write_text("part_id,name,cost\nHX-101,Ventil,45.50\n", encoding="utf-8")

    connector = CsvConnector(csv_file)
    ctx = IngestContext(run_id="test_run", source_name="test_csv")

    batches = [b async for b in connector.extract(ctx)]
    assert len(batches) == 1
    records = batches[0].records
    assert len(records) == 1
    assert records[0]["part_id"] == "HX-101"
    assert batches[0].metadata["delimiter"] == ","
