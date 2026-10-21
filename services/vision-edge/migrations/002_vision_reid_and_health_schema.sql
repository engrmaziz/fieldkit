-- Migration 002: ClickHouse schema for Cross-Camera Re-ID (Person Journeys) and Camera Health Audits
-- Project 5: Multi-Camera Edge Video Analytics Platform

CREATE DATABASE IF NOT EXISTS fieldkit_vision;

-- 1. Person local track sightings and global identity association
CREATE TABLE IF NOT EXISTS fieldkit_vision.person_tracks
(
    global_person_id   String,
    camera_id          LowCardinality(String),
    track_id           UInt32,
    first_seen         Float64,
    last_seen          Float64,
    similarity         Float32,
    created_at         DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree(last_seen)
ORDER BY (global_person_id, camera_id, track_id);

-- 2. Cross-camera transition journey audit
CREATE TABLE IF NOT EXISTS fieldkit_vision.person_journeys
(
    journey_id         UUID DEFAULT generateUUIDv4(),
    global_person_id   String,
    from_camera        LowCardinality(String),
    to_camera          LowCardinality(String),
    transit_time_sec   Float32,
    similarity         Float32,
    timestamp          DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (global_person_id, timestamp)
TTL timestamp + INTERVAL 90 DAY;

-- 3. Camera health diagnostic reports
CREATE TABLE IF NOT EXISTS fieldkit_vision.camera_health
(
    camera_id          LowCardinality(String),
    timestamp          DateTime64(3),
    status             LowCardinality(String),
    is_frozen          UInt8,
    is_black           UInt8,
    is_blurred         UInt8,
    is_view_shifted    UInt8,
    processed_fps      Float32,
    laplacian_variance Float32,
    mean_intensity     Float32,
    mean_abs_diff      Float32,
    orb_match_ratio    Float32,
    reconnect_count    UInt32,
    diagnostics        Array(String)
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (camera_id, timestamp)
TTL toDateTime(timestamp) + INTERVAL 90 DAY;
