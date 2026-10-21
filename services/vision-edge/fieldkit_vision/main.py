"""FastAPI service for Vision Edge multi-camera analytics."""

from __future__ import annotations

import logging
from collections import deque
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import cv2
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from fieldkit_vision.camera_worker import CameraWorker, load_all_camera_configs
from fieldkit_vision.clip_generator import FrameRingBuffer, MinIOClipUploader, generate_event_clip
from fieldkit_vision.config import settings
from fieldkit_vision.detector import YOLOOnnxDetector
from fieldkit_vision.events import ClickHouseEventStorage, RedpandaEventPublisher, VisionEvent
from fieldkit_vision.health import (
    CameraHealthMonitor,
    CameraHealthReport,
    HealthStatus,
)
from fieldkit_vision.homography import CameraHomography
from fieldkit_vision.metrics import (
    VISION_ALERTS_TOTAL,
    VISION_CAMERA_BLUR_SCORE,
    VISION_CAMERA_HEALTH_STATUS,
)
from fieldkit_vision.models import CameraHealthStatus, CameraMetrics, FramePacket, TrackResponse
from fieldkit_vision.reid import (
    CameraTopology,
    GlobalPersonRegistry,
    OSNetFeatureExtractor,
    PersonSighting,
)
from fieldkit_vision.rules_engine import DeterministicRulesEngine
from fieldkit_vision.tracker import ByteTracker, associate_ppe_to_tracks

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("fieldkit.vision.main")

# Global workers, trackers, homographies, health monitors, and reid
workers: dict[str, CameraWorker] = {}
trackers: dict[str, ByteTracker] = {}
homographies: dict[str, CameraHomography] = {}
rules_engines: dict[str, DeterministicRulesEngine] = {}
ring_buffers: dict[str, FrameRingBuffer] = {}
health_monitors: dict[str, CameraHealthMonitor] = {}
recent_events: deque[VisionEvent] = deque(maxlen=500)

topology = CameraTopology.from_yaml("configs/topology.yaml")
person_registry = GlobalPersonRegistry(topology=topology)
reid_extractor = OSNetFeatureExtractor()

