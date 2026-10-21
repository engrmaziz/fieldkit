# ADR 0022: In-House Pure Go Event-Sourced Workflow Engine vs Heavy Temporal/Airflow Cluster

- **Status**: Accepted
- **Date**: 2026-10-21
- **Author**: engrmaziz & Tobias Becker

## Context
Industrial manufacturing plants operating in air-gapped Operational Technology (OT) networks require durable, long-running workflow orchestration to coordinate ETL pipelines, automated defect model retraining, shadow evaluations, and human-in-the-loop approvals.
Standard enterprise orchestration solutions present severe constraints in air-gapped plant deployments:
1. **Resource Bloat**: Systems like Apache Airflow or Temporal require heavy multi-node clustering (PostgreSQL/MySQL + Elasticsearch/Cassandra + multiple coordination daemons), consuming 4+ GB of baseline memory before running any workflow.
2. **External Dependencies & Telemetry**: Off-the-shelf orchestrators often embed telemetry, cloud-calling defaults, or complex ingress requirements that violate OT zero-trust egress policies.
3. **Deployment Complexity**: Managing Cassandra, Temporal web UI, and separate worker pools on a single industrial server is an operational burden for on-site plant IT teams.

## Decision
We implemented a **lightweight, pure Go 1.23+ event-sourced workflow engine** (`services/workflow-engine`) with deterministic state machine mechanics:
1. **Deterministic Event Sourcing (`internal/orchestrator/orchestrator.go`)**:
   - Complete workflow run state is computed as a pure, stateless function of its append-only event stream: `ComputeNextActions(events []WorkflowEvent, def *WorkflowDefinition) NextActions`.
   - Zero state drift across server crashes, worker terminations, or container restarts; replays log to reconstruct execution state identically.
2. **First-Class Saga Pattern Compensations**:
   - Every forward step can define an automated reverse compensation step (`compensate_with`).
   - If a downstream terminal step fails, the engine automatically schedules compensating actions in strict reverse topological order.
3. **Distributed Worker Leasing**:
   - Worker leasing pool uses database-level atomic reservation (`SELECT ... FOR UPDATE SKIP LOCKED` semantics with 30s lease duration and 5s heartbeat renewals).
   - Surviving worker instances automatically reclaim orphaned leases upon SIGKILL or hardware failure.
4. **Lightweight Footprint**:
   - Single static Go binary (< 25 MB disk, < 50 MB RAM baseline) exposing health probes (`/healthz`, `/readyz`), Prometheus metrics (`/metrics`), and Chi REST API.

## Consequences
- **Positive**:
  - Memory consumption reduced from ~4 GB (Temporal) to < 50 MB (> 98% reduction).
  - Strictly 0 duplicate side-effects verified across 200 concurrent workflows under live worker SIGKILL crashes.
  - Native Saga rollbacks, human approval gates, timer waits, and fan-out maps without third-party plugins.
- **Negative**:
  - Does not support arbitrary dynamic code execution within workflow definitions; workflows must be declared via deterministic YAML DAGs and HTTP/Wait/Branch/Map/Approval primitives.
