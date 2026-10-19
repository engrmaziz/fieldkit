-- ClickHouse Schema Migration: 001_initial_schema.sql
-- Fieldkit Project 7: Tracehub (LLM Observability & Anomaly Alerting)

CREATE DATABASE IF NOT EXISTS fieldkit_tracehub;

-- 1. Main analytical spans table (MergeTree with 30-day TTL)
CREATE TABLE IF NOT EXISTS fieldkit_tracehub.spans (
    trace_id String,
    span_id String,
    parent_span_id String,
    service LowCardinality(String),
    name LowCardinality(String),
    start_time DateTime64(6, 'UTC'),
    end_time DateTime64(6, 'UTC'),
    duration_ms Float64,
    status LowCardinality(String),
    status_message String,
    model LowCardinality(String),
    task LowCardinality(String),
    prompt_version LowCardinality(String),
    route LowCardinality(String),
    plant LowCardinality(String),
    input_tokens UInt32,
    output_tokens UInt32,
    attributes Map(String, String),
    events String
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(start_time)
ORDER BY (service, task, start_time, trace_id, span_id)
TTL toDateTime(start_time) + INTERVAL 30 DAY
SETTINGS index_granularity = 8192;

-- 2. Minute-level Aggregated Rollups (AggregatingMergeTree with Quantiles)
CREATE TABLE IF NOT EXISTS fieldkit_tracehub.metrics_1m (
    window_start DateTime('UTC'),
    service LowCardinality(String),
    task LowCardinality(String),
    model LowCardinality(String),
    prompt_version LowCardinality(String),
    route LowCardinality(String),
    plant LowCardinality(String),
    call_count SimpleAggregateFunction(sum, UInt64),
    error_count SimpleAggregateFunction(sum, UInt64),
    total_duration_ms SimpleAggregateFunction(sum, Float64),
    total_input_tokens SimpleAggregateFunction(sum, UInt64),
    total_output_tokens SimpleAggregateFunction(sum, UInt64),
    latency_quantiles AggregateFunction(quantiles(0.5, 0.9, 0.95, 0.99), Float64)
)
ENGINE = AggregatingMergeTree()
PARTITION BY toYYYYMM(window_start)
ORDER BY (service, task, model, prompt_version, route, plant, window_start)
TTL window_start + INTERVAL 90 DAY;

-- 3. Materialized View computing 1-minute aggregations in real-time
CREATE MATERIALIZED VIEW IF NOT EXISTS fieldkit_tracehub.mv_spans_to_metrics_1m
TO fieldkit_tracehub.metrics_1m AS
SELECT
    toStartOfMinute(start_time) AS window_start,
    service,
    task,
    model,
    prompt_version,
    route,
    plant,
    count() AS call_count,
    countIf(status = 'ERROR' OR status = 'error') AS error_count,
    sum(duration_ms) AS total_duration_ms,
    sum(input_tokens) AS total_input_tokens,
    sum(output_tokens) AS total_output_tokens,
    quantilesState(0.5, 0.9, 0.95, 0.99)(duration_ms) AS latency_quantiles
FROM fieldkit_tracehub.spans
GROUP BY
    window_start,
    service,
    task,
    model,
    prompt_version,
    route,
    plant;

-- 4. Kafka Engine table reading from Redpanda topic 'otel.spans'
CREATE TABLE IF NOT EXISTS fieldkit_tracehub.kafka_spans_queue (
    raw_payload String
)
ENGINE = Kafka()
SETTINGS
    kafka_broker_list = 'redpanda:9092',
    kafka_topic_list = 'otel.spans',
    kafka_group_name = 'clickhouse-otel-ingest',
    kafka_format = 'JSONAsString';
