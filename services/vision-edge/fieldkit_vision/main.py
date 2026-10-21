"""FastAPI service for Vision Edge multi-camera analytics."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import cv2
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from fieldkit_vision.camera_worker import CameraWorker, load_all_camera_configs
from fieldkit_vision.config import settings
from fieldkit_vision.detector import YOLOOnnxDetector
from fieldkit_vision.homography import CameraHomography
from fieldkit_vision.models import CameraHealthStatus, CameraMetrics, TrackResponse
from fieldkit_vision.tracker import ByteTracker, associate_ppe_to_tracks

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("fieldkit.vision.main")

# Global workers, trackers, and homographies
workers: dict[str, CameraWorker] = {}
trackers: dict[str, ByteTracker] = {}
homographies: dict[str, CameraHomography] = {}
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

        # Load homography if configured
        if cfg.homography and cfg.homography.image_points and cfg.homography.floor_points_meters:
            try:
                homographies[cfg.camera_id] = CameraHomography.from_config(cfg.homography)
            except Exception as e:
                logger.warning("Failed to initialize homography for camera %s: %s", cfg.camera_id, e)

        worker.start()
        logger.info("Spawned worker and tracker for camera %s (%s)", cfg.camera_id, cfg.name)

    yield

    logger.info("Shutting down Vision Edge camera workers...")
    for cid, worker in list(workers.items()):
        await worker.stop()
        logger.info("Stopped worker for camera %s", cid)
    workers.clear()
    trackers.clear()
    homographies.clear()


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

