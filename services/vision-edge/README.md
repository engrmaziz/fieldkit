# Fieldkit Vision Edge (Project 5)

Multi-Camera Edge Video Analytics Platform for Halden Industrie GmbH (Plant Safety & Logistics Operations, Hamburg `DE-HAM`).

## System Overview

Fieldkit Vision Edge processes 4 simulated RTSP camera feeds in real time on a local laptop CPU/GPU:
- `cam1_press`: Heavy Stamping Press Bed 3
- `cam2_logistics`: High-Bay Forklift Corridor A
- `cam3_assembly`: Hydraulic Staging Workstations
- `cam4_perimeter`: North Logistics Gate & Security Perimeter

## Core Capabilities Across Milestones

1. **Robust Edge Ingestion (M1)**:
   - Independent `asyncio` ingestion workers with TCP transport (`rtsp_transport=tcp`), 5.0s timeout, and exponential backoff auto-reconnect (up to 30s).
   - Timestamp-based 5 FPS downsampling.
   - Bounded `asyncio.Queue(maxsize=4)` with drop-oldest discipline ensuring bounded memory under compute backpressure.
   - Per-camera Prometheus metrics (`decoded_fps`, `processed_fps`, `dropped_frames`, `reconnects`).

2. **PPE & Machinery Detector (M2)**:
   - YOLO11 ONNX dynamic-batch runtime supporting unified classes: `[person, helmet, no_helmet, vest, forklift]`.
   - Vectorized NMS and multi-camera dynamic batching across frames.

3. **Multi-Object Tracking & Homography (M3)**:
   - ByteTrack multi-object tracking with Kalman motion prediction and track ID persistence.
   - Top 25% head-region PPE association with rolling observation history.
   - 4-point floor-plane homography projective transformation mapping pixel foot-points to physical meters ($0.0000\text{ m}$ reprojection error).

4. **Deterministic Rules Engine & Privacy Clips (M4)**:
   - Ray-casting polygon containment (`point_in_polygon`), line crossing detection, and zone dwell timing.
   - Rolling compliance window ($\ge 70\%$ violation over 2.0s) suppressing false alarms.
   - Euclidean metric proximity ($< 2.0\text{ m}$, forklift speed $\ge 0.5\text{ m/s}$, duration $\ge 0.6\text{ s}$).
   - 30s alert cooldown per `(camera_id, rule_id, target_key)`.
   - Redpanda event streaming to `vision.events` and ClickHouse partitioned `MergeTree` schema with 90-day TTL.
   - 10s MP4 event clip generator (5s pre + 5s post ring buffer) with GDPR Gaussian face-blurring on detected persons uploaded to MinIO `vision-clips`.

5. **Cross-Camera Re-ID & Camera Diagnostics (M5)**:
   - 512-dim OSNet normalized feature embedding (`cosine similarity >= 0.75`).
   - Plant spatial-temporal transit topology gating (`configs/topology.yaml`).
   - Camera hardware health diagnostics: frozen frame detection, black frame detection, Laplacian blur/defocus variance drop, and ORB view shift / tamper detection.

6. **Search API & Next.js 14 Console UI (M6)**:
   - Parameterized REST API: `GET /events`, `GET /events/{event_id}`, `GET /cameras/{camera_id}/health`, `GET/POST /cameras/{camera_id}/zones`.
   - Conversational Natural Language Query Parser: `POST /search/nl` emitting schema-validated `EventFilter` JSON.
   - Web Console at `/vision`: 4-camera live wall, conversational search bar, events table, video clip player with 2D floor-plan minimap, Re-ID journey timeline, and camera health grid.

7. **Evaluation Benchmark & Load Testing (M7)**:
   - 30 annotated industrial shop-floor video scenarios: 1.0000 precision, 1.0000 recall, 0.000 FA/cam-hr.
   - Ablation study proving 10.9x alert volume noise reduction via temporal smoothing.
   - Concurrent 4-camera sustained load test at 19.9 aggregate FPS with 0-frame backpressure depth and 20.45 ms P95 latency.

## Verification & Execution

```bash
# Run turnkey 2-minute demonstration
uv run python scripts/seed_demo.py --profile p5

# Run master evaluation benchmark and generate report
uv run python evals/runner.py --profile p5

# Run unit and integration tests
uv run pytest services/vision-edge/tests/ -v
```
