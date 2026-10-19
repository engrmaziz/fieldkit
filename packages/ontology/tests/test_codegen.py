"""Golden test for deterministic ontology code generation."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fieldkit_ontology.codegen import (
    generate_alembic_migration,
    generate_pydantic_schemas,
    generate_sqlalchemy_models,
)
from fieldkit_ontology.spec import load_ontology_spec


def test_load_ontology_spec_structure() -> None:
    spec = load_ontology_spec()
    assert spec.version == "1.0.0"
    assert len(spec.objects) == 7
    assert len(spec.links) == 5

    assert "Supplier" in spec.objects
    assert "PurchaseOrder" in spec.objects
    assert spec.objects["PurchaseOrder"].plant_scoped is True
    assert spec.objects["Supplier"].plant_scoped is False


def test_codegen_produces_valid_syntax() -> None:
    spec = load_ontology_spec()

    models_code = generate_sqlalchemy_models(spec)
    ast.parse(models_code)
    assert "class Supplier(Base):" in models_code
    assert "class PurchaseOrder(Base):" in models_code
    assert "class PropertyProvenance(Base):" in models_code
    assert "class LineageEdge(Base):" in models_code

    schemas_code = generate_pydantic_schemas(spec)
    ast.parse(schemas_code)
    assert "class SupplierRead(BaseModel):" in schemas_code
    assert "class PurchaseOrderRead(BaseModel):" in schemas_code

    migration_code = generate_alembic_migration(spec)
    ast.parse(migration_code)
    assert "ENABLE ROW LEVEL SECURITY" in migration_code


def test_committed_models_match_codegen_golden() -> None:
    """Ensures committed models and schemas match codegen output without drift."""
    spec = load_ontology_spec()
    pkg_dir = Path(__file__).parent.parent / "fieldkit_ontology"

    models_path = pkg_dir / "models.py"
    if models_path.exists():
        expected_models = generate_sqlalchemy_models(spec)
        actual_ast = ast.dump(ast.parse(models_path.read_text(encoding="utf-8")))
        expected_ast = ast.dump(ast.parse(expected_models))
        assert actual_ast == expected_ast

    schemas_path = pkg_dir / "schemas.py"
    if schemas_path.exists():
        expected_schemas = generate_pydantic_schemas(spec)
        actual_ast = ast.dump(ast.parse(schemas_path.read_text(encoding="utf-8")))
        expected_ast = ast.dump(ast.parse(expected_schemas))
        assert actual_ast == expected_ast


def test_alembic_offline_migration_generates_valid_sql(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verifies that Alembic generates complete, valid PostgreSQL DDL with RLS in offline mode."""
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head", sql=True)
    captured = capsys.readouterr()
    sql = captured.out

    assert "CREATE TABLE suppliers" in sql
    assert "CREATE TABLE purchase_orders" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "CREATE POLICY purchase_orders_plant_isolation" in sql
    assert "CREATE TABLE property_provenance" in sql
    assert "CREATE TABLE lineage_edges" in sql
    assert "CREATE ROLE assistant_ro" in sql
    assert "GRANT SELECT ON TABLE" in sql
