"""Foundry API Objects and Typed Query Router with RLS Isolation, Search, Keyset Pagination, and Graph Traversal."""

from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fieldkit_common.auth import Principal, current_principal
from fieldkit_ontology import models
from fieldkit_ontology.spec import load_ontology_spec
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from fieldkit_foundry.db import apply_plant_rls, get_db_session, set_rls_context
from fieldkit_foundry.dsl import (
    DSLValidationError,
    QueryFilter,
    TypedQueryRequest,
    compile_dsl_query,
    validate_dsl_query,
)

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


def _encode_cursor(created_at: datetime, obj_id: uuid.UUID) -> str:
    raw = f"{created_at.isoformat()}|{obj_id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8")


def _decode_cursor(cursor_str: str) -> tuple[datetime, uuid.UUID]:
    try:
        decoded = base64.urlsafe_b64decode(cursor_str.encode("utf-8")).decode("utf-8")
        ts_str, id_str = decoded.split("|", 1)
        ts = datetime.fromisoformat(ts_str)
        uid = uuid.UUID(id_str)
        return ts, uid
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid pagination cursor '{cursor_str}'",
        ) from err


@router.get("/{object_type}")
async def list_objects(
    object_type: str,
    q: str | None = None,
    filters: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(current_principal()),
) -> dict[str, Any]:
    """Lists ontology objects with search, keyset pagination, and plant-scoped Row-Level Security."""
    model = _resolve_model(object_type)
    await set_rls_context(session, principal)

    query = select(model)
    query = apply_plant_rls(query, model, principal)

    # 1. Trigram / substring text search
    if q and q.strip():
        search_term = f"%{q.strip()}%"
        conditions = []
        if hasattr(model, "name"):
            conditions.append(model.name.ilike(search_term))
        if hasattr(model, "natural_key"):
            conditions.append(model.natural_key.ilike(search_term))
        if hasattr(model, "description"):
            conditions.append(model.description.ilike(search_term))
        if conditions:
            query = query.where(or_(*conditions))

    # 2. Filter parameter if provided as JSON string
    if filters:
        try:
            parsed_filters = json.loads(filters)
            if isinstance(parsed_filters, list):
                q_filters = [QueryFilter(**f) for f in parsed_filters]
                req = TypedQueryRequest(type=object_type, filters=q_filters, limit=limit)
                validate_dsl_query(req, ONTOLOGY_SPEC)
                query = compile_dsl_query(req, model, principal)
        except DSLValidationError as dsl_err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=dsl_err.message
            ) from dsl_err
        except Exception as err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid filters parameter: {err}"
            ) from err

    # 3. Keyset pagination using (created_at, id)
    if cursor:
        cursor_dt, cursor_id = _decode_cursor(cursor)
        query = query.where(
            or_(
                model.created_at < cursor_dt,
                (model.created_at == cursor_dt) & (model.id < cursor_id),
            )
        )

    query = query.order_by(model.created_at.desc(), model.id.desc()).limit(limit)

    result = await session.execute(query)
    records = result.scalars().all()

    items = [{c.name: getattr(r, c.name) for c in model.__table__.columns} for r in records]

    next_cursor = None
    if len(records) == limit:
        last_rec = records[-1]
        next_cursor = _encode_cursor(last_rec.created_at, last_rec.id)

    return {
        "type": object_type,
        "count": len(items),
        "items": items,
        "next_cursor": next_cursor,
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


@router.get("/{object_type}/{object_id}/neighbors")
async def get_object_neighbors(
    object_type: str,
    object_id: uuid.UUID,
    link: str | None = None,
    depth: int = Query(default=1, ge=1, le=2),
    session: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(current_principal()),
) -> dict[str, Any]:
    """Traverses typed ontology links up to depth 2 with RLS enforcement on neighbor objects."""
    if depth > 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Traversal depth limit exceeded (maximum allowed depth is 2)",
        )

    model = _resolve_model(object_type)
    await set_rls_context(session, principal)

    # Verify origin object exists and is accessible
    orig_q = select(model).where(model.id == object_id)
    orig_q = apply_plant_rls(orig_q, model, principal)
    orig_obj = (await session.execute(orig_q)).scalar_one_or_none()
    if not orig_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{object_type} with ID '{object_id}' not found or access denied by RLS",
        )

    neighbors: list[dict[str, Any]] = []

    # Helper to add neighbor if accessible under RLS
    async def _add_neighbors_for(
        target_model: Any,
        target_type: str,
        link_name: str,
        fk_col: str,
        val: Any,
        current_depth: int,
    ) -> list[Any]:
        if link and link != link_name:
            return []
        q = select(target_model).where(getattr(target_model, fk_col) == val)
        q = apply_plant_rls(q, target_model, principal)
        res = (await session.execute(q)).scalars().all()
        added_objs = []
        for item in res:
            item_dict = {c.name: getattr(item, c.name) for c in target_model.__table__.columns}
            neighbors.append(
                {
                    "link": link_name,
                    "target_type": target_type,
                    "depth": current_depth,
                    "object": item_dict,
                }
            )
            added_objs.append(item)
        return added_objs

    # Depth 1 traversal
    if model is models.Supplier:
        # ordered_from: PurchaseOrder -> Supplier
        await _add_neighbors_for(
            models.PurchaseOrder, "PurchaseOrder", "ordered_from", "supplier_id", object_id, 1
        )
        # certified_by: Certificate -> Supplier
        await _add_neighbors_for(
            models.Certificate, "Certificate", "certified_by", "supplier_id", object_id, 1
        )

    elif model is models.PurchaseOrder:
        # ordered_from: PurchaseOrder -> Supplier
        if orig_obj.supplier_id:
            await _add_neighbors_for(
                models.Supplier, "Supplier", "ordered_from", "id", orig_obj.supplier_id, 1
            )
        # delivered_to: Shipment -> PurchaseOrder
        await _add_neighbors_for(models.Shipment, "Shipment", "delivered_to", "po_id", object_id, 1)

    elif model is models.QualityIncident:
        # incident_on: QualityIncident -> Part
        if orig_obj.part_id:
            await _add_neighbors_for(models.Part, "Part", "incident_on", "id", orig_obj.part_id, 1)
        if orig_obj.supplier_id:
            await _add_neighbors_for(
                models.Supplier, "Supplier", "ordered_from", "id", orig_obj.supplier_id, 1
            )

    elif model is models.Shipment:
        # delivered_to: Shipment -> PurchaseOrder
        if orig_obj.po_id:
            pos = await _add_neighbors_for(
                models.PurchaseOrder, "PurchaseOrder", "delivered_to", "id", orig_obj.po_id, 1
            )
            # Depth 2: If depth == 2, traverse from PurchaseOrder to Supplier
            if depth >= 2:
                for po_item in pos:
                    if po_item.supplier_id:
                        await _add_neighbors_for(
                            models.Supplier,
                            "Supplier",
                            "ordered_from",
                            "id",
                            po_item.supplier_id,
                            2,
                        )

    return {
        "object_id": str(object_id),
        "object_type": object_type,
        "depth": depth,
        "count": len(neighbors),
        "neighbors": neighbors,
    }


@router.post("/query")
async def execute_typed_query(
    req: TypedQueryRequest,
    session: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(current_principal()),
) -> dict[str, Any]:
    """Compiles and executes a typed DSL query with strict semantic validation and RLS enforcement."""
    try:
        validate_dsl_query(req, ONTOLOGY_SPEC)
    except DSLValidationError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err.message) from err

    model = _resolve_model(req.type)
    await set_rls_context(session, principal)

    query = compile_dsl_query(req, model, principal)
    result = await session.execute(query)
    records = result.scalars().all()

    items = [{c.name: getattr(r, c.name) for c in model.__table__.columns} for r in records]
    return {
        "type": req.type,
        "count": len(items),
        "items": items,
    }
