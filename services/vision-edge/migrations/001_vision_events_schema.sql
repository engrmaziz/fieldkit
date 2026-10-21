-- ClickHouse Schema Migration: 001_vision_events_schema.sql
-- Multi-Camera Vision Analytics Safety Events, Redpanda Kafka Engine, and 90-Day Retention

CREATE DATABASE IF NOT EXISTS fieldkit_vision;

-- 1. Main Analytical Events Table
CREATE TABLE IF NOT EXISTS fieldkit_vision.events
(
    event_id String,
    timestamp DateTime64(3, 'UTC'),
    camera_id LowCardinality(String),
    plant_id LowCardinality(String) DEFAULT 'DE-HAM',
    rule_id LowCardinality(String),
    rule_type LowCardinality(String),
    severity LowCardinality(String) DEFAULT 'WARNING',
    track_id UInt32,
    related_track_id UInt32 DEFAULT 0,
    zone_id LowCardinality(String) DEFAULT '',
    metric_distance Nullable(Float32),
    metric_speed Nullable(Float32),
    clip_uri String DEFAULT '',
    metadata_json String DEFAULT '{}',
    created_at DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (camera_id, rule_type, severity, timestamp, event_id)
TTL toDateTime(timestamp) + INTERVAL 90 DAY
SETTINGS index_granularity = 8192;

-- 2. Kafka Engine Table Consuming Redpanda Topic vision.events
CREATE TABLE IF NOT EXISTS fieldkit_vision.events_kafka
(
    event_id String,
    timestamp Float64,
    camera_id String,
    plant_id String,
    rule_id String,
    rule_type String,
    severity String,
    track_id UInt32,
    related_track_id UInt32,
    zone_id String,
    metric_distance Nullable(Float32),
    metric_speed Nullable(Float32),
    clip_uri String,
    metadata_json String
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = 'redpanda:9092',
    kafka_topic_list = 'vision.events',
    kafka_group_name = 'clickhouse-vision-events',
    kafka_format = 'JSONEachRow',
    kafka_num_consumers = 2;

-- 3. Materialized View Piping Kafka Ingestion Stream into MergeTree Table
CREATE MATERIALIZED VIEW IF NOT EXISTS fieldkit_vision.events_mv TO fieldkit_vision.events AS
SELECT
    event_id,
    toDateTime64(timestamp, 3, 'UTC') AS timestamp,
    camera_id,
    plant_id,
    rule_id,
    rule_type,
    severity,
    track_id,
    related_track_id,
    zone_id,
    metric_distance,
    metric_speed,
    clip_uri,
    metadata_json,
    now() AS created_at
FROM fieldkit_vision.events_kafka;
