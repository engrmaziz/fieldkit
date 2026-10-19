"""Deterministic code generator compiling ontology.yaml into SQLAlchemy 2, Pydantic, and Alembic."""

from __future__ import annotations

from pathlib import Path

from fieldkit_ontology.spec import OntologySpec, load_ontology_spec

TYPE_MAPPING_SA = {
    "string": "String(255)",
    "text": "Text",
    "float": "Float",
    "integer": "Integer",
    "date": "Date",
    "uuid": "Uuid",
    "boolean": "Boolean",
}

TYPE_MAPPING_PYDANTIC = {
    "string": "str",
    "text": "str",
    "float": "float",
    "integer": "int",
    "date": "date",
    "uuid": "uuid.UUID",
    "boolean": "bool",
}

TYPE_MAPPING_ALEMBIC = {
    "string": "sa.String(255)",
    "text": "sa.Text()",
    "float": "sa.Float()",
    "integer": "sa.Integer()",
    "date": "sa.Date()",
    "uuid": "sa.Uuid()",
    "boolean": "sa.Boolean()",
}


def generate_sqlalchemy_models(spec: OntologySpec) -> str:
    lines = [
        '"""Generated SQLAlchemy 2 async models from ontology.yaml. DO NOT EDIT DIRECTLY."""',
        "",
        "from __future__ import annotations",
        "",
        "import uuid",
        "from datetime import date, datetime",
        "from typing import Any",
        "",
        "from sqlalchemy import JSON, Date, DateTime, Float, String, Text, Uuid",
        "from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column",
        "",
        "",
        "class Base(DeclarativeBase):",
        "    pass",
        "",
    ]

    # Generate each object model
    for name, obj in spec.objects.items():
        lines.append(f"class {name}(Base):")
        lines.append(f'    """{obj.description}"""')
        lines.append(f'    __tablename__ = "{obj.table_name}"')
        lines.append("")
        # Standard common base columns
        lines.append(
            "    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)"
        )
        lines.append(
            "    natural_key: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)"
        )
        lines.append(
            "    plant: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)"
        )
        lines.append("    row_hash: Mapped[str] = mapped_column(String(64), nullable=False)")
        lines.append("    created_run_id: Mapped[str] = mapped_column(String(128), nullable=False)")
        lines.append("    updated_run_id: Mapped[str] = mapped_column(String(128), nullable=False)")
        lines.append(
            "    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)"
        )
        lines.append(
            "    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)"
        )

        # Custom properties
        for prop_name, prop in obj.properties.items():
            if prop_name in ("id", "natural_key", "plant"):
                continue
            sa_type = TYPE_MAPPING_SA.get(prop.type, "String(255)")
            nullable = not prop.required
            type_hint = TYPE_MAPPING_PYDANTIC.get(prop.type, "str")
            if nullable:
                lines.append(
                    f"    {prop_name}: Mapped[{type_hint} | None] = mapped_column({sa_type}, nullable=True)"
                )
            else:
                lines.append(
                    f"    {prop_name}: Mapped[{type_hint}] = mapped_column({sa_type}, nullable=False)"
                )

        lines.append("")
        lines.append("")

    # PropertyProvenance table
    lines.extend(
        [
            "class PropertyProvenance(Base):",
            '    """Tracks field-level provenance according to OpenLineage standards."""',
            '    __tablename__ = "property_provenance"',
            "",
            "    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)",
            "    object_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)",
            "    object_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)",
            "    property_name: Mapped[str] = mapped_column(String(64), nullable=False)",
            "    value: Mapped[str | None] = mapped_column(Text, nullable=True)",
            "    source_id: Mapped[str] = mapped_column(String(128), nullable=False)",
            "    source_row_ref: Mapped[str] = mapped_column(String(255), nullable=False)",
            "    run_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)",
            "    rule_applied: Mapped[str] = mapped_column(String(64), nullable=False)",
            "    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)",
            "",
            "",
            "class LineageEdge(Base):",
            '    """Records OpenLineage transform DAG edges across runs."""',
            '    __tablename__ = "lineage_edges"',
            "",
            "    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)",
            "    run_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)",
            "    input_dataset: Mapped[str] = mapped_column(String(255), nullable=False)",
            "    transform: Mapped[str] = mapped_column(String(255), nullable=False)",
            "    output_dataset: Mapped[str] = mapped_column(String(255), nullable=False)",
            "    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)",
            "    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)",
            "    facets: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)",
            "",
        ]
    )

    return "\n".join(lines) + "\n"


