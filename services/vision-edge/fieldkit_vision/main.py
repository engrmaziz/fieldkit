"""FastAPI service for Vision Edge multi-camera analytics."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import cv2
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from fieldkit_vision.camera_worker import CameraWorker, load_all_camera_configs
from fieldkit_vision.config import settings
from fieldkit_vision.models import CameraHealthStatus, CameraMetrics

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("fieldkit.vision.main")

# Global workers dictionary
workers: dict[str, CameraWorker] = {}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown lifecycle for camera workers."""
    logger.info("Initializing Vision Edge camera workers from %s...", settings.config_dir)
    configs = load_all_camera_configs(settings.config_dir)

    for cfg in configs:
        worker = CameraWorker(config=cfg)
        workers[cfg.camera_id] = worker
        worker.start()
        logger.info("Spawned worker for camera %s (%s)", cfg.camera_id, cfg.name)

    yield

    logger.info("Shutting down Vision Edge camera workers...")
    for cid, worker in list(workers.items()):
        await worker.stop()
        logger.info("Stopped worker for camera %s", cid)
    workers.clear()


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
