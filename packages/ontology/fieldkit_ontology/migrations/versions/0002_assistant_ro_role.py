"""0002_assistant_ro_role

Revision ID: 0002_assistant_ro_role
Revises: 0001_initial_ontology
Create Date: 2026-10-19
"""

from __future__ import annotations

from alembic import op

revision = "0002_assistant_ro_role"
down_revision = "0001_initial_ontology"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create assistant_ro read-only role if it doesn't already exist
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'assistant_ro') THEN
                CREATE ROLE assistant_ro WITH LOGIN PASSWORD 'assistant_ro_local';
            END IF;
        END
        $$;
        """
    )
    # Grant USAGE on schema and SELECT on all ontology tables
    op.execute("GRANT USAGE ON SCHEMA public TO assistant_ro;")
    op.execute(
        """
        GRANT SELECT ON TABLE
            suppliers,
            parts,
            plants,
            purchase_orders,
            shipments,
            quality_incidents,
            certificates,
            property_provenance,
            lineage_edges
        TO assistant_ro;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        REVOKE SELECT ON TABLE
            suppliers,
            parts,
            plants,
            purchase_orders,
            shipments,
            quality_incidents,
            certificates,
            property_provenance,
            lineage_edges
        FROM assistant_ro;
        """
    )
    op.execute("REVOKE USAGE ON SCHEMA public FROM assistant_ro;")
    op.execute("DROP ROLE IF EXISTS assistant_ro;")