def generate_pydantic_schemas(spec: OntologySpec) -> str:
    lines = [
        '"""Generated Pydantic v2 schemas from ontology.yaml. DO NOT EDIT DIRECTLY."""',
        "",
        "from __future__ import annotations",
        "",
        "import uuid",
        "from datetime import date, datetime",
        "from typing import Any",
        "",
        "from pydantic import BaseModel, ConfigDict, Field",
        "",
        "",
    ]

    for name, obj in spec.objects.items():
        lines.append(f"class {name}Read(BaseModel):")
        lines.append(f'    """Read model for {name}."""')
        lines.append("    model_config = ConfigDict(from_attributes=True)")
        lines.append("")
        lines.append("    id: uuid.UUID")
        lines.append("    natural_key: str")
        lines.append("    plant: str | None = None")
        lines.append("    row_hash: str")
        lines.append("    created_run_id: str")
        lines.append("    updated_run_id: str")
        lines.append("    created_at: datetime")
        lines.append("    updated_at: datetime")

        for prop_name, prop in obj.properties.items():
            if prop_name in ("id", "natural_key", "plant"):
                continue
            py_type = TYPE_MAPPING_PYDANTIC.get(prop.type, "str")
            if not prop.required:
                lines.append(f"    {prop_name}: {py_type} | None = None")
            else:
                lines.append(f"    {prop_name}: {py_type}")

        lines.append("")
        lines.append("")

    lines.extend(
        [
            "class PropertyProvenanceRead(BaseModel):",
            "    model_config = ConfigDict(from_attributes=True)",
            "",
            "    id: uuid.UUID",
            "    object_id: uuid.UUID",
            "    object_type: str",
            "    property_name: str",
            "    value: str | None = None",
            "    source_id: str",
            "    source_row_ref: str",
            "    run_id: str",
            "    rule_applied: str",
            "    recorded_at: datetime",
            "",
            "",
            "class LineageEdgeRead(BaseModel):",
            "    model_config = ConfigDict(from_attributes=True)",
            "",
            "    id: uuid.UUID",
            "    run_id: str",
            "    input_dataset: str",
            "    transform: str",
            "    output_dataset: str",
            "    started_at: datetime",
            "    ended_at: datetime",
            "    facets: dict[str, Any] = Field(default_factory=dict)",
            "",
        ]
    )

    return "\n".join(lines) + "\n"


