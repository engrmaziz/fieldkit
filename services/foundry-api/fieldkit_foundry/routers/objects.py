"""Foundry API Objects and Typed Query Router with RLS Isolation."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fieldkit_common.auth import Principal, current_principal
from fieldkit_ontology import models
from fieldkit_ontology.spec import load_ontology_spec
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fieldkit_foundry.db import apply_plant_rls, get_db_session, set_rls_context

router = APIRouter(prefix="/objects", tags=["Ontology Objects"])

ONTOLOGY_SPEC = load_ontology_spec()

MODEL_MAP: dict[str, Any] = {
    "Supplier": models.Supplier,
    "suppliers": models.Supplier,
    "Part": models.Part,
    "parts": models.Part,
    "Plant": models.Plant,
    "plants": models.Plant,
    "PurchaseOrder": models.PurchaseOrder,
    "purchase_orders": models.PurchaseOrder,
    "Shipment": models.Shipment,
    "shipments": models.Shipment,
    "QualityIncident": models.QualityIncident,
    "quality_incidents": models.QualityIncident,
    "Certificate": models.Certificate,
    "certificates": models.Certificate,
}


def _resolve_model(type_name: str) -> Any:
    norm_type = type_name.strip()
    if norm_type in MODEL_MAP:
        return MODEL_MAP[norm_type]
    for k, v in MODEL_MAP.items():
        if k.lower() == norm_type.lower():
            return v
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Unknown ontology object type '{type_name}'",
    )


class QueryFilter(BaseModel):
    prop: str
    op: str  # eq, ne, gt, lt, gte, lte, contains
    value: Any


class TypedQueryRequest(BaseModel):
    type: str
    filters: list[QueryFilter] = []
    limit: int = 50


@router.get("/{object_type}")
async def list_objects(
    object_type: str,
    limit: int = Query(default=50, le=500),
    cursor: str | None = None,
    session: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(current_principal()),
) -> dict[str, Any]:
    """Lists ontology objects with plant-scoped Row-Level Security."""
    model = _resolve_model(object_type)
    await set_rls_context(session, principal)

    query = select(model)
    query = apply_plant_rls(query, model, principal)
    query = query.limit(limit)

    result = await session.execute(query)
    records = result.scalars().all()

    items = []
    for r in records:
        item_dict = {c.name: getattr(r, c.name) for c in model.__table__.columns}
        items.append(item_dict)

    return {
        "type": object_type,
        "count": len(items),
        "items": items,
    }


@router.get("/{object_type}/{object_id}")
async def get_object(
    object_type: str,
    object_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(current_principal()),
) -> dict[str, Any]:
    """Retrieves an ontology object by UUID along with property provenance."""
    model = _resolve_model(object_type)
    await set_rls_context(session, principal)

    query = select(model).where(model.id == object_id)
    query = apply_plant_rls(query, model, principal)

    result = await session.execute(query)
    obj = result.scalar_one_or_none()

    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{object_type} with ID '{object_id}' not found or access denied by RLS",
        )

    # Fetch provenance
    prov_query = select(models.PropertyProvenance).where(
        models.PropertyProvenance.object_id == object_id
    )
    prov_res = await session.execute(prov_query)
    provenance_records = prov_res.scalars().all()

    provenance_map = {
        p.property_name: {
            "value": p.value,
            "source_id": p.source_id,
            "source_row_ref": p.source_row_ref,
            "run_id": p.run_id,
            "rule": p.rule_applied,
            "recorded_at": p.recorded_at.isoformat(),
        }
        for p in provenance_records
    }

    item_dict = {c.name: getattr(obj, c.name) for c in model.__table__.columns}
    return {
        "object": item_dict,
        "provenance": provenance_map,
    }


@router.post("/query")
async def execute_typed_query(
    req: TypedQueryRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(current_principal()),
) -> dict[str, Any]:
    """Compiles and executes a typed DSL query with strict RLS enforcement."""
    model = _resolve_model(req.type)
    await set_rls_context(session, principal)

    query = select(model)
    query = apply_plant_rls(query, model, principal)

    for f in req.filters:
        if not hasattr(model, f.prop):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Field '{f.prop}' does not exist on type '{req.type}'",
            )
        col = getattr(model, f.prop)
        if f.op == "eq":
            query = query.where(col == f.value)
        elif f.op == "ne":
            query = query.where(col != f.value)
        elif f.op == "gt":
            query = query.where(col > f.value)
        elif f.op == "lt":
            query = query.where(col < f.value)
        elif f.op == "gte":
            query = query.where(col >= f.value)
        elif f.op == "lte":
            query = query.where(col <= f.value)
        elif f.op == "contains":
            query = query.where(col.ilike(f"%{f.value}%"))
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported operator '{f.op}'",
            )

    query = query.limit(min(req.limit, 500))
    result = await session.execute(query)
    records = result.scalars().all()

    items = [{c.name: getattr(r, c.name) for c in model.__table__.columns} for r in records]
    return {
        "type": req.type,
        "count": len(items),
        "items": items,
    }
