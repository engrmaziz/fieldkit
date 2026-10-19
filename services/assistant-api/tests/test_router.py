"""Unit tests for Hybrid Query Router."""

import pytest
from fieldkit_assistant.router import HybridRouter


@pytest.mark.asyncio
async def test_router_sql_rules() -> None:
    router = HybridRouter()

    decision = await router.route("How many purchase orders were placed in Q3 2026?")
    assert decision.route == "sql"
    assert decision.confidence >= 0.85
    assert decision.method == "rule"

    decision2 = await router.route("Top 5 suppliers by late deliveries to Hamburg")
    assert decision2.route == "sql"
    assert decision2.confidence >= 0.85

    decision3 = await router.route("What is the average unit cost of hydraulic valves?")
    assert decision3.route == "sql"


@pytest.mark.asyncio
async def test_router_rag_rules() -> None:
    router = HybridRouter()

    decision = await router.route(
        "What does the EU Machinery Regulation (2023/1230) mandate regarding emergency shut-off valves?"
    )
    assert decision.route == "rag"
    assert decision.confidence >= 0.85
    assert decision.method == "rule"

    decision2 = await router.route("What is the quarantine procedure under Halden SOP-ENG-014?")
    assert decision2.route == "rag"
    assert decision2.confidence >= 0.85

    decision3 = await router.route("According to OSHA, what are lockout tagout rules for presses?")
    assert decision3.route == "rag"


@pytest.mark.asyncio
async def test_router_both_rules() -> None:
    router = HybridRouter()

    decision = await router.route(
        "What is our defect rate on hydraulic valves and what does our SOP require for defective lots?"
    )
    assert decision.route == "both"
    assert decision.confidence >= 0.85

    decision2 = await router.route(
        "How many safety incidents occurred on presses and what does OSHA mandate for press guards?"
    )
    assert decision2.route == "both"


@pytest.mark.asyncio
async def test_router_empty_and_fallback() -> None:
    router = HybridRouter()

    decision = await router.route("   ")
    assert decision.route == "rag"
    assert decision.method == "default"

    # Query with no rules matching falls back to LLM/offline heuristic
    decision2 = await router.route("Tell me something general about the plant atmosphere")
    assert decision2.route in ["rag", "sql", "both"]