def generate_alembic_migration(spec: OntologySpec) -> str:
    lines = [
        '"""0001_initial_ontology',
        "",
        "Revision ID: 0001_initial_ontology",
        "Revises: None",
        "Create Date: 2026-10-17",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "import sqlalchemy as sa",
        "from alembic import op",
        "",
        "revision = '0001_initial_ontology'",
        "down_revision = None",
        "branch_labels = None",
        "depends_on = None",
        "",
        "",
        "def upgrade() -> None:",
    ]

    # Generate table creations
    for _name, obj in spec.objects.items():
        t_name = obj.table_name
        lines.append(f"    # Table: {t_name}")
        lines.append("    op.create_table(")
        lines.append(f"        '{t_name}',")
        lines.append("        sa.Column('id', sa.Uuid(), primary_key=True),")
        lines.append(
            "        sa.Column('natural_key', sa.String(255), unique=True, nullable=False),"
        )
        lines.append("        sa.Column('plant', sa.String(64), nullable=True),")
        lines.append("        sa.Column('row_hash', sa.String(64), nullable=False),")
        lines.append("        sa.Column('created_run_id', sa.String(128), nullable=False),")
        lines.append("        sa.Column('updated_run_id', sa.String(128), nullable=False),")
        lines.append("        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),")
        lines.append("        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),")

        for prop_name, prop in obj.properties.items():
            if prop_name in ("id", "natural_key", "plant"):
                continue
            sa_type = TYPE_MAPPING_ALEMBIC.get(prop.type, "sa.String(255)")
            nullable = not prop.required
            lines.append(f"        sa.Column('{prop_name}', {sa_type}, nullable={nullable}),")

        lines.append("    )")
        lines.append(f"    op.create_index('ix_{t_name}_natural_key', '{t_name}', ['natural_key'])")
        lines.append(f"    op.create_index('ix_{t_name}_plant', '{t_name}', ['plant'])")

        # Row-level security for plant-scoped tables
        if obj.plant_scoped:
            lines.append(f"    # Enable RLS on {t_name}")
            lines.append(f"    op.execute('ALTER TABLE {t_name} ENABLE ROW LEVEL SECURITY;')")
            lines.append("    op.execute('''")
            lines.append(
                f"        CREATE POLICY {t_name}_plant_isolation ON {t_name} FOR ALL USING ("
            )
            lines.append("            plant IS NULL")
            lines.append("            OR plant = current_setting('app.plant', true)")
            lines.append("            OR current_setting('app.role', true) = 'admin'")
            lines.append("        );")
            lines.append("    ''')")
        lines.append("")

    # PropertyProvenance table
    lines.extend(
        [
            "    # Table: property_provenance",
            "    op.create_table(",
            "        'property_provenance',",
            "        sa.Column('id', sa.Uuid(), primary_key=True),",
            "        sa.Column('object_id', sa.Uuid(), nullable=False),",
            "        sa.Column('object_type', sa.String(64), nullable=False),",
            "        sa.Column('property_name', sa.String(64), nullable=False),",
            "        sa.Column('value', sa.Text(), nullable=True),",
            "        sa.Column('source_id', sa.String(128), nullable=False),",
            "        sa.Column('source_row_ref', sa.String(255), nullable=False),",
            "        sa.Column('run_id', sa.String(128), nullable=False),",
            "        sa.Column('rule_applied', sa.String(64), nullable=False),",
            "        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),",
            "    )",
            "    op.create_index('ix_provenance_object_id', 'property_provenance', ['object_id'])",
            "    op.create_index('ix_provenance_run_id', 'property_provenance', ['run_id'])",
            "",
            "    # Table: lineage_edges",
            "    op.create_table(",
            "        'lineage_edges',",
            "        sa.Column('id', sa.Uuid(), primary_key=True),",
            "        sa.Column('run_id', sa.String(128), nullable=False),",
            "        sa.Column('input_dataset', sa.String(255), nullable=False),",
            "        sa.Column('transform', sa.String(255), nullable=False),",
            "        sa.Column('output_dataset', sa.String(255), nullable=False),",
            "        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),",
            "        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=False),",
            "        sa.Column('facets', sa.JSON(), nullable=False),",
            "    )",
            "    op.create_index('ix_lineage_run_id', 'lineage_edges', ['run_id'])",
            "",
            "",
            "def downgrade() -> None:",
        ]
    )

    for _name, obj in reversed(list(spec.objects.items())):
        lines.append(f"    op.drop_table('{obj.table_name}')")
    lines.append("    op.drop_table('property_provenance')")
    lines.append("    op.drop_table('lineage_edges')")

    return "\n".join(lines) + "\n"


def generate_all(spec: OntologySpec | None = None, output_dir: Path | None = None) -> None:
    """Executes full code generation and writes models.py, schemas.py, and migration."""
    if spec is None:
        spec = load_ontology_spec()
    if output_dir is None:
        output_dir = Path(__file__).parent

    # 1. models.py
    models_file = output_dir / "models.py"
    models_file.write_text(generate_sqlalchemy_models(spec), encoding="utf-8")

    # 2. schemas.py
    schemas_file = output_dir / "schemas.py"
    schemas_file.write_text(generate_pydantic_schemas(spec), encoding="utf-8")

    # 3. migrations
    mig_dir = output_dir / "migrations" / "versions"
    mig_dir.mkdir(parents=True, exist_ok=True)
    mig_file = mig_dir / "0001_initial_ontology.py"
    mig_file.write_text(generate_alembic_migration(spec), encoding="utf-8")


if __name__ == "__main__":
    generate_all()
    print("Ontology codegen completed successfully.")
