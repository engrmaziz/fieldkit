"""Unit tests for Hash-Chained Audit Ledger with SHA-256 tamper detection."""


from fieldkit_copilot.audit import AuditLedger


def test_genesis_event_and_hash_chaining() -> None:
    """Verifies that events are monotonically sequenced and hash-chained with SHA-256."""
    ledger = AuditLedger()
    e1 = ledger.record_event(
        ticket_id="TICK-101",
        event_type="STATE_TRANSITION",
        state_name="intake",
        payload={"raw_len": 120, "language": "de"},
    )
    assert e1.sequence == 1
    assert e1.prev_hash == "0" * 64
    assert len(e1.hash) == 64

    e2 = ledger.record_event(
        ticket_id="TICK-101",
        event_type="PLAN_PROPOSED",
        state_name="planning",
        payload={"action_count": 2, "tools": ["lookup_order", "create_rma"]},
    )
    assert e2.sequence == 2
    assert e2.prev_hash == e1.hash
    assert e2.hash != e1.hash

    e3 = ledger.record_event(
        ticket_id="TICK-101",
        event_type="APPROVAL_REQUESTED",
        state_name="approval_gate",
        payload={"awaiting": True, "side_effects": True},
    )
    assert e3.sequence == 3
    assert e3.prev_hash == e2.hash

    # Verify cryptographic integrity
    is_valid, errors = ledger.verify_integrity("TICK-101")
    assert is_valid is True
    assert len(errors) == 0


def test_tamper_detection_modified_payload() -> None:
    """Verifies 100% tamper detection when an attacker alters an event payload in the ledger."""
    ledger = AuditLedger()
    ledger.record_event("TICK-102", "STATE_TRANSITION", "intake", {"step": 1})
    e2 = ledger.record_event("TICK-102", "PLAN_PROPOSED", "planning", {"amount": 200.0})
    ledger.record_event("TICK-102", "TOOL_EXECUTED", "execution", {"status": "ok"})

    # Tamper with event 2's payload (e.g. altering credit amount)
    e2.payload["amount"] = 9999.0

    is_valid, errors = ledger.verify_integrity("TICK-102")
    assert is_valid is False
    assert any("Hash mismatch" in err or "Payload tampered" in err for err in errors)


def test_tamper_detection_altered_prev_hash() -> None:
    """Verifies tamper detection when prev_hash pointer is broken."""
    ledger = AuditLedger()
    ledger.record_event("TICK-103", "EVT_1", "state1", {"data": 1})
    e2 = ledger.record_event("TICK-103", "EVT_2", "state2", {"data": 2})

    # Tamper with prev_hash
    e2.prev_hash = "f" * 64

    is_valid, errors = ledger.verify_integrity("TICK-103")
    assert is_valid is False
    assert any("prev_hash" in err.lower() or "broken chain" in err.lower() for err in errors)


def test_tamper_detection_deleted_event() -> None:
    """Verifies tamper detection when an intermediate event is deleted from the ledger."""
    ledger = AuditLedger()
    ledger.record_event("TICK-104", "EVT_1", "state1", {})
    ledger.record_event("TICK-104", "EVT_2", "state2", {})
    ledger.record_event("TICK-104", "EVT_3", "state3", {})

    # Delete the middle event
    events = ledger.get_events("TICK-104")
    assert len(events) == 3
    # Remove event index 1
    ledger._events["TICK-104"].pop(1)

    is_valid, errors = ledger.verify_integrity("TICK-104")
    assert is_valid is False
    assert any("Sequence gap" in err or "broken" in err.lower() for err in errors)
