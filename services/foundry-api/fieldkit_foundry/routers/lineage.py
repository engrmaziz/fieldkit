"""Lineage Router serving property-level provenance and OpenLineage DAG transforms."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fieldkit_common.auth import Principal, current_principal
from fieldkit_ontology import models
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from fieldkit_foundry.db import apply_plant_rls, get_db_session, set_rls_context
from fieldkit_foundry.routers.objects import _resolve_model

router = APIRouter(prefix="/lineage", tags=["Lineage & Provenance"])


@router.get("/{object_type}/{object_id}/{property_name}")
async def get_property_lineage(
    object_type: str,
    object_id: uuid.UUID,
    property_name: str,
    session: AsyncSession = Depends(get_db_session),
    principal: Principal = Depends(current_principal()),
) -> dict[str, Any]:
    """Retrieves field-level provenance and associated OpenLineage transformation edges."""
    model = _resolve_model(object_type)
    await set_rls_context(session, principal)

    # 1. Verify object exists and principal has RLS authorization
    obj_q = select(model).where(model.id == object_id)
    obj_q = apply_plant_rls(obj_q, model, principal)
    obj = (await session.execute(obj_q)).scalar_one_or_none()
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{object_type} with ID '{object_id}' not found or access denied by RLS",
        )

    # 2. Fetch property provenance entries
    prov_q = (
        select(models.PropertyProvenance)
        .where(
            models.PropertyProvenance.object_id == object_id,
            models.PropertyProvenance.property_name == property_name,
        )
        .order_by(models.PropertyProvenance.recorded_at.desc())
    )
    prov_records = (await session.execute(prov_q)).scalars().all()

    history = [
        {
            "id": str(p.id),
            "value": p.value,
            "source_id": p.source_id,
            "source_row_ref": p.source_row_ref,
            "rule_applied": p.rule_applied,
            "run_id": p.run_id,
            "recorded_at": p.recorded_at.isoformat(),
        }
        for p in prov_records
    ]

    # 3. Fetch associated OpenLineage transform edges for the run_ids
    run_ids = list({p.run_id for p in prov_records})
    transforms = []
    if run_ids:
        edge_q = select(models.LineageEdge).where(models.LineageEdge.run_id.in_(run_ids))
        edge_records = (await session.execute(edge_q)).scalars().all()
        transforms = [
            {
                "id": str(e.id),
                "run_id": e.run_id,
                "input_dataset": e.input_dataset,
                "transform": e.transform,
                "output_dataset": e.output_dataset,
                "started_at": e.started_at.isoformat(),
                "ended_at": e.ended_at.isoformat(),
                "facets": e.facets,
            }
            for e in edge_records
        ]

    current_val = getattr(obj, property_name, None)

    return {
        "object_type": object_type,
        "object_id": str(object_id),
        "property_name": property_name,
        "current_value": str(current_val) if current_val is not None else None,
        "provenance_count": len(history),
        "history": history,
        "transforms": transforms,
    }
