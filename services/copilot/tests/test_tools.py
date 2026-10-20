"""Unit and integration tests for copilot tool registry, execution, and retries."""

import asyncio
from typing import Any

import pytest
from fieldkit_copilot.tools.base import ToolExecutionError, ToolRegistry
from fieldkit_copilot.tools.registry import (
    EscalateResult,
    GetShipmentsResult,
    SearchKBResult,
    SendReplyResult,
    build_default_tool_registry,
)
from fieldkit_mock_erp.models import CreditResponse, Order, RMAResponse
from pydantic import BaseModel


@pytest.fixture
def registry() -> ToolRegistry:
    return build_default_tool_registry()


def test_registry_schema_export(registry: ToolRegistry) -> None:
    """Verifies that all 7 tools export schemas formatted for LLM ActionPlan prompts."""
    schemas = registry.export_schemas_for_planner()
    assert len(schemas) == 7

    tool_names = {s["name"] for s in schemas}
    expected_tools = {
        "lookup_order",
        "get_shipments",
        "search_kb",
        "create_rma",
        "issue_credit",
        "escalate",
        "send_reply",
    }
    assert tool_names == expected_tools

    # Check side effect flags
    side_effects = {s["name"]: s["side_effect"] for s in schemas}
    assert side_effects["lookup_order"] is False
    assert side_effects["get_shipments"] is False
    assert side_effects["search_kb"] is False
    assert side_effects["create_rma"] is True
    assert side_effects["issue_credit"] is True
    assert side_effects["escalate"] is False
    assert side_effects["send_reply"] is True


@pytest.mark.asyncio
async def test_read_only_tools_execution(registry: ToolRegistry) -> None:
    """Verifies lookup_order, get_shipments, and search_kb."""
    # 1. lookup_order
    order = await registry.execute("lookup_order", {"order_id": "PO-1001"}, "TCK-1", 0)
    assert isinstance(order, Order)
    assert order.order_id == "PO-1001"
    assert order.status == "delivered"

    # 2. get_shipments
    shps = await registry.execute("get_shipments", {"order_id": "PO-1001"}, "TCK-1", 1)
    assert isinstance(shps, GetShipmentsResult)
    assert len(shps.shipments) >= 1
    assert shps.shipments[0].tracking_number == "DHL-DE-994821"

    # 3. search_kb
    kb = await registry.execute("search_kb", {"query": "leakage valve HX-400"}, "TCK-1", 2)
    assert isinstance(kb, SearchKBResult)
    assert len(kb.articles) >= 1
    assert "HX-400" in kb.articles[0].title or "Seal" in kb.articles[0].title


@pytest.mark.asyncio
async def test_mutating_tools_execution_and_idempotency(registry: ToolRegistry) -> None:
    """Verifies create_rma and issue_credit execute and preserve idempotency."""
    # 1. create_rma
    rma_args = {
        "order_id": "PO-1001",
        "reason": "Severe leak at flange seal",
        "items": [{"part_id": "HX-400", "quantity": 1, "defect_description": "Crack"}],
    }
    rma_1 = await registry.execute("create_rma", rma_args, "TCK-7712", 0)
    assert isinstance(rma_1, RMAResponse)
    assert rma_1.approved is True
    assert "RMA-" in rma_1.rma_id

    # Idempotency replay with exact same ticket_id:action_index -> identical RMA
    rma_2 = await registry.execute("create_rma", rma_args, "TCK-7712", 0)
    assert rma_2.rma_id == rma_1.rma_id
    assert rma_2.created_at == rma_1.created_at

    # 2. issue_credit
    credit_args = {
        "order_id": "PO-1001",
        "amount_eur": 220.0,
        "reason": "Expedited freight delay compensation",
    }
    cred_1 = await registry.execute("issue_credit", credit_args, "TCK-7712", 1)
    assert isinstance(cred_1, CreditResponse)
    assert cred_1.amount_eur == 220.0

    # Idempotent replay
    cred_2 = await registry.execute("issue_credit", credit_args, "TCK-7712", 1)
    assert cred_2.credit_id == cred_1.credit_id


@pytest.mark.asyncio
async def test_escalate_and_send_reply(registry: ToolRegistry) -> None:
    """Verifies escalate and send_reply tools."""
    # escalate
    esc = await registry.execute(
        "escalate",
        {"ticket_id": "TCK-4001", "reason": "Severe hydraulic pressure drop on manufacturing line", "target_team": "quality"},
        "TCK-4001",
        0,
    )
    assert isinstance(esc, EscalateResult)
    assert esc.escalated is True
    assert esc.target_team == "quality"

    # send_reply
    reply = await registry.execute(
        "send_reply",
        {"ticket_id": "TCK-4001", "to_email": "purchasing@client.de", "subject": "Update on HX-400", "body": "We have dispatched a replacement."},
        "TCK-4001",
        1,
    )
    assert isinstance(reply, SendReplyResult)
    assert reply.sent is True
    assert reply.recipient == "purchasing@client.de"
    assert "MSG-" in reply.message_id


@pytest.mark.asyncio
async def test_tool_timeout_handling() -> None:
    """Verifies that a tool exceeding timeout raises ToolExecutionError."""
    reg = ToolRegistry()

    class SleepArgs(BaseModel):
        duration: float

    class SleepResult(BaseModel):
        slept: bool

    async def _slow_handler(args: dict[str, Any], _key: str) -> SleepResult:
        await asyncio.sleep(args["duration"])
        return SleepResult(slept=True)

    reg.register(
        name="slow_tool",
        description="Slow simulated operation",
        args_schema=SleepArgs,
        result_schema=SleepResult,
        side_effect=False,
        executor_func=_slow_handler,
        timeout_seconds=0.05,  # 50ms timeout
    )

    with pytest.raises(ToolExecutionError, match="timeout"):
        await reg.execute("slow_tool", {"duration": 0.20}, "TCK-TIMEOUT", 0, max_retries=1)


@pytest.mark.asyncio
async def test_transient_error_retry_resilience() -> None:
    """Verifies that transient errors (503) are retried and eventually succeed."""
    reg = ToolRegistry()
    attempts = 0

    class DummyArgs(BaseModel):
        val: str

    class DummyResult(BaseModel):
        ok: bool

    async def _flaky_handler(_args: dict[str, Any], _key: str) -> DummyResult:
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise RuntimeError("HTTP 503: Service Unavailable transient failure")
        return DummyResult(ok=True)

    reg.register(
        name="flaky_tool",
        description="Flaky operation simulating transient 503",
        args_schema=DummyArgs,
        result_schema=DummyResult,
        side_effect=True,
        executor_func=_flaky_handler,
        timeout_seconds=2.0,
    )

    result = await reg.execute("flaky_tool", {"val": "test"}, "TCK-RETRY", 0, max_retries=3)
    assert isinstance(result, DummyResult)
    assert result.ok is True
    assert attempts == 2
