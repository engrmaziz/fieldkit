# ADR 0006: Versioned YAML Ontology Specification and Codegen vs Dynamic EAV Schema

- **Status**: Accepted
- **Date**: 2026-10-19
- **Author**: engrmaziz

## Context
Industrial data fusion platforms (such as Palantir Foundry or C3.ai) structure heterogeneous enterprise records into an integrated business ontology. Common architectural patterns for ontology persistence include:
1. Dynamic Entity-Attribute-Value (EAV) / JSONB tables in a relational database.
2. Strongly-typed, version-controlled relational tables generated deterministically from an ontology specification.

Halden Industrie requires sub-150 ms P95 latency across 50k+ objects, keyset cursor pagination, typed link graph traversal, strict schema drift governance, and full TypeScript/Python type safety across services.

## Decision
We established `packages/ontology/ontology.yaml` as the authoritative single source of truth for all business entities and link types:

1. **Declarative Specification (`ontology.yaml`)**:
   - Explicit object definitions (`Supplier`, `Part`, `Plant`, `PurchaseOrder`, `Shipment`, `QualityIncident`, `Certificate`).
   - Strongly-typed properties (`string`, `float`, `integer`, `date`, `uuid`), primary keys, natural keys, and plant scoping.
   - Directed link definitions (`ordered_from`, `delivered_to`, `incident_on`, `certified_by`, `supplies`) with cardinality declarations (`one_to_many`, `many_to_one`).
2. **Deterministic Codegen (`packages/ontology/codegen.py`)**:
   - Generates SQLAlchemy 2 async declarative models with typed columns and composite indexes.
   - Generates Pydantic read models (`schemas.py`) for API serialization.
   - Generates Alembic database migration scripts with PostgreSQL RLS policies.
   - Golden test `test_committed_models_match_codegen_golden` runs in CI, failing if hand-edits drift from `ontology.yaml`.
3. **Safe Typed Query DSL (`services/foundry-api/dsl.py`)**:
   - Compiles user requests `{type, filters, traverse, limit}` into validated SQLAlchemy AST expressions.
   - Validates properties, operators, and types against `ontology.yaml` without permitting raw SQL string concatenation.

## Alternatives Rejected
- **Dynamic Entity-Attribute-Value (EAV) Store**: Poor join performance, lack of database column indexing for range filters (`total_amount >= 1500`), loss of referential integrity, and inability to utilize constant-time keyset pagination.
- **Manual Schema Synchronization**: High maintenance overhead and risk of silent drift between OpenAPI models, database tables, and validation schemas.

## Consequences
- **Positive**: Strict compile-time and runtime type checking, high query throughput (>300 req/s), constant-time keyset pagination, zero SQL injection attack surface, and seamless OpenLineage DAG provenance tracking.
- **Negative**: Modifying the ontology requires editing `ontology.yaml`, running `fieldkit-ontology codegen`, and generating an Alembic migration.
