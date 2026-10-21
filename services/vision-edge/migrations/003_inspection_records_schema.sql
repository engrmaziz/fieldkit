-- PostgreSQL Schema Migration: 003_inspection_records_schema.sql
-- Fieldkit Project 6: InspectAI Defect Inspection Ledger & Human Review Audits

CREATE TABLE IF NOT EXISTS inspection_records (
    inspection_id VARCHAR(64) PRIMARY KEY,
    part_id VARCHAR(128) NOT NULL,
    product_id VARCHAR(64) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    disposition VARCHAR(32) NOT NULL,              -- 'pass', 'review', 'reject'
    anomaly_score DOUBLE PRECISION NOT NULL,        -- PatchCore normalized anomaly score [0.0, 1.0]
    predicted_class VARCHAR(64) NOT NULL,          -- Supervised defect class or 'good'
    calibrated_probability DOUBLE PRECISION NOT NULL, -- Temperature-scaled probability P(c|x)
    probabilities JSONB NOT NULL DEFAULT '{}'::jsonb, -- Full calibrated posterior distribution
    expected_cost DOUBLE PRECISION NOT NULL,       -- Computed asymmetric expected cost
    heatmap_uri TEXT,                              -- MinIO s3:// or file path to blended Jet heatmap JPEG
    image_uri TEXT,                                -- MinIO s3:// or file path to raw input image
    is_audit_sample BOOLEAN NOT NULL DEFAULT FALSE,-- 2% random seeded audit flag
    operator_label VARCHAR(64),                    -- Human reviewer confirmed label
    operator_notes TEXT,                           -- Quality operator audit notes
    reviewed_by VARCHAR(64),                       -- Operator ID (e.g., 'mehmet.yilmaz')
    reviewed_at TIMESTAMPTZ,                       -- Timestamp of human review disposition
    latency_ms DOUBLE PRECISION NOT NULL,          -- End-to-end edge inference latency
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexing for high-throughput queries, filtering by product, disposition, and timestamp
CREATE INDEX IF NOT EXISTS idx_inspection_product_ts
    ON inspection_records (product_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_inspection_disposition
    ON inspection_records (disposition, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_inspection_review_queue
    ON inspection_records (product_id, timestamp ASC)
    WHERE disposition = 'review' AND operator_label IS NULL;

CREATE INDEX IF NOT EXISTS idx_inspection_audit_samples
    ON inspection_records (timestamp DESC)
    WHERE is_audit_sample = TRUE;
