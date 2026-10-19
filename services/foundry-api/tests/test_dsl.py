"""Unit tests for the Typed Query DSL Validator and Compiler."""

from __future__ import annotations

import pytest
from fieldkit_common.auth import Principal
from fieldkit_foundry.dsl import (
    DSLValidationError,
    QueryFilter,
    TypedQueryRequest,
    compile_dsl_query,
    validate_dsl_query,
)
from fieldkit_ontology.models import PurchaseOrder
from fieldkit_ontology.spec import load_ontology_spec

SPEC = load_ontology_spec()


def test_dsl_validates_unknown_object_type() -> None:
    req = TypedQueryRequest(type="NonExistentType", filters=[])
    with pytest.raises(DSLValidationError, match="Unknown ontology object type 'NonExistentType'"):
        validate_dsl_query(req, SPEC)


def test_dsl_validates_unknown_property() -> None:
    req = TypedQueryRequest(
        type="Supplier",
        filters=[QueryFilter(prop="non_existent_field", op="eq", value="foo")],
    )
    with pytest.raises(DSLValidationError, match="Unknown property 'non_existent_field'"):
        validate_dsl_query(req, SPEC)


def test_dsl_validates_invalid_operator() -> None:
    req = TypedQueryRequest(
        type="Supplier",
        filters=[QueryFilter(prop="name", op="regex_match", value=".*")],
    )
    with pytest.raises(DSLValidationError, match="Unsupported operator 'regex_match'"):
        validate_dsl_query(req, SPEC)


def test_dsl_validates_type_mismatches() -> None:
    # 1. Float field with string that cannot be parsed
    req_float = TypedQueryRequest(
        type="PurchaseOrder",
        filters=[QueryFilter(prop="total_amount", op="gt", value="not_a_number")],
    )
    with pytest.raises(DSLValidationError, match="cannot parse 'not_a_number' as float"):
        validate_dsl_query(req_float, SPEC)

    # 2. Float field with boolean
    req_bool = TypedQueryRequest(
        type="PurchaseOrder",
        filters=[QueryFilter(prop="total_amount", op="gt", value=True)],
    )
    with pytest.raises(DSLValidationError, match="boolean value provided for numeric property"):
        validate_dsl_query(req_bool, SPEC)

    # 3. Date field with malformed date
    req_date = TypedQueryRequest(
        type="PurchaseOrder",
        filters=[QueryFilter(prop="order_date", op="eq", value="2024-99-99")],
    )
    with pytest.raises(DSLValidationError, match="invalid ISO date"):
        validate_dsl_query(req_date, SPEC)


def test_dsl_validates_traversal_depth_limit() -> None:
    req = TypedQueryRequest(
        type="PurchaseOrder",
        traverse=["ordered_from", "supplies", "incident_on"],  # 3 steps > max 2
    )
    with pytest.raises(DSLValidationError, match="Traversal depth limit exceeded"):
        validate_dsl_query(req, SPEC)


def test_dsl_validates_unknown_link() -> None:
    req = TypedQueryRequest(
        type="PurchaseOrder",
        traverse=["unknown_link_relation"],
    )
    with pytest.raises(DSLValidationError, match="Unknown link 'unknown_link_relation'"):
        validate_dsl_query(req, SPEC)


def test_dsl_validates_disconnected_link() -> None:
    # 'delivered_to' links Shipment -> Plant, not connected to Supplier
    req = TypedQueryRequest(
        type="Supplier",
        traverse=["delivered_to"],
    )
    with pytest.raises(DSLValidationError, match="does not connect to/from object type 'Supplier'"):
        validate_dsl_query(req, SPEC)


def test_dsl_compile_query_compiles_safely() -> None:
    principal = Principal(sub="user1", username="lukas", roles=["support"], plant="DE-STR")
    req = TypedQueryRequest(
        type="PurchaseOrder",
        filters=[
            QueryFilter(prop="status", op="eq", value="OPEN"),
            QueryFilter(prop="total_amount", op="gte", value=5000.0),
        ],
        limit=25,
    )

    validate_dsl_query(req, SPEC)
    query = compile_dsl_query(req, PurchaseOrder, principal)
    sql_str = str(query)

    assert "purchase_orders.status = :status_1" in sql_str
    assert "purchase_orders.total_amount >= :total_amount_1" in sql_str
    assert "purchase_orders.plant = :plant_1" in sql_str  # RLS plant filter applied