event_publisher = RedpandaEventPublisher()
clickhouse_storage = ClickHouseEventStorage()
clip_uploader = MinIOClipUploader()
detector: YOLOOnnxDetector | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown lifecycle for camera workers, trackers, and homographies."""
    global detector
    logger.info("Initializing Vision Edge camera workers from %s...", settings.config_dir)
    configs = load_all_camera_configs(settings.config_dir)

    # Initialize ONNX detector
    detector = YOLOOnnxDetector()

    for cfg in configs:
        worker = CameraWorker(config=cfg)
        workers[cfg.camera_id] = worker
        trackers[cfg.camera_id] = ByteTracker(camera_id=cfg.camera_id)
        ring_buffers[cfg.camera_id] = FrameRingBuffer(capacity=50)

        # Load homography if configured
        homog: CameraHomography | None = None
        if cfg.homography and cfg.homography.image_points and cfg.homography.floor_points_meters:
            try:
                homog = CameraHomography.from_config(cfg.homography)
                homographies[cfg.camera_id] = homog
            except Exception as e:
                logger.warning("Failed to initialize homography for camera %s: %s", cfg.camera_id, e)

        # Initialize deterministic rules engine with temporal smoothing
        rules_engines[cfg.camera_id] = DeterministicRulesEngine(camera_config=cfg, homography=homog)
        health_monitors[cfg.camera_id] = CameraHealthMonitor(camera_id=cfg.camera_id)

        worker.start()
        logger.info("Spawned worker, tracker, and rules engine for camera %s (%s)", cfg.camera_id, cfg.name)

    yield

    logger.info("Shutting down Vision Edge camera workers...")
    for cid, worker in list(workers.items()):
        await worker.stop()
        logger.info("Stopped worker for camera %s", cid)
    workers.clear()
    trackers.clear()
    homographies.clear()
    rules_engines.clear()
    ring_buffers.clear()
    health_monitors.clear()


app = FastAPI(
    title="Fieldkit Vision Edge Service",
    description="Multi-Camera Video Analytics & Worker Safety Ingestion Platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "service": "fieldkit-vision-edge"}


@app.get("/readyz")
async def readyz() -> dict[str, str | int]:
    """Readiness probe."""
    connected_count = sum(1 for w in workers.values() if w.metrics.is_connected)
    return {
        "status": "ready",
        "total_cameras": len(workers),
        "connected_cameras": connected_count,
    }


@app.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/cameras", response_model=list[CameraHealthStatus])
async def list_cameras() -> list[CameraHealthStatus]:
    """List operational status and metrics for all configured cameras."""
    results = []
    for cid, worker in workers.items():
        m = worker.metrics.get_metrics()
        status = "healthy" if m.is_connected and m.processed_fps > 0 else (
            "degraded" if m.is_connected else "offline"
        )
        results.append(CameraHealthStatus(camera_id=cid, status=status, metrics=m))
    return results


@app.get("/cameras/{camera_id}/metrics", response_model=CameraMetrics)
async def get_camera_metrics(camera_id: str) -> CameraMetrics:
    """Retrieve detailed metrics for a specific camera."""
    worker = workers.get(camera_id)
    if not worker:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")
    return worker.metrics.get_metrics()


@app.get("/cameras/{camera_id}/frame")
async def get_camera_frame(camera_id: str) -> Response:
    """Retrieve latest JPEG snapshot from camera queue."""
    worker = workers.get(camera_id)
    if not worker:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    frame_packet = worker.latest_frame
    if not frame_packet or frame_packet.image is None:
        raise HTTPException(status_code=503, detail="No frame available yet")

    success, encoded = cv2.imencode(".jpg", frame_packet.image, [cv2.IMWRITE_JPEG_QUALITY, 80])
    if not success:
        raise HTTPException(status_code=500, detail="Failed to encode JPEG snapshot")

    return Response(content=encoded.tobytes(), media_type="image/jpeg")


@app.get("/cameras/{camera_id}/homography")
async def get_camera_homography(camera_id: str) -> dict[str, Any]:
    """Retrieve homography calibration matrix and points for a camera."""
    worker = workers.get(camera_id)
    if not worker:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    homog = homographies.get(camera_id)
    if not homog:
        return {"configured": False, "camera_id": camera_id}

    return {
        "configured": True,
        "camera_id": camera_id,
        "matrix": homog.matrix.tolist(),
        "inverse_matrix": homog.inverse_matrix.tolist(),
        "image_points": homog._image_points,
        "floor_points_meters": homog._floor_points,
    }


@app.get("/cameras/{camera_id}/tracks", response_model=list[TrackResponse])
async def get_camera_tracks(camera_id: str) -> list[TrackResponse]:
    """Retrieve current tracked entities with PPE compliance and metric coordinates."""
    worker = workers.get(camera_id)
    if not worker:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    tracker = trackers.setdefault(camera_id, ByteTracker(camera_id=camera_id))
    homog = homographies.get(camera_id)

    # If worker has a frame, run detection and tracker update
    frame_packet = worker.latest_frame
    if frame_packet and frame_packet.image is not None and detector is not None:
        detections = detector.detect(frame_packet.image)
        active_tracks = tracker.update(detections, timestamp=frame_packet.timestamp)
        associate_ppe_to_tracks(active_tracks, detections)
    else:
        active_tracks = list(tracker.tracked_tracks.values())

    results: list[TrackResponse] = []
    for t in active_tracks:
        floor_coord = None
        if homog:
            try:
                floor_coord = homog.image_to_floor(t.foot_point)
            except Exception:
                pass

        results.append(
            TrackResponse(
                track_id=t.track_id,
                camera_id=t.camera_id,
                class_id=t.class_id,
                class_name=t.class_name,
                box=t.box,
                confidence=t.confidence,
                foot_point=t.foot_point,
                head_region=t.head_region,
                torso_region=t.torso_region,
                floor_coord=floor_coord,
                is_wearing_helmet=t.is_wearing_helmet,
                is_wearing_vest=t.is_wearing_vest,
                helmet_compliance_ratio=round(t.helmet_compliance_ratio, 3),
                vest_compliance_ratio=round(t.vest_compliance_ratio, 3),
                speed_mps=t.speed_mps,
            )
        )
    return results


async def process_frame_and_evaluate_rules(
    camera_id: str,
    frame_packet: FramePacket,
    generate_clips: bool = False,
) -> list[VisionEvent]:
    """Run detection, tracking, PPE association, deterministic rules engine, and emit events."""
    ring = ring_buffers.setdefault(camera_id, FrameRingBuffer(capacity=50))
    ring.append(frame_packet)

    tracker = trackers.setdefault(camera_id, ByteTracker(camera_id=camera_id))
    rules_engine = rules_engines.get(camera_id)

    if detector is None or rules_engine is None or frame_packet.image is None:
        return []

    # 1. Detection
    detections = detector.detect(frame_packet.image)

    # 2. Tracking
    active_tracks = tracker.update(detections, timestamp=frame_packet.timestamp)

    # 3. PPE Association
    associate_ppe_to_tracks(active_tracks, detections)

    # 4. Rules Engine Evaluation (with temporal smoothing and 30s cooldown)
    violations = rules_engine.evaluate(tracks=active_tracks, timestamp=frame_packet.timestamp)

    emitted_events: list[VisionEvent] = []
    for v in violations:
        clip_uri: str | None = None

        # 5. Optional 10s MP4 event clip generation with privacy face blur
        if generate_clips and ring.size() >= 5:
            try:
                clip_path = Path(f"data/p5/clips/{camera_id}_{int(frame_packet.timestamp)}.mp4")
                person_boxes = [t.box for t in active_tracks if t.class_name == "person"]
                generate_event_clip(
                    frames=ring.get_frames(),
                    output_path=clip_path,
                    fps=5.0,
                    apply_privacy=True,
                    person_boxes=person_boxes,
                )
                clip_uri = clip_uploader.upload_clip(clip_path, camera_id=camera_id, event_id=f"evt_{v.track_id}")
            except Exception as e:
                logger.warning("Failed to generate/upload event clip for camera %s: %s", camera_id, e)

        evt = VisionEvent(
            camera_id=camera_id,
            plant_id="DE-HAM",
            rule_id=v.rule_id,
            rule_type=v.rule_type,
            severity=v.severity,
            track_id=v.track_id,
            related_track_id=v.related_track_id,
            zone_id=v.zone_id,
            metric_distance=v.metric_distance,
            metric_speed=v.metric_speed,
            timestamp=v.timestamp,
            clip_uri=clip_uri,
            metadata=v.metadata,
        )

        # Increment Prometheus alert metric
        VISION_ALERTS_TOTAL.labels(camera_id=camera_id, rule_type=v.rule_type, severity=v.severity).inc()

        # Stream to Redpanda and ClickHouse
        await event_publisher.publish(evt)
        await clickhouse_storage.store_event(evt)
        recent_events.appendleft(evt)
        emitted_events.append(evt)

    return emitted_events


@app.get("/events", response_model=list[VisionEvent])
async def list_events(
    camera_id: str | None = None,
    rule_type: str | None = None,
    severity: str | None = None,
    limit: int = 50,
) -> list[VisionEvent]:
    """Retrieve recent safety and security violation events with optional filtering."""
    results = list(recent_events)
    if camera_id:
        results = [e for e in results if e.camera_id == camera_id]
    if rule_type:
        results = [e for e in results if e.rule_type == rule_type]
    if severity:
        results = [e for e in results if e.severity == severity]
    return results[:limit]


@app.post("/cameras/{camera_id}/evaluate", response_model=list[VisionEvent])
async def evaluate_camera_events(camera_id: str) -> list[VisionEvent]:
    """Evaluate active camera frame against rules engine and emit events."""
    worker = workers.get(camera_id)
    if not worker:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    frame_packet = worker.latest_frame
    if not frame_packet or frame_packet.image is None:
        return []

    return await process_frame_and_evaluate_rules(camera_id, frame_packet, generate_clips=False)


@app.get("/cameras/{camera_id}/health", response_model=CameraHealthReport)
async def get_camera_health(camera_id: str) -> CameraHealthReport:
    """Retrieve diagnostic health assessment for a specific camera."""
    worker = workers.get(camera_id)
    if not worker:
        raise HTTPException(status_code=404, detail=f"Camera {camera_id} not found")

    monitor = health_monitors.get(camera_id)
    if not monitor:
        monitor = CameraHealthMonitor(camera_id=camera_id)
        health_monitors[camera_id] = monitor

    metrics_obj = worker.metrics.get_metrics()
    frame_packet = worker.latest_frame
    if frame_packet and frame_packet.image is not None:
        report = monitor.evaluate_frame(
            frame_packet.image,
            timestamp=frame_packet.timestamp,
            processed_fps=metrics_obj.processed_fps,
            reconnect_count=metrics_obj.reconnects,
        )
    else:
        report = CameraHealthReport(
            camera_id=camera_id,
            timestamp=metrics_obj.last_frame_timestamp or 0.0,
            status=HealthStatus.HEALTHY if metrics_obj.is_connected else HealthStatus.CRITICAL,
            processed_fps=metrics_obj.processed_fps,
            reconnect_count=metrics_obj.reconnects,
        )

    # Update Prometheus gauges
    status_num = (
        1.0
        if report.status == HealthStatus.HEALTHY
        else (2.0 if report.status == HealthStatus.DEGRADED else 3.0)
    )
    VISION_CAMERA_HEALTH_STATUS.labels(camera_id=camera_id).set(status_num)
    VISION_CAMERA_BLUR_SCORE.labels(camera_id=camera_id).set(report.laplacian_variance)
    return report


@app.get("/health/cameras", response_model=list[CameraHealthReport])
async def list_all_camera_health() -> list[CameraHealthReport]:
    """Retrieve diagnostic health reports across all configured cameras."""
    reports: list[CameraHealthReport] = []
    for cid in workers.keys():
        try:
            rep = await get_camera_health(cid)
            reports.append(rep)
        except Exception:
            pass
    return reports


@app.get("/reid/topology")
async def get_reid_topology() -> dict[str, Any]:
    """Retrieve inter-camera spatial-temporal transit topology."""
    return topology.model_dump()


@app.get("/reid/journeys/{person_id}", response_model=list[PersonSighting])
async def get_person_journey(person_id: str) -> list[PersonSighting]:
    """Retrieve chronological cross-camera journey history for a global person ID."""
    journey = person_registry.get_journey(person_id)
    if not journey:
        raise HTTPException(
            status_code=404, detail=f"No sightings recorded for person {person_id}"
        )
    return journey



