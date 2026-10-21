# Fieldkit Vision Edge (P5)

Multi-Camera Edge Video Analytics Platform for Halden Industrie GmbH (Plant Safety & Logistics Operations, Hamburg `DE-HAM`).

## Features
- Ingestion worker with MediaMTX RTSP simulation, 5 FPS timestamp downsampler, bounded queue backpressure, and exponential auto-reconnect.
- PPE and forklift detector (YOLO11 ONNX runtime) with dynamic batching and vectorized NMS.
- ByteTrack multi-object tracking, top 25% head-region PPE association, and floor homography calibration.
- Deterministic rules engine with temporal violation smoothing, 30s alert cooldown, Redpanda `vision.events` streaming, ClickHouse schema migration, and 10s MP4 clips with Gaussian privacy face blurring.
