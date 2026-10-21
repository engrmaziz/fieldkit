# ADR 0016: ClickHouse MergeTree vs. PostgreSQL for High-Frequency Industrial Vision Events

- **Status**: Accepted
- **Date**: 2026-10-21
- **Author**: engrmaziz

## Context
Project 5 (Multi-Camera Edge Video Analytics) ingests 4 continuous camera streams generating continuous telemetry:
1. **High Ingestion Write Velocity**: 4 cameras at 5 FPS generate 20 processed frame states/sec, high-volume bounding box trajectories, cross-camera person sightings, and camera hardware diagnostic metrics.
2. **Analytical Query Patterns**: Safety compliance dashboards, EHS audit investigations, and natural language search queries filter over time ranges (`timestamp BETWEEN from AND to`), specific cameras, rule types, and person track identifiers over millions of rows.
3. **Data Lifecycle & Storage Limits**: Industrial edge servers operate with constrained local NVMe storage. Event history older than 90 days must be purged automatically without locking database tables or causing I/O spikes.

## Decision

1. **ClickHouse Columnar Storage for Vision Events**:
   - Store all safety violation events, cross-camera worker tracks, and camera health records in ClickHouse rather than PostgreSQL.
   - Core tables:
     * `fieldkit_vision.events`: Partitioned by month (`toYYYYMM(timestamp)`), ordered by `(camera_id, rule_type, severity, timestamp, event_id)` with native `TTL timestamp + INTERVAL 90 DAY`.
     * `fieldkit_vision.person_tracks`: Engine `ReplacingMergeTree(last_seen)` for automatic deduplication of active person tracklets and appearance embeddings.
     * `fieldkit_vision.person_journeys`: Multi-camera transit audit trail ordered by `(plant_id, person_id, start_time)`.
     * `fieldkit_vision.camera_health`: Periodic hardware diagnostic metrics (blur, freeze, view shift, FPS).

2. **Decoupled Asynchronous Streaming via Redpanda**:
   - Vision edge workers publish structured JSON events to Redpanda (Kafka-compatible) topic `vision.events` partitioned by `camera_id`.
   - ClickHouse consumes from the topic using the native Kafka Engine table + Materialized View pipeline, guaranteeing decoupled buffering and zero frame-drop during database maintenance.

## Consequences
- **Positive**: Sub-millisecond range queries across millions of safety records, high columnar compression ratios (>10x), zero write degradation during heavy batching, and automated partition-level TTL drops with zero VACUUM overhead.
- **Negative**: Lack of relational foreign key constraints and ACID multi-table transactions; however, vision event streams are strictly append-only immutable time-series data where relational transactions are unnecessary.
