"""Typed Query DSL Compiler and Validator for Fieldkit Ontology."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from fieldkit_common.auth import Principal
from fieldkit_ontology.spec import OntologySpec
from pydantic import BaseModel, Field
from sqlalchemy import Select, select

from fieldkit_foundry.db import apply_plant_rls

ALLOWED_OPERATORS = {"eq", "ne", "gt", "gte", "lt", "lte", "contains", "in"}


class DSLValidationError(Exception):
    """Raised when a typed query DSL request fails semantic validation."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class QueryFilter(BaseModel):
    prop: str
    op: str  # eq, ne, gt, gte, lt, lte, contains, in
    value: Any


class TypedQueryRequest(BaseModel):
    type: str
    filters: list[QueryFilter] = Field(default_factory=list)
    traverse: list[str] = Field(default_factory=list)
    limit: int = Field(default=50, ge=1, le=500)


def validate_filter_value(prop_type: str, value: Any, prop_name: str) -> None:
    """Validates that filter value is semantically compatible with ontology property type."""
    if value is None:
        return

    if prop_type in ("float", "integer"):
        if isinstance(value, bool):
            raise DSLValidationError(
                f"Type mismatch: boolean value provided for numeric property '{prop_name}'"
            )
        try:
            if prop_type == "float":
                float(value)
            else:
                int(value)
        except (ValueError, TypeError) as err:
            raise DSLValidationError(
                f"Type mismatch: cannot parse '{value}' as {prop_type} for property '{prop_name}'"
            ) from err

    elif prop_type == "date":
        if isinstance(value, (date, datetime)):
            return
        if not isinstance(value, str):
            raise DSLValidationError(
                f"Type mismatch: expected date string for property '{prop_name}'"
            )
        try:
            date.fromisoformat(value[:10])
        except ValueError as err:
            raise DSLValidationError(
                f"Type mismatch: invalid ISO date '{value}' for property '{prop_name}'"
            ) from err

    elif prop_type == "uuid":
        if isinstance(value, uuid.UUID):
            return
        try:
            uuid.UUID(str(value))
        except ValueError as err:
            raise DSLValidationError(
                f"Type mismatch: invalid UUID '{value}' for property '{prop_name}'"
            ) from err


def validate_dsl_query(req: TypedQueryRequest, spec: OntologySpec) -> None:
    """Validates request against ontology.yaml specification.

    Rejects unknown properties, unknown links, type mismatches, and depth > 2.
    """
    # 1. Validate object type
    if req.type not in spec.objects:
        raise DSLValidationError(f"Unknown ontology object type '{req.type}'")

    obj_spec = spec.objects[req.type]
    valid_props = set(obj_spec.properties.keys()) | {
        "id",
        "natural_key",
        "plant",
        "created_at",
        "updated_at",
        "row_hash",
        "created_run_id",
        "updated_run_id",
    }

    # 2. Validate filters
    for f in req.filters:
        if f.prop not in valid_props:
            raise DSLValidationError(
                f"Unknown property '{f.prop}' on ontology object type '{req.type}'"
            )

        if f.op not in ALLOWED_OPERATORS:
            raise DSLValidationError(
                f"Unsupported operator '{f.op}'. Allowed operators: {sorted(ALLOWED_OPERATORS)}"
            )

        prop_type = (
            obj_spec.properties.get(f.prop, {}).type if f.prop in obj_spec.properties else "string"
        )
        if f.op == "in":
            if not isinstance(f.value, list):
                raise DSLValidationError(
                    f"Operator 'in' requires a list value for property '{f.prop}'"
                )
            for item in f.value:
                validate_filter_value(prop_type, item, f.prop)
        else:
            validate_filter_value(prop_type, f.value, f.prop)

    # 3. Validate traversal depth limit
    if len(req.traverse) > 2:
        raise DSLValidationError(
            f"Traversal depth limit exceeded: requested {len(req.traverse)} steps, maximum allowed is 2"
        )

    # 4. Validate traversal links
    curr_type = req.type
    for link_name in req.traverse:
        if link_name not in spec.links:
            raise DSLValidationError(f"Unknown link '{link_name}'")

        link_spec = spec.links[link_name]
        # Link must connect to or from curr_type
        if curr_type not in (link_spec.from_object, link_spec.to_object):
            raise DSLValidationError(
                f"Link '{link_name}' does not connect to/from object type '{curr_type}'"
            )
        # Advance current type
        curr_type = (
            link_spec.to_object if curr_type == link_spec.from_object else link_spec.from_object
        )


def compile_dsl_query(
    req: TypedQueryRequest,
    model: Any,
    principal: Principal,
) -> Select[Any]:
    """Compiles validated TypedQueryRequest into a safe SQLAlchemy Select query."""
    query = select(model)
    query = apply_plant_rls(query, model, principal)

    for f in req.filters:
        if not hasattr(model, f.prop):
            continue
        col = getattr(model, f.prop)
        val = f.value

        # Normalize date strings if needed
        if (
            hasattr(col.type, "python_type")
            and col.type.python_type is date
            and isinstance(val, str)
        ):
            val = date.fromisoformat(val[:10])

        if f.op == "eq":
            query = query.where(col == val)
        elif f.op == "ne":
            query = query.where(col != val)
        elif f.op == "gt":
            query = query.where(col > val)
        elif f.op == "gte":
            query = query.where(col >= val)
        elif f.op == "lt":
            query = query.where(col < val)
        elif f.op == "lte":
            query = query.where(col <= val)
        elif f.op == "contains":
            query = query.where(col.ilike(f"%{val}%"))
        elif f.op == "in":
            query = query.where(col.in_(val))

    query = query.limit(req.limit)
    return query
