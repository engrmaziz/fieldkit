"""0001_initial_ontology

Revision ID: 0001_initial_ontology
Revises: None
Create Date: 2026-10-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial_ontology"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Table: suppliers
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("natural_key", sa.String(255), unique=True, nullable=False),
        sa.Column("plant", sa.String(64), nullable=True),
        sa.Column("row_hash", sa.String(64), nullable=False),
        sa.Column("created_run_id", sa.String(128), nullable=False),
        sa.Column("updated_run_id", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("supplier_code", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("street", sa.String(255), nullable=True),
        sa.Column("city", sa.String(255), nullable=True),
        sa.Column("postal_code", sa.String(255), nullable=True),
        sa.Column("country", sa.String(255), nullable=False),
        sa.Column("lei", sa.String(255), nullable=True),
        sa.Column("legal_form", sa.String(255), nullable=True),
    )
    op.create_index("ix_suppliers_natural_key", "suppliers", ["natural_key"])
    op.create_index("ix_suppliers_plant", "suppliers", ["plant"])

    # Table: parts
    op.create_table(
        "parts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("natural_key", sa.String(255), unique=True, nullable=False),
        sa.Column("plant", sa.String(64), nullable=True),
        sa.Column("row_hash", sa.String(64), nullable=False),
        sa.Column("created_run_id", sa.String(128), nullable=False),
        sa.Column("updated_run_id", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("part_number", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(255), nullable=False),
        sa.Column("unit_of_measure", sa.String(255), nullable=False),
        sa.Column("unit_cost", sa.Float(), nullable=False),
    )
    op.create_index("ix_parts_natural_key", "parts", ["natural_key"])
    op.create_index("ix_parts_plant", "parts", ["plant"])

    # Table: plants
    op.create_table(
        "plants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("natural_key", sa.String(255), unique=True, nullable=False),
        sa.Column("plant", sa.String(64), nullable=True),
        sa.Column("row_hash", sa.String(64), nullable=False),
        sa.Column("created_run_id", sa.String(128), nullable=False),
        sa.Column("updated_run_id", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("plant_code", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("location", sa.String(255), nullable=False),
        sa.Column("country", sa.String(255), nullable=False),
    )
    op.create_index("ix_plants_natural_key", "plants", ["natural_key"])
    op.create_index("ix_plants_plant", "plants", ["plant"])
    # Enable RLS on plants
    op.execute("ALTER TABLE plants ENABLE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY plants_plant_isolation ON plants FOR ALL USING (
            plant IS NULL
            OR plant = current_setting('app.plant', true)
            OR current_setting('app.role', true) = 'admin'
        );
    """)

    # Table: purchase_orders
    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("natural_key", sa.String(255), unique=True, nullable=False),
        sa.Column("plant", sa.String(64), nullable=True),
        sa.Column("row_hash", sa.String(64), nullable=False),
        sa.Column("created_run_id", sa.String(128), nullable=False),
        sa.Column("updated_run_id", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("po_number", sa.String(255), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("total_amount", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(255), nullable=False),
        sa.Column("status", sa.String(255), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=True),
    )
    op.create_index("ix_purchase_orders_natural_key", "purchase_orders", ["natural_key"])
    op.create_index("ix_purchase_orders_plant", "purchase_orders", ["plant"])
    # Enable RLS on purchase_orders
    op.execute("ALTER TABLE purchase_orders ENABLE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY purchase_orders_plant_isolation ON purchase_orders FOR ALL USING (
            plant IS NULL
            OR plant = current_setting('app.plant', true)
            OR current_setting('app.role', true) = 'admin'
        );
    """)

    # Table: shipments
    op.create_table(
        "shipments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("natural_key", sa.String(255), unique=True, nullable=False),
        sa.Column("plant", sa.String(64), nullable=True),
        sa.Column("row_hash", sa.String(64), nullable=False),
        sa.Column("created_run_id", sa.String(128), nullable=False),
        sa.Column("updated_run_id", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("shipment_number", sa.String(255), nullable=False),
        sa.Column("tracking_number", sa.String(255), nullable=True),
        sa.Column("delivery_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(255), nullable=False),
        sa.Column("po_id", sa.Uuid(), nullable=True),
    )
    op.create_index("ix_shipments_natural_key", "shipments", ["natural_key"])
    op.create_index("ix_shipments_plant", "shipments", ["plant"])
    # Enable RLS on shipments
    op.execute("ALTER TABLE shipments ENABLE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY shipments_plant_isolation ON shipments FOR ALL USING (
            plant IS NULL
            OR plant = current_setting('app.plant', true)
            OR current_setting('app.role', true) = 'admin'
        );
    """)

    # Table: quality_incidents
    op.create_table(
        "quality_incidents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("natural_key", sa.String(255), unique=True, nullable=False),
        sa.Column("plant", sa.String(64), nullable=True),
        sa.Column("row_hash", sa.String(64), nullable=False),
        sa.Column("created_run_id", sa.String(128), nullable=False),
        sa.Column("updated_run_id", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("incident_number", sa.String(255), nullable=False),
        sa.Column("incident_date", sa.Date(), nullable=False),
        sa.Column("severity", sa.String(255), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("resolution_status", sa.String(255), nullable=False),
        sa.Column("part_id", sa.Uuid(), nullable=True),
        sa.Column("supplier_id", sa.Uuid(), nullable=True),
    )
    op.create_index("ix_quality_incidents_natural_key", "quality_incidents", ["natural_key"])
    op.create_index("ix_quality_incidents_plant", "quality_incidents", ["plant"])
    # Enable RLS on quality_incidents
    op.execute("ALTER TABLE quality_incidents ENABLE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY quality_incidents_plant_isolation ON quality_incidents FOR ALL USING (
            plant IS NULL
            OR plant = current_setting('app.plant', true)
            OR current_setting('app.role', true) = 'admin'
        );
    """)

    # Table: certificates
    op.create_table(
        "certificates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("natural_key", sa.String(255), unique=True, nullable=False),
        sa.Column("plant", sa.String(64), nullable=True),
        sa.Column("row_hash", sa.String(64), nullable=False),
        sa.Column("created_run_id", sa.String(128), nullable=False),
        sa.Column("updated_run_id", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("certificate_number", sa.String(255), nullable=False),
        sa.Column("standard", sa.String(255), nullable=False),
        sa.Column("issuer", sa.String(255), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=True),
    )
    op.create_index("ix_certificates_natural_key", "certificates", ["natural_key"])
    op.create_index("ix_certificates_plant", "certificates", ["plant"])

    # Table: property_provenance
    op.create_table(
        "property_provenance",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("object_id", sa.Uuid(), nullable=False),
        sa.Column("object_type", sa.String(64), nullable=False),
        sa.Column("property_name", sa.String(64), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("source_id", sa.String(128), nullable=False),
        sa.Column("source_row_ref", sa.String(255), nullable=False),
        sa.Column("run_id", sa.String(128), nullable=False),
        sa.Column("rule_applied", sa.String(64), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_provenance_object_id", "property_provenance", ["object_id"])
    op.create_index("ix_provenance_run_id", "property_provenance", ["run_id"])

    # Table: lineage_edges
    op.create_table(
        "lineage_edges",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.String(128), nullable=False),
        sa.Column("input_dataset", sa.String(255), nullable=False),
        sa.Column("transform", sa.String(255), nullable=False),
        sa.Column("output_dataset", sa.String(255), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("facets", sa.JSON(), nullable=False),
    )
    op.create_index("ix_lineage_run_id", "lineage_edges", ["run_id"])


def downgrade() -> None:
    op.drop_table("certificates")
    op.drop_table("quality_incidents")
    op.drop_table("shipments")
    op.drop_table("purchase_orders")
    op.drop_table("plants")
    op.drop_table("parts")
    op.drop_table("suppliers")
    op.drop_table("property_provenance")
    op.drop_table("lineage_edges")
