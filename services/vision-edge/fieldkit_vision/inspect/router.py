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
)
from fieldkit_vision.inspect.worker import InspectionWorker

router = APIRouter(prefix="/inspect", tags=["Defect Inspection"])

# Singleton worker instance for router
worker = InspectionWorker()


@router.get("/products", response_model=list[str])
async def list_products() -> list[str]:
    """List all supported product inspection configurations."""
    return worker.list_supported_products()


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
