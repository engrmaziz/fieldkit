"""Implementations of all 7 typed copilot tools for Halden Operations."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fieldkit_mock_erp.models import (
    CreditRequest,
    CreditResponse,
    Order,
    RMAItem,
    RMARequest,
    RMAResponse,
    Shipment,
)
from fieldkit_mock_erp.storage import storage as erp_storage
from pydantic import BaseModel, Field

from .base import ToolRegistry


# -----------------------------------------------------------------------------
# Tool 1: lookup_order
# -----------------------------------------------------------------------------
class LookupOrderArgs(BaseModel):
    """Input parameters for lookup_order."""

    order_id: str = Field(description="Customer purchase order ID, e.g. PO-1001")


# -----------------------------------------------------------------------------
# Tool 2: get_shipments
# -----------------------------------------------------------------------------
class GetShipmentsArgs(BaseModel):
    """Input parameters for get_shipments."""

    order_id: str = Field(description="Order ID to retrieve tracking shipments for")


class GetShipmentsResult(BaseModel):
    """Result returned by get_shipments."""

    order_id: str
    shipments: list[Shipment]


# -----------------------------------------------------------------------------
# Tool 3: search_kb
# -----------------------------------------------------------------------------
class SearchKBArgs(BaseModel):
    """Input parameters for search_kb."""

    query: str = Field(description="Technical search inquiry regarding parts or SOPs")
    top_k: int = Field(default=3, ge=1, le=10, description="Max articles to retrieve")


class KBArticle(BaseModel):
    """Retrieved knowledge base excerpt."""

    title: str
    content: str
    category: str


class SearchKBResult(BaseModel):
    """Result returned by search_kb."""

    query: str
    articles: list[KBArticle]


# -----------------------------------------------------------------------------
# Tool 4: create_rma
# -----------------------------------------------------------------------------
class CreateRMAArgs(BaseModel):
    """Input parameters for create_rma."""

    order_id: str = Field(description="Order ID associated with the defective part")
    reason: str = Field(description="Technical reason for the return authorization")
    items: list[RMAItem] = Field(description="List of parts and quantities to return")


# -----------------------------------------------------------------------------
# Tool 5: issue_credit
# -----------------------------------------------------------------------------
class IssueCreditArgs(BaseModel):
    """Input parameters for issue_credit."""

    order_id: str = Field(description="Order ID for which credit is issued")
    amount_eur: float = Field(gt=0.0, description="Credit amount in Euros (max €500.00 without executive approval)")
    reason: str = Field(description="Business justification for the refund/credit")


# -----------------------------------------------------------------------------
# Tool 6: escalate
# -----------------------------------------------------------------------------
class EscalateArgs(BaseModel):
    """Input parameters for escalate."""

    ticket_id: str = Field(description="Support ticket ID to escalate")
    reason: str = Field(description="Reason why automated copilot is escalating to human supervisor")
    target_team: str = Field(default="engineering", description="Target escalation team: engineering, quality, legal")


class EscalateResult(BaseModel):
    """Result returned by escalate."""

    ticket_id: str
    escalated: bool
    target_team: str
    assigned_lead: str
    escalated_at: str


# -----------------------------------------------------------------------------
# Tool 7: send_reply
# -----------------------------------------------------------------------------
class SendReplyArgs(BaseModel):
    """Input parameters for send_reply."""

    ticket_id: str = Field(description="Support ticket ID")
    to_email: str = Field(description="Recipient customer email address")
    subject: str = Field(description="Email subject line")
    body: str = Field(description="Sanitized email body text")


class SendReplyResult(BaseModel):
    """Result returned by send_reply."""

    sent: bool
    ticket_id: str
    message_id: str
    recipient: str
    sent_at: str


# =============================================================================
# Registry Factory
# =============================================================================
def build_default_tool_registry() -> ToolRegistry:
    """Build and register all 7 typed tools with production handlers."""
    registry = ToolRegistry()

    # 1. lookup_order (Read-only)
    async def _handle_lookup_order(args: dict[str, Any], _idemp_key: str) -> Order:
        order = erp_storage.get_order(args["order_id"])
        if not order:
            raise ValueError(f"Order '{args['order_id']}' not found in ERP system.")
        return order

    registry.register(
        name="lookup_order",
        description="Fetch customer order details including plant, status, total amount, and line items.",
        args_schema=LookupOrderArgs,
        result_schema=Order,
        side_effect=False,
        executor_func=_handle_lookup_order,
        required_role="support",
        timeout_seconds=5.0,
    )

    # 2. get_shipments (Read-only)
    async def _handle_get_shipments(args: dict[str, Any], _idemp_key: str) -> GetShipmentsResult:
        shipments = erp_storage.get_shipments(args["order_id"])
        return GetShipmentsResult(order_id=args["order_id"], shipments=shipments)

    registry.register(
        name="get_shipments",
        description="Retrieve carrier shipping tracking numbers, carrier names, and delivery status.",
        args_schema=GetShipmentsArgs,
        result_schema=GetShipmentsResult,
        side_effect=False,
        executor_func=_handle_get_shipments,
        required_role="support",
        timeout_seconds=5.0,
    )

    # 3. search_kb (Read-only)
    async def _handle_search_kb(args: dict[str, Any], _idemp_key: str) -> SearchKBResult:
        query_low = args["query"].lower()
        articles = [
            KBArticle(
                title="SOP-HAL-204: Hydraulic Seal Inspection Protocol",
                content="Inspect seal rings under 250 bar pressure. If leakage exceeds 2 drops/minute, authorize RMA immediately.",
                category="quality",
            )
        ]
        if "hx-400" in query_low or "leak" in query_low:
            articles.append(
                KBArticle(
                    title="Technical Advisory: HX-400 Valve Sealing Flange",
                    content="Certain batch lots of HX-400 valves exhibit seal deformation under high thermal stress.",
                    category="engineering",
                )
            )
        return SearchKBResult(query=args["query"], articles=articles[: args.get("top_k", 3)])

    registry.register(
        name="search_kb",
        description="Search Halden standard operating procedures, technical advisories, and warranty protocols.",
        args_schema=SearchKBArgs,
        result_schema=SearchKBResult,
        side_effect=False,
        executor_func=_handle_search_kb,
        required_role="support",
        timeout_seconds=5.0,
    )

    # 4. create_rma (Mutating Side-effect)
    async def _handle_create_rma(args: dict[str, Any], idemp_key: str) -> RMAResponse:
        rma_req = RMARequest(
            order_id=args["order_id"],
            reason=args["reason"],
            items=[RMAItem(**i) for i in args["items"]],
        )
        return erp_storage.create_rma(rma_req, idempotency_key=idemp_key)

    registry.register(
        name="create_rma",
        description="Authorize Return Merchandise Authorization (RMA) and generate prepaid return shipping label.",
        args_schema=CreateRMAArgs,
        result_schema=RMAResponse,
        side_effect=True,
        executor_func=_handle_create_rma,
        required_role="support",
        timeout_seconds=10.0,
    )

    # 5. issue_credit (Mutating Side-effect)
    async def _handle_issue_credit(args: dict[str, Any], idemp_key: str) -> CreditResponse:
        cred_req = CreditRequest(
            order_id=args["order_id"],
            amount_eur=float(args["amount_eur"]),
            reason=args["reason"],
        )
        return erp_storage.issue_credit(cred_req, idempotency_key=idemp_key)

    registry.register(
        name="issue_credit",
        description="Issue financial credit memo / refund to customer account (policy limit: <= €500.00).",
        args_schema=IssueCreditArgs,
        result_schema=CreditResponse,
        side_effect=True,
        executor_func=_handle_issue_credit,
        required_role="support",
        timeout_seconds=10.0,
    )

    # 6. escalate (Exempt from policy blocks)
    async def _handle_escalate(args: dict[str, Any], _idemp_key: str) -> EscalateResult:
        team = args.get("target_team", "engineering")
        lead = "lukas" if team == "support" else "mehmet"
        return EscalateResult(
            ticket_id=args["ticket_id"],
            escalated=True,
            target_team=team,
            assigned_lead=lead,
            escalated_at=datetime.now(UTC).isoformat(),
        )

    registry.register(
        name="escalate",
        description="Escalate ticket to human operations lead, quality manager, or engineering specialist.",
        args_schema=EscalateArgs,
        result_schema=EscalateResult,
        side_effect=False,
        executor_func=_handle_escalate,
        required_role="support",
        timeout_seconds=5.0,
    )

    # 7. send_reply (Mutating Side-effect)
    async def _handle_send_reply(args: dict[str, Any], _idemp_key: str) -> SendReplyResult:
        msg_id = f"MSG-{uuid.uuid4().hex[:12]}"
        return SendReplyResult(
            sent=True,
            ticket_id=args["ticket_id"],
            message_id=msg_id,
            recipient=args["to_email"],
            sent_at=datetime.now(UTC).isoformat(),
        )

    registry.register(
        name="send_reply",
        description="Send outbound email response to customer following human review and QA validation.",
        args_schema=SendReplyArgs,
        result_schema=SendReplyResult,
        side_effect=True,
        executor_func=_handle_send_reply,
        required_role="support",
        timeout_seconds=10.0,
    )

    return registry
