"""State definition for LangGraph Ops Copilot state machine."""

from __future__ import annotations

from typing import Any, TypedDict


class CopilotState(TypedDict, total=False):
    """Complete state dictionary propagated across LangGraph nodes."""

    ticket_id: str
    raw_text: str
    masked_text: str
    detected_pii: list[dict[str, Any]]
    language: str
    queue: str
    priority: str
    confidence: float
    needs_human_triage: bool
    internal_only: bool

    order_id: str | None
    customer_id: str | None
    world_state: dict[str, Any]

    action_plan: dict[str, Any]
    violations: list[dict[str, Any]]
    replan_count: int

    awaiting_approval: bool
    approval_status: str  # "pending", "approved", "edited", "rejected"
    approval_feedback: str | None

    tool_results: list[dict[str, Any]]
    reply_sent: bool
    status: str  # "triaged", "planned", "awaiting_approval", "executed", "escalated", "completed", "rejected"
    error: str | None
