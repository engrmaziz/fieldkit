"""Unit and integration tests for LangGraph Ops Copilot state machine."""

import pytest
from fieldkit_copilot.audit import AuditLedger
from fieldkit_copilot.graph import compile_copilot_graph
from langgraph.checkpoint.memory import MemorySaver


@pytest.mark.asyncio
async def test_read_only_ticket_executes_autonomously() -> None:
    """Verifies that inquiry tickets without side effects complete autonomously without pausing."""
    ledger = AuditLedger()
    saver = MemorySaver()
    copilot = compile_copilot_graph(checkpointer=saver, audit_ledger=ledger)

    config = {"configurable": {"thread_id": "TICK-READ-ONLY-01"}}
    initial_state = {
        "ticket_id": "TICK-READ-ONLY-01",
        "raw_text": "Wo finde ich das Datenblatt für Ventil HX-400?",
        "internal_only": True,
        "replan_count": 0,
        "approval_status": "pending",
    }

    # Execute graph
    final_state = await copilot.graph.ainvoke(initial_state, config=config)

    assert final_state["status"] == "completed"
    assert final_state["masked_text"] is not None
    assert final_state["world_state"] is not None
    assert final_state["action_plan"] is not None
    assert len(final_state["tool_results"]) > 0

    # Verify audit chain integrity
    is_valid, errors = ledger.verify_integrity("TICK-READ-ONLY-01")
    assert is_valid is True
    assert len(errors) == 0


@pytest.mark.asyncio
async def test_side_effect_ticket_interrupts_at_approval_gate() -> None:
    """Verifies that tickets with side effects (e.g. RMA, Credit) interrupt at the approval gate."""
    ledger = AuditLedger()
    saver = MemorySaver()
    copilot = compile_copilot_graph(checkpointer=saver, audit_ledger=ledger)

    config = {"configurable": {"thread_id": "TICK-RMA-01"}}
    initial_state = {
        "ticket_id": "TICK-RMA-01",
        "raw_text": "Der Zylinder zu Bestellung PO-1001 leckt stark. Wir bitten um Rücksendung und RMA.",
        "replan_count": 0,
        "approval_status": "pending",
    }

    # Run up to interrupt
    await copilot.graph.ainvoke(initial_state, config=config)

    # Next state should be interrupted before human_approval_gate
    snapshot = copilot.graph.get_state(config)
    assert "human_approval_gate" in snapshot.next

    # Resume with approval
    resume_update = {"approval_status": "approved"}
    copilot.graph.update_state(config, resume_update)

    final_state = await copilot.graph.ainvoke(None, config=config)
    assert final_state["status"] == "completed"
    assert any(res["tool"] == "create_rma" for res in final_state["tool_results"])

    # Verify cryptographic audit ledger
    is_valid, errors = ledger.verify_integrity("TICK-RMA-01")
    assert is_valid is True
    assert len(errors) == 0


@pytest.mark.asyncio
async def test_human_rejection_prevents_side_effects() -> None:
    """Verifies that an operator rejection terminates the flow without executing side effects."""
    ledger = AuditLedger()
    saver = MemorySaver()
    copilot = compile_copilot_graph(checkpointer=saver, audit_ledger=ledger)

    config = {"configurable": {"thread_id": "TICK-RMA-REJECT"}}
    initial_state = {
        "ticket_id": "TICK-RMA-REJECT",
        "raw_text": "Wir möchten PO-1001 zurücksenden.",
        "replan_count": 0,
        "approval_status": "pending",
    }

    # Run up to interrupt
    await copilot.graph.ainvoke(initial_state, config=config)

    # Resume with rejection and feedback
    copilot.graph.update_state(
        config,
        {
            "approval_status": "rejected",
            "approval_feedback": "Customer damaged item during mounting.",
        },
    )

    final_state = await copilot.graph.ainvoke(None, config=config)
    assert final_state["status"] == "rejected"
    assert "tool_results" not in final_state or len(final_state.get("tool_results", [])) == 0

    # Verify audit ledger recorded rejection
    events = ledger.get_events("TICK-RMA-REJECT")
    assert any(e.event_type == "PLAN_REJECTED" for e in events)
    is_valid, errors = ledger.verify_integrity("TICK-RMA-REJECT")
    assert is_valid is True


@pytest.mark.asyncio
async def test_legal_hold_triggers_replan_and_escalation() -> None:
    """Verifies that legal hold violation triggers the replan loop and self-heals by escalating."""
    ledger = AuditLedger()
    saver = MemorySaver()
    copilot = compile_copilot_graph(checkpointer=saver, audit_ledger=ledger)

    config = {"configurable": {"thread_id": "TICK-LEGAL-HOLD"}}
    initial_state = {
        "ticket_id": "TICK-LEGAL-HOLD",
        "raw_text": "Der Zylinder zu Bestellung PO-1004 leckt. Bitte um Rücksendung und RMA.",
        "order_id": "PO-1004",  # Order for CUST-003 with legal_hold=True
        "replan_count": 0,
        "approval_status": "pending",
    }

    final_state = await copilot.graph.ainvoke(initial_state, config=config)

    # Replan should have triggered and self-healed into escalate
    assert final_state["replan_count"] >= 1
    actions = final_state["action_plan"]["actions"]
    assert any(a["tool"] == "escalate" for a in actions)

    # Verify audit chain records REPLAN_TRIGGERED
    events = ledger.get_events("TICK-LEGAL-HOLD")
    assert any(e.event_type == "REPLAN_TRIGGERED" for e in events)
    is_valid, errors = ledger.verify_integrity("TICK-LEGAL-HOLD")
    assert is_valid is True
    assert len(errors) == 0
