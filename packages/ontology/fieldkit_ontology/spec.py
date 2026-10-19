"""Ontology YAML Schema Parser and Validator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class PropertySpec(BaseModel):
    """Specification of an individual object property/column."""

    type: str  # string, float, integer, date, uuid, boolean
    required: bool = True
    default: Any = None
    description: str | None = None


class ObjectSpec(BaseModel):
    """Specification of an ontology object entity."""

    description: str
    table_name: str
    primary_key: str = "id"
    natural_key: str
    plant_scoped: bool = False
    properties: dict[str, PropertySpec] = Field(default_factory=dict)


class LinkSpec(BaseModel):
    """Specification of a relationship edge between ontology objects."""

    from_object: str
    to_object: str
    cardinality: str  # many_to_one, one_to_many, many_to_many, one_to_one
    foreign_key: str | None = None
    description: str | None = None


class OntologySpec(BaseModel):
    """Root model for the enterprise ontology definition."""

    version: str
    objects: dict[str, ObjectSpec]
    links: dict[str, LinkSpec]


def load_ontology_spec(yaml_path: str | Path | None = None) -> OntologySpec:
    """Loads and validates ontology.yaml specification."""
    if yaml_path is None:
        yaml_path = Path(__file__).parent.parent / "ontology.yaml"
    path = Path(yaml_path)
    if not path.exists():
        raise FileNotFoundError(f"Ontology specification not found at: {path}")

    raw_data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return OntologySpec.model_validate(raw_data)
