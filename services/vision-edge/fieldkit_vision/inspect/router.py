"""FastAPI router exposing industrial inspection endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)

from fieldkit_vision.inspect.models import (
    InspectionRecord,
    InspectionResponse,
    InspectionReviewUpdate,
    ModelPromotionRequest,
    ModelRollbackRequest,
    RetrainRequest,
    ReviewSubmission,
)
from fieldkit_vision.inspect.worker import InspectionWorker

router = APIRouter(prefix="/inspect", tags=["Defect Inspection"])

# Singleton worker instance for router
worker = InspectionWorker()


@router.get("/products", response_model=list[str])
async def list_products() -> list[str]:
    """List all supported product inspection configurations."""
    return worker.list_supported_products()


@router.get("/records", response_model=list[InspectionRecord])
async def get_inspection_records(
    product_id: Annotated[str | None, Query()] = None,
    disposition: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> list[InspectionRecord]:
    """Query recent component inspection records and audit logs."""
    return worker.get_records(product_id=product_id, disposition=disposition, limit=limit)


@router.get("/records/{inspection_id}", response_model=InspectionRecord)
async def get_single_record(inspection_id: str) -> InspectionRecord:
    """Retrieve full inspection record by UUID."""
    rec = worker.get_record(inspection_id)
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection record '{inspection_id}' not found",
        )
    return rec


@router.post("/records/{inspection_id}/review", response_model=InspectionRecord)
async def submit_operator_review(
    inspection_id: str,
    update: InspectionReviewUpdate,
) -> InspectionRecord:
    """Submit operator review decision for ambiguous inspection item."""
    rec = worker.update_record_review(inspection_id, update)
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection record '{inspection_id}' not found",
        )
    return rec


@router.get("/heatmap/{inspection_id}")
async def get_heatmap_image(inspection_id: str) -> Response:
    """Stream binary JPEG heatmap overlay for inspection item."""
    img_bytes = worker.get_heatmap_bytes(inspection_id)
    if not img_bytes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Heatmap for inspection '{inspection_id}' not found",
        )
    return Response(content=img_bytes, media_type="image/jpeg")


# --- M5 Review Queue, Shadow Mode, Retrain & Drift Endpoints ---


@router.get("/review-queue", response_model=list[InspectionRecord])
async def get_review_queue(
    product_id: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[InspectionRecord]:
    """Retrieve pending review queue items awaiting human audit."""
    records = worker.get_records(product_id=product_id, disposition="review", limit=limit)
    return [r for r in records if r.operator_label is None]


@router.post("/reviews", response_model=InspectionRecord)
async def submit_review(submission: ReviewSubmission) -> InspectionRecord:
    """Submit human reviewer decision, label, and optional polygon annotations."""
    label = submission.defect_class if submission.verdict == "defect" and submission.defect_class else submission.verdict
    update = InspectionReviewUpdate(
        operator_label=label,
        operator_notes=submission.notes,
        reviewed_by=submission.reviewed_by,
    )
    rec = worker.update_record_review(submission.inspection_id, update)
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection record '{submission.inspection_id}' not found",
        )
    return rec


@router.post("/retrain")
async def trigger_retrain(req: RetrainRequest) -> dict:
    """Trigger automated candidate retraining loop on reviewed dataset manifest."""
    try:
        res = worker.retrain_candidate(product_id=req.product_id)
        return {
            "status": "SUCCESS" if res.gate_passed else "GATE_FAILED",
            "candidate_version": res.candidate_version,
            "manifest_version": res.manifest_version,
            "gate_passed": res.gate_passed,
            "registered": res.registered,
            "candidate_metrics": res.candidate_metrics,
            "production_metrics": res.production_metrics,
            "gate_summary": res.gate_summary,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Retraining pipeline error: {e}",
        ) from e


@router.get("/shadow/report")
async def get_shadow_promotion_report(
    product_id: Annotated[str, Query()],
) -> dict:
    """Fetch comparative shadow mode promotion report between production and candidate."""
    rep = worker.get_shadow_report(product_id=product_id)
    return {
        "product_id": rep.product_id,
        "candidate_version": rep.candidate_version,
        "production_version": rep.production_version,
        "total_shadow_samples": rep.total_shadow_samples,
        "agreement_rate": rep.agreement_rate,
        "disagreement_count": rep.disagreement_count,
        "reviewed_sample_count": rep.reviewed_sample_count,
        "prod_escape_count": rep.prod_escape_count,
        "candidate_escape_count": rep.candidate_escape_count,
        "prod_p95_latency_ms": rep.prod_p95_latency_ms,
        "candidate_p95_latency_ms": rep.candidate_p95_latency_ms,
        "promotion_recommended": rep.promotion_recommended,
        "gate_checks": rep.gate_checks,
        "reasons": rep.reasons,
    }


@router.get("/shadow/records")
async def get_shadow_records(
    product_id: Annotated[str, Query()],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[dict]:
    """Retrieve paired production vs candidate shadow execution logs."""
    recs = worker.get_paired_shadow_records(product_id=product_id, limit=limit)
    return [r.to_dict() for r in recs]


@router.post("/models/promote")
async def promote_candidate_model(req: ModelPromotionRequest) -> dict:
    """Promote candidate model to production in local registry (requires quality role)."""
    if req.role != "quality":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Promotion requires quality reviewer authorization",
        )

    success = worker.promote_candidate(
        product_id=req.product_id,
        version=req.version,
        promoted_by=req.promoted_by,
        notes=req.notes,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to promote version '{req.version}' for product '{req.product_id}'",
        )
    return {
        "status": "PROMOTED",
        "product_id": req.product_id,
        "version": req.version,
        "promoted_by": req.promoted_by,
        "notes": req.notes,
    }


@router.post("/models/rollback")
async def rollback_production_model(req: ModelRollbackRequest) -> dict:
    """Instantly roll back active production model to specified historical version."""
    success = worker.rollback_model(
        product_id=req.product_id,
        target_version=req.target_version,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Rollback to version '{req.target_version}' failed for product '{req.product_id}'",
        )
    return {
        "status": "ROLLED_BACK",
        "product_id": req.product_id,
        "target_version": req.target_version,
    }


@router.get("/models")
async def list_registered_models(
    product_id: Annotated[str | None, Query()] = None,
) -> list[dict]:
    """List all registered candidate, production, and archived models."""
    models = worker.registry.list_models(product_id)
    return [
        {
            "model_name": m.model_name,
            "version": m.version,
            "stage": m.stage.value,
            "artifact_path": m.artifact_path,
            "metrics": m.metrics,
            "parameters": m.parameters,
            "created_at": m.created_at,
            "promoted_by": m.promoted_by,
            "promotion_notes": m.promotion_notes,
        }
        for m in models
    ]


@router.get("/drift")
async def get_distribution_drift(
    product_id: Annotated[str, Query()],
) -> dict:
    """Analyze score distribution drift against reference baseline using PSI."""
    res = worker.get_drift_analysis(product_id=product_id)
    return {
        "product_id": res.product_id,
        "psi": res.psi,
        "status": res.status,
        "reference_count": res.reference_count,
        "actual_count": res.actual_count,
        "drift_detected": res.drift_detected,
        "alert_message": res.alert_message,
        "evaluated_at": res.evaluated_at,
    }


@router.post(
    "/{product_id}",
    response_model=InspectionResponse,
    status_code=status.HTTP_200_OK,
)
async def inspect_component(
    product_id: str,
    file: Annotated[UploadFile, File(...)],
    part_id: Annotated[str | None, Form()] = None,
    plant_id: Annotated[str, Form()] = "DE-HAM",
) -> InspectionResponse:
    """Execute synchronous component defect inspection and return disposition."""
    try:
        contents = await file.read()
        return worker.inspect_image(
            product_id=product_id,
            image_bytes=contents,
            part_id=part_id,
            plant_id=plant_id,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Inspection failed: {e}",
        ) from e


