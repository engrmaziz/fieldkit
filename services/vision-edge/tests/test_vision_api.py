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


@pytest.mark.asyncio
async def test_camera_homography_and_tracks_endpoints() -> None:
    from fieldkit_vision.homography import CameraHomography
    from fieldkit_vision.main import homographies, trackers

    cfg = CameraConfig(
        camera_id="cam_track_mock",
        name="Mock Track Camera",
        rtsp_url="rtsp://dummy",
    )
    mock_worker = CameraWorker(config=cfg)
    dummy_img = np.full((360, 640, 3), 114, dtype=np.uint8)
    mock_worker._latest_frame = FramePacket(
        camera_id="cam_track_mock",
        timestamp=200.0,
        frame_index=1,
        image=dummy_img,
        width=640,
        height=360,
    )
    workers["cam_track_mock"] = mock_worker

    # Provide homography calibration
    img_pts = [[0.0, 0.0], [640.0, 0.0], [640.0, 360.0], [0.0, 360.0]]
    flr_pts = [[0.0, 0.0], [10.0, 0.0], [10.0, 15.0], [0.0, 15.0]]
    homographies["cam_track_mock"] = CameraHomography(img_pts, flr_pts)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Test GET /cameras/{id}/homography
        h_resp = await client.get("/cameras/cam_track_mock/homography")
        assert h_resp.status_code == 200
        h_data = h_resp.json()
        assert h_data["configured"] is True
        assert len(h_data["matrix"]) == 3

        # Test GET /cameras/{id}/tracks
        t_resp = await client.get("/cameras/cam_track_mock/tracks")
        assert t_resp.status_code == 200
        t_data = t_resp.json()
        assert isinstance(t_data, list)
        # Verify tracked entities have expected schema if any
        if t_data:
            assert "track_id" in t_data[0]
            assert "is_wearing_helmet" in t_data[0]
            assert "floor_coord" in t_data[0]

    # Cleanup
    del workers["cam_track_mock"]
    if "cam_track_mock" in homographies:
        del homographies["cam_track_mock"]
    if "cam_track_mock" in trackers:
        del trackers["cam_track_mock"]


@pytest.mark.asyncio
async def test_events_and_evaluate_endpoints() -> None:
    from fieldkit_vision.events import VisionEvent
    from fieldkit_vision.main import recent_events

    # Seed mock event into recent_events
    test_evt = VisionEvent(
        camera_id="cam1_press",
        plant_id="DE-HAM",
        rule_id="rule_press_helmet",
        rule_type="zone_ppe_missing",
        severity="CRITICAL",
        track_id=42,
    )
    recent_events.append(test_evt)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # GET /events
        resp = await client.get("/events")
        assert resp.status_code == 200
        events = resp.json()
        assert len(events) >= 1
        assert any(e["track_id"] == 42 for e in events)

        # GET /events with filter
        filt_resp = await client.get("/events?camera_id=cam1_press&severity=CRITICAL")
        assert filt_resp.status_code == 200
        filt_events = filt_resp.json()
        assert all(e["camera_id"] == "cam1_press" for e in filt_events)


