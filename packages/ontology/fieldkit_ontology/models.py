"""Generated SQLAlchemy 2 async models from ontology.yaml. DO NOT EDIT DIRECTLY."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Date, DateTime, Float, String, Text, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Supplier(Base):
    """Enterprise canonical supplier resolved from GLEIF, ERP vendors, and Excel planning"""

    __tablename__ = "suppliers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    natural_key: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    plant: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    row_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    updated_run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    supplier_code: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str] = mapped_column(String(255), nullable=False)
    lei: Mapped[str | None] = mapped_column(String(255), nullable=True)
    legal_form: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Part(Base):
    """Hydraulic machinery component part catalog"""

    __tablename__ = "parts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    natural_key: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    plant: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    row_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    updated_run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    part_number: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_of_measure: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_cost: Mapped[float] = mapped_column(Float, nullable=False)


class Plant(Base):
    """Halden Industrie manufacturing plant location"""

    __tablename__ = "plants"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    natural_key: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    plant: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    row_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    updated_run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    plant_code: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str] = mapped_column(String(255), nullable=False)


class PurchaseOrder(Base):
    """Procurement purchase order contract"""

    __tablename__ = "purchase_orders"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    natural_key: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    plant: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    row_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    updated_run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    po_number: Mapped[str] = mapped_column(String(255), nullable=False)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(255), nullable=False)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)


class Shipment(Base):
    """Physical goods delivery shipment to plant"""

    __tablename__ = "shipments"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    natural_key: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    plant: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    row_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    updated_run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    shipment_number: Mapped[str] = mapped_column(String(255), nullable=False)
    tracking_number: Mapped[str | None] = mapped_column(String(255), nullable=True)
    delivery_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(255), nullable=False)
    po_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)


class QualityIncident(Base):
    """Plant defect or inspection quality incident report"""

    __tablename__ = "quality_incidents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    natural_key: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    plant: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    row_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    updated_run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    incident_number: Mapped[str] = mapped_column(String(255), nullable=False)
    incident_date: Mapped[date] = mapped_column(Date, nullable=False)
    severity: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    resolution_status: Mapped[str] = mapped_column(String(255), nullable=False)
    part_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)


class Certificate(Base):
    """Vendor compliance or quality certification (e.g. ISO 9001)"""

    __tablename__ = "certificates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    natural_key: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    plant: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    row_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    updated_run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    certificate_number: Mapped[str] = mapped_column(String(255), nullable=False)
    standard: Mapped[str] = mapped_column(String(255), nullable=False)
    issuer: Mapped[str] = mapped_column(String(255), nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date] = mapped_column(Date, nullable=False)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)


class PropertyProvenance(Base):
    """Tracks field-level provenance according to OpenLineage standards."""

    __tablename__ = "property_provenance"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    object_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)
    object_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    property_name: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_row_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    run_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    rule_applied: Mapped[str] = mapped_column(String(64), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )


class LineageEdge(Base):
    """Records OpenLineage transform DAG edges across runs."""

    __tablename__ = "lineage_edges"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    input_dataset: Mapped[str] = mapped_column(String(255), nullable=False)
    transform: Mapped[str] = mapped_column(String(255), nullable=False)
    output_dataset: Mapped[str] = mapped_column(String(255), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    facets: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
