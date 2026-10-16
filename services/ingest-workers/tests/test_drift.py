"""Unit tests for Schema Drift Detection, Statistical Fingerprinting, and Governed Overrides."""

from __future__ import annotations

import tempfile
import uuid

import pytest
from fieldkit_ingest.drift import (
    DriftEventType,
    DriftRuleEngine,
    DriftSeverity,
    DriftStore,
    LLMRenameSuggester,
    RenameSuggestion,
    compute_fingerprint,
)


def test_compute_fingerprint_empty() -> None:
    fp = compute_fingerprint(records=[], source="test_src", run_id="run_001")
    assert fp.row_count == 0
    assert fp.columns == []
    assert fp.null_rate == {}


def test_compute_fingerprint_stats() -> None:
    records = [
        {"vendor_id": "V1", "amount": 100.0, "status": "ACTIVE"},
        {"vendor_id": "V2", "amount": 200.0, "status": "ACTIVE"},
        {"vendor_id": "V3", "amount": 300.0, "status": "PENDING"},
        {"vendor_id": "V4", "amount": None, "status": "ACTIVE"},
    ]
    fp = compute_fingerprint(records=records, source="erp_vendors", run_id="run_002")

    assert fp.row_count == 4
    col_names = [c["name"] for c in fp.columns]
    assert "vendor_id" in col_names
    assert "amount" in col_names
    assert "status" in col_names

    # Check null rates
    assert fp.null_rate["vendor_id"] == 0.0
    assert fp.null_rate["amount"] == 0.25  # 1 out of 4 is null

    # Check distinct counts
    assert fp.distinct_count["status"] == 2  # ACTIVE, PENDING

    # Check top values
    assert "ACTIVE" in fp.top_values["status"]

    # Check numeric quantiles
    assert "amount" in fp.numeric_quantiles
    p50 = fp.numeric_quantiles["amount"]["p50"]
    assert 100.0 <= p50 <= 300.0


def test_drift_rule_column_removed_and_added() -> None:
    engine = DriftRuleEngine()

    contract = {
        "vendor_id": {"type": "str", "required": True},
        "legal_name": {"type": "str", "required": True},
        "optional_notes": {"type": "str", "required": False},
    }

    # Current payload has missing legal_name and optional_notes, plus unexpected new_company_name
    curr_records = [
        {"vendor_id": "V100", "new_company_name": "Acme GmbH"},
        {"vendor_id": "V101", "new_company_name": "Beta AG"},
    ]
    fp = compute_fingerprint(curr_records, source="erp_vendors", run_id="run_003")

    events = engine.evaluate(current=fp, contract_columns=contract)

    # Missing legal_name (required) -> BLOCK
    req_removed = [e for e in events if e.event_type == DriftEventType.COLUMN_REMOVED and e.column_name == "legal_name"]
    assert len(req_removed) == 1
    assert req_removed[0].severity == DriftSeverity.BLOCK

    # Missing optional_notes (optional) -> WARN
    opt_removed = [e for e in events if e.event_type == DriftEventType.COLUMN_REMOVED and e.column_name == "optional_notes"]
    assert len(opt_removed) == 1
    assert opt_removed[0].severity == DriftSeverity.WARN

    # Added new_company_name -> WARN
    col_added = [e for e in events if e.event_type == DriftEventType.COLUMN_ADDED and e.column_name == "new_company_name"]
    assert len(col_added) == 1
    assert col_added[0].severity == DriftSeverity.WARN


def test_drift_rule_dtype_changed() -> None:
    engine = DriftRuleEngine()

    contract = {
        "amount": {"type": "float", "required": True},
    }

    # Observed payload has string amounts that cannot be parsed as floats
    curr_records = [
        {"amount": "NOT_A_NUMBER_ABC"},
        {"amount": "UNPRICED"},
    ]
    fp = compute_fingerprint(curr_records, source="pos", run_id="run_004")

    events = engine.evaluate(current=fp, contract_columns=contract)
    dtype_events = [e for e in events if e.event_type == DriftEventType.DTYPE_CHANGED and e.column_name == "amount"]
    assert len(dtype_events) == 1
    assert dtype_events[0].severity == DriftSeverity.BLOCK


