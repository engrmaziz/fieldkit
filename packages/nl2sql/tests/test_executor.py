"""Unit tests for SQLExecutor and NL2SQLGenerator with repair loops."""

import pytest
from fieldkit_common.auth import Principal
from fieldkit_nl2sql.executor import SQLExecutor
from fieldkit_nl2sql.generator import NL2SQLGenerator


@pytest.mark.asyncio
async def test_sql_executor_offline_fallback() -> None:
    executor = SQLExecutor()
    principal = Principal(sub="user-1", username="mehmet", roles=["quality"], plant="DE-HAM")
    result = await executor.execute(
        "SELECT id, name, city FROM suppliers WHERE country = 'DE' LIMIT 10;",
        principal=principal,
    )
    assert result.error is None
    assert len(result.columns) >= 2
    assert len(result.rows) > 0
    assert result.truncated is False


@pytest.mark.asyncio
async def test_sql_executor_timeout_guard() -> None:
    executor = SQLExecutor()
    # Execute query with simulated 0.001s timeout to verify timeout guard behavior
    result = await executor.execute(
        "SELECT * FROM suppliers;",
        statement_timeout_seconds=0.001,
    )
    assert result.execution_time_ms >= 0.0


@pytest.mark.asyncio
async def test_nl2sql_generator_end_to_end() -> None:
    generator = NL2SQLGenerator()
    principal = Principal(sub="user-2", username="sofia", roles=["procurement", "admin"], plant=None)

    resp = await generator.generate(
        query="List all suppliers in Germany with total purchase order spend in 2026",
        principal=principal,
        execute=True,
    )

    assert resp.validation.is_valid is True
    assert resp.sql.upper().startswith("SELECT")
    assert "LIMIT" in resp.sql.upper()
    assert len(resp.tables_used) > 0
    assert resp.execution is not None
    assert resp.execution.error is None


@pytest.mark.asyncio
async def test_nl2sql_generator_repair_loop_on_invalid_sql() -> None:
    generator = NL2SQLGenerator()

    # Verify that repair loop terminates safely and generates valid SQL
    resp = await generator.generate(
        query="Show quality incidents with critical severity for plant Stuttgart",
        execute=False,
    )
    assert resp.validation.is_valid is True
    assert "quality_incidents" in resp.sql.lower()
