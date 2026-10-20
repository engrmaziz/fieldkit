"""Pydantic data models for Project 3 Ops Copilot."""

from __future__ import annotations

from typing import Any

from fieldkit_mock_erp.models import Customer, Order, Shipment
from pydantic import BaseModel, Field


class ActionCall(BaseModel):
    """Structured tool invocation proposed by the LLM action planner."""

    tool: str = Field(description="Name of the tool to execute")
    args: dict[str, Any] = Field(default_factory=dict, description="Arguments for the tool")
    rationale: str = Field(description="Operational rationale explaining why this tool is needed")


class ActionPlan(BaseModel):
    """Complete action plan containing tool invocations and customer reply draft."""

    actions: list[ActionCall] = Field(
        default_factory=list, description="Ordered sequence of tool actions"
    )
    reply_draft: str = Field(
        default="", description="Draft email response to send to customer upon human approval"
    )


class WorldState(BaseModel):
    """Aggregated operational world state against which plans and policies are evaluated."""

    ticket_id: str
    language: str = "de"
    customer: Customer | None = None
    order: Order | None = None
    shipments: list[Shipment] = Field(default_factory=list)
    kb_articles: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Violation(BaseModel):
    """Deterministic policy check failure."""

    action_index: int = Field(description="Zero-based index of the violating action in plan")
    rule: str = Field(description="Identifier of the violated policy rule")
    message: str = Field(description="Human-readable explanation of why the action violated policy")
    tool: str = Field(description="Name of the violating tool")
