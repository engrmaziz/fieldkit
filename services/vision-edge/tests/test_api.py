"""Tests for Vision Edge FastAPI service endpoints."""

import httpx
import numpy as np
import pytest
from fieldkit_vision.camera_worker import CameraWorker
from fieldkit_vision.main import app, workers
from fieldkit_vision.models import CameraConfig, FramePacket


@pytest.mark.asyncio
async def test_healthz() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/healthz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "fieldkit-vision-edge"


@pytest.mark.asyncio
async def test_readyz() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/readyz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"


@pytest.mark.asyncio
async def test_metrics_endpoint() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/metrics")
        assert resp.status_code == 200
        assert "vision_camera_" in resp.text or "process_cpu_seconds" in resp.text


@pytest.mark.asyncio
async def test_list_cameras_and_frame() -> None:
    # Inject a mock worker into workers dict
    cfg = CameraConfig(
        camera_id="cam_api_mock",
        name="Mock Camera",
        rtsp_url="rtsp://dummy",
    )
    mock_worker = CameraWorker(config=cfg)
    # Put a dummy frame packet
    dummy_img = np.full((100, 100, 3), 120, dtype=np.uint8)
    mock_worker._latest_frame = FramePacket(
        camera_id="cam_api_mock",
        timestamp=100.0,
        frame_index=1,
        image=dummy_img,
        width=100,
        height=100,
    )
    workers["cam_api_mock"] = mock_worker

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # GET /cameras
        resp = await client.get("/cameras")
        assert resp.status_code == 200
        cams = resp.json()
        assert any(c["camera_id"] == "cam_api_mock" for c in cams)

        # GET /cameras/{id}/metrics
        m_resp = await client.get("/cameras/cam_api_mock/metrics")
        assert m_resp.status_code == 200
        assert m_resp.json()["camera_id"] == "cam_api_mock"

        # GET /cameras/{id}/frame
        f_resp = await client.get("/cameras/cam_api_mock/frame")
        assert f_resp.status_code == 200
        assert f_resp.headers["content-type"] == "image/jpeg"
        assert len(f_resp.content) > 0

    # Cleanup
    del workers["cam_api_mock"]
