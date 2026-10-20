"""Unit tests for ticket classification data preparation and stratified splitting."""

from pathlib import Path

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
