"""Unit tests for ticket classification data preparation and stratified splitting."""

from pathlib import Path
from unittest.mock import MagicMock

from fieldkit_ticketclf.data import (
    ALLOWED_PRIORITIES,
    ALLOWED_QUEUES,
    generate_ticket_corpus,
    load_parquet_records,
    normalize_ticket_record,
    prepare_and_split_dataset,
)


def test_normalize_ticket_record() -> None:
    """Verifies label normalization and field concatenation."""
    raw = {
        "subject": "Pump defect on line 2",
        "body": "Hydraulic pressure dropped below 40 bar on cylinder HX-200.",
        "language": "EN",
        "queue": "technical_defect",
        "priority": "HIGH",
    }
    normalized = normalize_ticket_record(raw)

    assert normalized["language"] == "en"
    assert normalized["queue"] == "technical_defect"
    assert normalized["priority"] == "high"
    assert "Pump defect on line 2" in normalized["text"]
    assert "HX-200" in normalized["text"]


def test_normalize_ticket_unknown_queue() -> None:
    """Verifies unknown or rare queues fall back to 'other'."""
    raw = {
        "subject": "Special question",
        "body": "Inquiry about coffee machine",
        "language": "de",
        "queue": "cafeteria_inquiry",
        "priority": "low",
    }
    normalized = normalize_ticket_record(raw)
    assert normalized["queue"] == "other"


def test_generate_ticket_corpus_distribution() -> None:
    """Verifies generation of balanced multilingual tickets."""
    corpus = generate_ticket_corpus(n_tickets=600, seed=42)

    assert len(corpus) == 600
    languages = {t["language"] for t in corpus}
    assert languages == {"en", "de"}

    queues = {t["queue"] for t in corpus}
    assert queues.issubset(ALLOWED_QUEUES)

    priorities = {t["priority"] for t in corpus}
    assert priorities.issubset(ALLOWED_PRIORITIES)


def test_prepare_and_split_dataset_ratios(tmp_path: Path) -> None:
    """Verifies 70/15/15 stratified split and parquet output."""
    splits = prepare_and_split_dataset(
        n_tickets=400,
        output_dir=tmp_path / "data",
        eval_path=tmp_path / "evals" / "clf_test.parquet",
        seed=42,
    )

    train_records = splits["train"]
    val_records = splits["val"]
    test_records = splits["test"]

    total = len(train_records) + len(val_records) + len(test_records)
    assert total == 400

    # Verify ~70% train, ~15% val, ~15% test
    assert 260 <= len(train_records) <= 300
    assert 50 <= len(val_records) <= 70
    assert 50 <= len(test_records) <= 70

    # Verify parquet files were written and can be read
    assert (tmp_path / "data" / "train.parquet").exists()
    assert (tmp_path / "data" / "val.parquet").exists()
    assert (tmp_path / "data" / "test.parquet").exists()
    assert (tmp_path / "evals" / "clf_test.parquet").exists()

    loaded = load_parquet_records(tmp_path / "evals" / "clf_test.parquet")
    assert len(loaded) == len(test_records)
    assert loaded[0]["ticket_id"] == test_records[0]["ticket_id"]


def test_normalize_hf_mappings() -> None:
    """Verifies external HF text labels map into Halden's 6 triage queues."""
    from fieldkit_ticketclf.data import normalize_hf_priority, normalize_hf_queue

    assert normalize_hf_queue("Hardware Failure on hydraulic motor") == "technical_defect"
    assert normalize_hf_queue("Shipping and carrier delay") == "order_delivery"
    assert normalize_hf_queue("Warranty replacement / RMA") == "returns_rma"
    assert normalize_hf_queue("Invoice payment dispute") == "billing_inquiry"
    assert normalize_hf_queue("Technical datasheet and CAD inquiry") == "general_inquiry"
    assert normalize_hf_queue("Unknown random topic") == "other"

    assert normalize_hf_priority("Urgent blocker") == "critical"
    assert normalize_hf_priority("Major high impact") == "high"
    assert normalize_hf_priority("Minor trivial bug") == "low"
    assert normalize_hf_priority("standard") == "medium"


def test_load_hf_dataset_drops_rare_queues(monkeypatch: object) -> None:
    """Verifies queues with < 50 examples are dropped into 'other'."""
    import datasets
    from fieldkit_ticketclf.data import load_hf_dataset

    # Create mock dataset: 60 technical_defect, 20 billing_inquiry (<50 -> other), 55 order_delivery
    mock_rows = []
    for i in range(60):
        mock_rows.append({
            "subject": f"Leak {i}",
            "body": "Oil pressure drop",
            "language": "en",
            "category": "technical defect",
            "priority": "high",
        })
    for i in range(20):
        mock_rows.append({
            "subject": f"Invoice {i}",
            "body": "Wrong tax",
            "language": "de",
            "category": "billing inquiry",
            "priority": "low",
        })
    for i in range(55):
        mock_rows.append({
            "subject": f"Delivery {i}",
            "body": "Tracking number missing",
            "language": "en",
            "category": "shipping delay",
            "priority": "medium",
        })

    mock_datasets = MagicMock()
    mock_datasets.load_dataset.return_value = mock_rows
    # Monkeypatch datasets module
    monkeypatch.setattr(datasets, "load_dataset", mock_datasets.load_dataset)  # type: ignore[attr-defined]

    tickets = load_hf_dataset(dataset_name="mock/test-tickets", min_queue_count=50, fallback_to_synthetic=False)
    assert len(tickets) == 135

    queues = [t["queue"] for t in tickets]
    # billing_inquiry had only 20 rows (< 50), so it must be mapped to "other"
    assert queues.count("technical_defect") == 60
    assert queues.count("order_delivery") == 55
    assert queues.count("billing_inquiry") == 0
    assert queues.count("other") == 20


def test_load_hf_dataset_offline_fallback() -> None:
    """Verifies that an unavailable dataset gracefully falls back to synthetic tickets."""
    from fieldkit_ticketclf.data import load_hf_dataset

    # Non-existent HF dataset with fallback_to_synthetic=True
    tickets = load_hf_dataset(
        dataset_name="nonexistent/fake-dataset-xyz-12345",
        max_records=50,
        fallback_to_synthetic=True,
    )
    assert len(tickets) == 50
    assert all("language" in t for t in tickets)
    assert all("queue" in t for t in tickets)

