"""Unit tests for NL2SQL schema linker and few-shot example selector."""

import pytest
from fieldkit_nl2sql.linker import FewShotSelector, SchemaLinker


@pytest.mark.asyncio
async def test_schema_linker_retrieves_relevant_tables_and_joins() -> None:
    linker = SchemaLinker()
    linked = await linker.link_schema("What are the total purchase orders placed with suppliers in Hamburg?", top_k=8)

    assert len(linked.top_columns) <= 8
    assert "suppliers" in linked.tables
    assert "purchase_orders" in linked.tables
    assert "CREATE TABLE suppliers" in linked.ddl
    assert "CREATE TABLE purchase_orders" in linked.ddl
    assert any("purchase_orders.supplier_id = suppliers.id" in jp for jp in linked.join_paths)


@pytest.mark.asyncio
async def test_schema_linker_quality_incidents() -> None:
    linker = SchemaLinker()
    linked = await linker.link_schema("Show parts with critical quality defect incidents in plant Stuttgart", top_k=8)

    assert "quality_incidents" in linked.tables
    assert "parts" in linked.tables
    assert "CREATE TABLE quality_incidents" in linked.ddl
    assert any("quality_incidents.part_id = parts.id" in jp for jp in linked.join_paths)


@pytest.mark.asyncio
async def test_few_shot_selector_loads_40_examples_and_retrieves_top_3() -> None:
    selector = FewShotSelector()
    await selector.initialize()

    # Assert exactly 40 verified gold queries loaded
    assert len(selector._examples) == 40

    # Retrieve nearest examples for a late delivery question
    examples = await selector.select_examples("Which suppliers had the highest late shipments to Hamburg?", k=3)
    assert len(examples) == 3
    # Top example should be late shipment or supplier delivery related
    example_ids = [ex.id for ex in examples]
    assert any(eid in ("sql-003", "sql-021", "sql-028") for eid in example_ids)
    assert all(ex.sql.startswith("SELECT") for ex in examples)


@pytest.mark.asyncio
async def test_few_shot_selector_quality_queries() -> None:
    selector = FewShotSelector()
    examples = await selector.select_examples("Which parts have critical defect severity?", k=3)
    assert len(examples) == 3
    example_ids = [ex.id for ex in examples]
    assert any(eid in ("sql-032", "sql-033", "sql-036", "sql-037") for eid in example_ids)
