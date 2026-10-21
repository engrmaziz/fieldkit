"""Pydantic data schemas for industrial inspection requests, responses, and records."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class InspectionRequest(BaseModel):
    """Payload for submitting component image to inspection pipeline."""

    product_id: str = Field(..., description="Target product configuration identifier (e.g. metal_nut, steel_sheet)")
    part_id: str | None = Field(default=None, description="Optional factory serial/batch identifier")
    plant_id: str = Field(default="DE-HAM", description="Originating plant identifier")
    camera_id: str | None = Field(default=None, description="Optical inspection station camera ID")


class InspectionResponse(BaseModel):
    """Synchronous edge inspection inference response."""

    inspection_id: str = Field(default_factory=lambda: str(uuid4()))
    product_id: str
    part_id: str
    plant_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    disposition: str  # "pass", "reject", "review"
    disposition_reason: str
    anomaly_score: float
    defect_class: str
    defect_confidence: float
    is_audit_sample: bool = False
    heatmap_url: str | None = None
    latency_ms: float
    details: dict[str, Any] = Field(default_factory=dict)


class InspectionRecord(BaseModel):
    """Archival record stored in PostgreSQL / audit ledger for review and retraining."""

    inspection_id: str
    product_id: str
    part_id: str
    plant_id: str
    timestamp: datetime
    disposition: str
    disposition_reason: str
    anomaly_score: float
    defect_class: str
    defect_confidence: float
    is_audit_sample: bool
    heatmap_url: str | None = None
    image_storage_url: str | None = None
    latency_ms: float
    operator_label: str | None = None
    operator_notes: str | None = None
    reviewed_at: datetime | None = None
    reviewed_by: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class InspectionReviewUpdate(BaseModel):
    """Operator submission updating review queue disposition with human ground truth."""

    operator_label: str = Field(..., description="Operator verified label (e.g. good, crazing, scratch, reject)")
    operator_notes: str | None = Field(default=None, description="Notes on defect manifestation")
    reviewed_by: str = Field(default="operator", description="Operator user identifier")


class ReviewSubmission(BaseModel):
    """Review queue submission matching M5 specification."""

    inspection_id: str
    verdict: str = Field(..., description="Verdict: good or defect")
    defect_class: str | None = Field(default=None, description="Specific defect class if verdict is defect")
    polygon: list[list[float]] | None = Field(default=None, description="Optional bounding polygon coordinates")
    notes: str | None = Field(default=None, description="Operator notes")
    reviewed_by: str = Field(default="mehmet", description="Reviewer identifier")


class RetrainRequest(BaseModel):
    """Payload to trigger closed-loop retraining."""

    product_id: str
    candidate_version: str | None = None


class ModelPromotionRequest(BaseModel):
    """Payload to promote candidate model to production."""

    product_id: str
    version: str
    promoted_by: str = "mehmet"
    role: str = "quality"
    notes: str = "Passed shadow evaluation"


class ModelRollbackRequest(BaseModel):
    """Payload to roll back production model."""

    product_id: str
    target_version: str

