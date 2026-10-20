"""FastAPI REST service for Fieldkit Ops Copilot (P3).

Provides API endpoints for:
- Support ticket intake and state machine execution
- Human-in-the-loop approval, editing, and rejection of side-effect actions
- Cryptographically verified, hash-chained audit trails
- Health and readiness probes
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fieldkit_common.logging import get_logger
from pydantic import BaseModel, Field

from .audit import get_audit_ledger
from .graph import CopilotGraph, compile_copilot_graph

logger = get_logger("fieldkit.copilot.api")

app = FastAPI(
    title="Fieldkit Ops Copilot API",
    description="Multi-Agent Ops Copilot with Human-in-the-Loop & Hash-Chained Audit Ledger",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global compiled orchestrator
copilot_engine: CopilotGraph | None = None


def get_copilot_engine() -> CopilotGraph:
    """Return singleton CopilotGraph instance."""
    global copilot_engine
    if copilot_engine is None:
        copilot_engine = compile_copilot_graph()
    return copilot_engine


# -----------------------------------------------------------------------------
# Request & Response Schemas
# -----------------------------------------------------------------------------


class IngestTicketRequest(BaseModel):
    """Input payload to submit a customer support ticket."""

    ticket_id: str = Field(description="Unique ticket identifier (e.g. TICK-1001)")
    raw_text: str = Field(description="Original unmasked customer message")
    order_id: str | None = Field(default=None, description="Optional associated purchase order")
    internal_only: bool = Field(default=False, description="Whether this is an internal lookup")


class IngestTicketResponse(BaseModel):
    """Execution status returned after processing ticket up to pause or completion."""

    ticket_id: str
    status: str
    queue: str | None = None
    priority: str | None = None
    confidence: float | None = None
    awaiting_approval: bool = False
    action_plan: dict[str, Any] | None = None
    violations: list[dict[str, Any]] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)


class ApprovalDecisionRequest(BaseModel):
    """Operator decision to resolve pending action plan."""

    decision: str = Field(description="'approved', 'edited', or 'rejected'")
    feedback: str | None = Field(default=None, description="Optional operator comment or reason")
    edited_actions: list[dict[str, Any]] | None = Field(
        default=None, description="Edited tool actions if decision is 'edited'"
    )


class AuditTrailResponse(BaseModel):
    """Tamper-evident audit chain for a support ticket."""

    ticket_id: str
    is_valid: bool
    event_count: int
    tamper_errors: list[str] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# Health and Readiness Endpoints
# -----------------------------------------------------------------------------


@app.get("/healthz", tags=["Probes"])
async def healthz() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "healthy", "service": "copilot", "version": "0.1.0"}


@app.get("/readyz", tags=["Probes"])
async def readyz() -> dict[str, str]:
    """Readiness probe."""
    return {"status": "ready"}


# -----------------------------------------------------------------------------
# Copilot Operational Endpoints
# -----------------------------------------------------------------------------


@app.post(
    "/copilot/tickets/ingest",
    response_model=IngestTicketResponse,
    status_code=status.HTTP_200_OK,
    tags=["Copilot"],
)
async def ingest_ticket(req: IngestTicketRequest) -> IngestTicketResponse:
    """Ingest a customer support ticket and run state machine to completion or interrupt."""
    engine = get_copilot_engine()
    config = {"configurable": {"thread_id": req.ticket_id}}

    initial_state = {
        "ticket_id": req.ticket_id,
        "raw_text": req.raw_text,
        "order_id": req.order_id,
        "internal_only": req.internal_only,
        "replan_count": 0,
        "approval_status": "pending",
    }

    try:
        final_state = await engine.graph.ainvoke(initial_state, config=config)
    except Exception as exc:
        logger.error("copilot_state_machine_execution_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"State machine failed: {exc}",
        ) from exc

    # Inspect if graph paused before approval gate
    snapshot = engine.graph.get_state(config)
    is_awaiting = "human_approval_gate" in snapshot.next

    return IngestTicketResponse(
        ticket_id=req.ticket_id,
        status="awaiting_approval" if is_awaiting else final_state.get("status", "completed"),
        queue=final_state.get("queue"),
        priority=final_state.get("priority"),
        confidence=final_state.get("confidence"),
        awaiting_approval=is_awaiting,
        action_plan=final_state.get("action_plan"),
        violations=final_state.get("violations", []),
        tool_results=final_state.get("tool_results", []),
    )


@app.get(
    "/copilot/tickets/{ticket_id}",
    response_model=dict[str, Any],
    tags=["Copilot"],
)
async def get_ticket_state(ticket_id: str) -> dict[str, Any]:
    """Retrieve current state and checkpoint snapshot for a support ticket."""
    engine = get_copilot_engine()
    config = {"configurable": {"thread_id": ticket_id}}

    snapshot = engine.graph.get_state(config)
    if not snapshot or not snapshot.values:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active session found for ticket '{ticket_id}'.",
        )

    values = dict(snapshot.values)
    is_awaiting = "human_approval_gate" in snapshot.next
    return {
        "ticket_id": ticket_id,
        "next_nodes": snapshot.next,
        "awaiting_approval": is_awaiting,
        "state": values,
    }


@app.post(
    "/copilot/tickets/{ticket_id}/approve",
    response_model=IngestTicketResponse,
    tags=["Copilot"],
)
async def approve_ticket(
    ticket_id: str, req: ApprovalDecisionRequest
) -> IngestTicketResponse:
    """Submit human approval decision (approve, edit, or reject) to resume execution."""
    engine = get_copilot_engine()
    config = {"configurable": {"thread_id": ticket_id}}

    snapshot = engine.graph.get_state(config)
    if not snapshot or not snapshot.values:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active checkpoint found for ticket '{ticket_id}'.",
        )

    decision_norm = req.decision.lower().strip()
    if decision_norm not in ("approved", "edited", "rejected"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid decision '{req.decision}'. Must be 'approved', 'edited', or 'rejected'.",
        )

    state_update: dict[str, Any] = {
        "approval_status": decision_norm,
        "approval_feedback": req.feedback,
    }

    if decision_norm == "edited" and req.edited_actions:
        # Override plan with human-edited actions
        current_plan = dict(snapshot.values.get("action_plan", {}))
        current_plan["actions"] = req.edited_actions
        state_update["action_plan"] = current_plan

    engine.graph.update_state(config, state_update)

    try:
        final_state = await engine.graph.ainvoke(None, config=config)
    except Exception as exc:
        logger.error("copilot_resume_execution_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Resume failed: {exc}",
        ) from exc

    return IngestTicketResponse(
        ticket_id=ticket_id,
        status=final_state.get("status", "completed"),
        queue=final_state.get("queue"),
        priority=final_state.get("priority"),
        confidence=final_state.get("confidence"),
        awaiting_approval=False,
        action_plan=final_state.get("action_plan"),
        violations=final_state.get("violations", []),
        tool_results=final_state.get("tool_results", []),
    )


@app.get(
    "/copilot/tickets/{ticket_id}/audit",
    response_model=AuditTrailResponse,
    tags=["Copilot"],
)
async def get_audit_trail(ticket_id: str) -> AuditTrailResponse:
    """Retrieve cryptographically verified SHA-256 hash-chained audit ledger."""
    ledger = get_audit_ledger()
    events = ledger.get_events(ticket_id)

    if not events:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No audit events found for ticket '{ticket_id}'.",
        )

    is_valid, errors = ledger.verify_integrity(ticket_id)

    return AuditTrailResponse(
        ticket_id=ticket_id,
        is_valid=is_valid,
        event_count=len(events),
        tamper_errors=errors,
        events=[e.model_dump() for e in events],
    )