def test_drift_rule_statistical_shifts() -> None:
    engine = DriftRuleEngine()
    contract = {
        "city": {"type": "str", "required": True},
        "score": {"type": "float", "required": True},
    }

    # Baseline fingerprint
    base_records = [
        {"city": "Hamburg", "score": 10.0},
        {"city": "Hamburg", "score": 10.0},
        {"city": "Berlin", "score": 10.0},
    ]
    base_fp = compute_fingerprint(base_records, source="test", run_id="base_run")

    # Current with null spike, new enum value, and p50 shift > 50%
    curr_records = [
        {"city": "Hamburg", "score": 50.0},
        {"city": "Warsaw", "score": 50.0},  # New enum
        {"city": None, "score": None},      # Null spike
        {"city": None, "score": None},
    ]
    curr_fp = compute_fingerprint(curr_records, source="test", run_id="curr_run")

    events = engine.evaluate(current=curr_fp, contract_columns=contract, baseline=base_fp)

    null_spikes = [e for e in events if e.event_type == DriftEventType.NULL_RATE_SPIKE]
    assert len(null_spikes) >= 1

    new_enums = [e for e in events if e.event_type == DriftEventType.NEW_ENUM_VALUE and e.column_name == "city"]
    assert len(new_enums) == 1
    assert "Warsaw" in new_enums[0].details["new_values"]

    p50_shifts = [e for e in events if e.event_type == DriftEventType.NUMERIC_P50_SHIFT]
    assert len(p50_shifts) == 1
    assert p50_shifts[0].details["shift_pct"] >= 50.0


def test_drift_rule_with_active_override() -> None:
    # Contract expects legal_name, but payload has firm_name
    # An active override exists: erp_vendors:legal_name -> firm_name
    engine = DriftRuleEngine(overrides={"erp_vendors:legal_name": "firm_name"})

    contract = {
        "vendor_id": {"type": "str", "required": True},
        "legal_name": {"type": "str", "required": True},
    }
    curr_records = [
        {"vendor_id": "V1", "firm_name": "Acme Industries"},
    ]
    fp = compute_fingerprint(curr_records, source="erp_vendors", run_id="run_005")

    events = engine.evaluate(current=fp, contract_columns=contract)
    # The override suppresses the missing legal_name BLOCK error!
    assert len(events) == 0


@pytest.mark.asyncio
async def test_llm_rename_suggester_fallback() -> None:
    suggester = LLMRenameSuggester()
    suggestion = await suggester.suggest_rename(
        source_name="erp_vendors",
        old_col="legal_name",
        old_dtype="string",
        old_samples=["Müller GmbH", "Siemens AG"],
        new_col="company_name",
        new_dtype="string",
        new_samples=["Müller GmbH", "Siemens AG"],
    )

    assert isinstance(suggestion, RenameSuggestion)
    assert suggestion.old_name == "legal_name"
    assert suggestion.new_name == "company_name"
    assert suggestion.confidence > 0.0
    assert len(suggestion.reason) > 0


def test_drift_store_persistence_and_approval() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        store = DriftStore(postgres_dsn="postgresql://invalid:5432/none", fallback_dir=tmp_dir)

        event_id = f"drift_{uuid.uuid4().hex[:12]}"
        from fieldkit_ingest.drift import DriftEvent

        event = DriftEvent(
            event_id=event_id,
            run_id="run_test_store",
            source="erp_vendors",
            event_type=DriftEventType.COLUMN_REMOVED,
            severity=DriftSeverity.BLOCK,
            column_name="legal_name",
            details={"message": "Missing column"},
            suggestion=RenameSuggestion(
                old_name="legal_name",
                new_name="vendor_legal_name",
                confidence=0.95,
                reason="Semantic exact match",
            ),
            status="open",
        )

        store.save_events([event])

        # Approve mapping
        approved = store.approve_mapping(event_id, approved_by="jana")
        assert approved is True

        # Check active overrides
        overrides = store.get_active_overrides("erp_vendors")
        assert overrides.get("erp_vendors:legal_name") == "vendor_legal_name"
