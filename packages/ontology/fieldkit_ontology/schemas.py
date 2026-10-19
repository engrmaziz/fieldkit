"""Generated Pydantic v2 schemas from ontology.yaml. DO NOT EDIT DIRECTLY."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SupplierRead(BaseModel):
    """Read model for Supplier."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    natural_key: str
    plant: str | None = None
    row_hash: str
    created_run_id: str
    updated_run_id: str
    created_at: datetime
    updated_at: datetime
    supplier_code: str
    name: str
    street: str | None = None
    city: str | None = None
    postal_code: str | None = None
    country: str
    lei: str | None = None
    legal_form: str | None = None


class PartRead(BaseModel):
    """Read model for Part."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    natural_key: str
    plant: str | None = None
    row_hash: str
    created_run_id: str
    updated_run_id: str
    created_at: datetime
    updated_at: datetime
    part_number: str
    name: str
    category: str
    unit_of_measure: str
    unit_cost: float


class PlantRead(BaseModel):
    """Read model for Plant."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    natural_key: str
    plant: str | None = None
    row_hash: str
    created_run_id: str
    updated_run_id: str
    created_at: datetime
    updated_at: datetime
    plant_code: str
    name: str
    location: str
    country: str


class PurchaseOrderRead(BaseModel):
    """Read model for PurchaseOrder."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    natural_key: str
    plant: str | None = None
    row_hash: str
    created_run_id: str
    updated_run_id: str
    created_at: datetime
    updated_at: datetime
    po_number: str
    order_date: date
    total_amount: float
    currency: str
    status: str
    supplier_id: uuid.UUID | None = None


class ShipmentRead(BaseModel):
    """Read model for Shipment."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    natural_key: str
    plant: str | None = None
    row_hash: str
    created_run_id: str
    updated_run_id: str
    created_at: datetime
    updated_at: datetime
    shipment_number: str
    tracking_number: str | None = None
    delivery_date: date
    status: str
    po_id: uuid.UUID | None = None


class QualityIncidentRead(BaseModel):
    """Read model for QualityIncident."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    natural_key: str
    plant: str | None = None
    row_hash: str
    created_run_id: str
    updated_run_id: str
    created_at: datetime
    updated_at: datetime
    incident_number: str
    incident_date: date
    severity: str
    description: str
    resolution_status: str
    part_id: uuid.UUID | None = None
    supplier_id: uuid.UUID | None = None


class CertificateRead(BaseModel):
    """Read model for Certificate."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    natural_key: str
    plant: str | None = None
    row_hash: str
    created_run_id: str
    updated_run_id: str
    created_at: datetime
    updated_at: datetime
    certificate_number: str
    standard: str
    issuer: str
    valid_from: date
    valid_to: date
    supplier_id: uuid.UUID | None = None


class PropertyProvenanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    object_id: uuid.UUID
    object_type: str
    property_name: str
    value: str | None = None
    source_id: str
    source_row_ref: str
    run_id: str
    rule_applied: str
    recorded_at: datetime


class LineageEdgeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: str
    input_dataset: str
    transform: str
    output_dataset: str
    started_at: datetime
    ended_at: datetime
    facets: dict[str, Any] = Field(default_factory=dict)
