"""Unit tests for ContractValidator: date cascades, German comma decimals, quarantine routing."""

from pathlib import Path

from fieldkit_ingest.contracts import ContractValidator


def test_contract_validation_and_quarantine(tmp_path: Path) -> None:
    contract_file = tmp_path / "test_contract.yaml"
    contract_file.write_text(
        """
name: test_source
columns:
  id:
    type: str
    required: true
    nullable: false
  price:
    type: float
    required: true
    nullable: false
    locale: de
  order_date:
    type: date
    required: true
    nullable: false
    date_formats: ["%d.%m.%Y", "%Y-%m-%d", "%m/%d/%y"]
""",
        encoding="utf-8",
    )

    validator = ContractValidator(contract_file)

    records = [
        # 1. Valid record with German date and comma decimal
        {"id": "REC-001", "price": "1.250,50", "order_date": "24.12.2024", "_source_row_num": 1},
        # 2. Valid record with ISO date and standard comma
        {"id": "REC-002", "price": "45,00", "order_date": "2024-05-10", "_source_row_num": 2},
        # 3. Invalid record: missing required non-nullable id
        {"id": "", "price": "10,00", "order_date": "2024-01-01", "_source_row_num": 3},
        # 4. Invalid record: invalid decimal
        {"id": "REC-004", "price": "N/A", "order_date": "2024-01-01", "_source_row_num": 4},
        # 5. Invalid record: unrecognizable date
        {"id": "REC-005", "price": "10,00", "order_date": "yesterday", "_source_row_num": 5},
    ]

    res = validator.validate_batch(records, "test_source", "run_123")

    # Valid records: 1 and 2
    assert len(res.valid_records) == 2
    assert res.valid_records[0]["price"] == 1250.50
    assert res.valid_records[0]["order_date"] == "2024-12-24"
    assert res.valid_records[1]["price"] == 45.00
    assert res.valid_records[1]["order_date"] == "2024-05-10"

    # Quarantined records: 3, 4, 5
    assert len(res.quarantined_records) == 3
    reasons = [q["reason"] for q in res.quarantined_records]
    assert any("Missing non-nullable" in r for r in reasons)
    assert any("Invalid decimal" in r for r in reasons)
    assert any("Unrecognized date format" in r for r in reasons)
