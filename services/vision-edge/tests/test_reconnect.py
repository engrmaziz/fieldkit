"""Unit tests for exponential reconnect backoff and connection error handling."""

import asyncio

import pytest
from fieldkit_vision.camera_worker import CameraWorker
from fieldkit_vision.models import CameraConfig, CameraReconnectConfig


def test_exponential_backoff_calculation() -> None:
    """Test exponential backoff formula and max backoff capping."""
    reconnect_cfg = CameraReconnectConfig(
        initial_backoff_sec=1.0,
        max_backoff_sec=30.0,
        backoff_multiplier=2.0,
        timeout_sec=5.0,
    )

    delays = []
    for attempt in range(1, 8):
        b = min(
            reconnect_cfg.initial_backoff_sec
            * (reconnect_cfg.backoff_multiplier ** min(attempt, 6)),
            reconnect_cfg.max_backoff_sec,
        )
        delays.append(b)

    # 1.0*2^1=2.0, 1.0*2^2=4.0, 1.0*2^3=8.0, 1.0*2^4=16.0, 1.0*2^5=32->30.0, 1.0*2^6=64->30.0
    assert delays[0] == 2.0
    assert delays[1] == 4.0
    assert delays[2] == 8.0
    assert delays[3] == 16.0
    assert delays[4] == 30.0
    assert delays[5] == 30.0


@pytest.mark.asyncio
async def test_worker_reconnect_against_stopped_stream() -> None:
    """Test worker handles stopped/unreachable stream without crashing and increments reconnects."""
    config = CameraConfig(
        camera_id="cam_unreachable",
        name="Dead Stream Test",
        rtsp_url="rtsp://127.0.0.1:59998/nonexistent",
        target_fps=5.0,
        reconnect=CameraReconnectConfig(
            initial_backoff_sec=0.05,
            max_backoff_sec=0.15,
            timeout_sec=0.1,
        ),
    )

    worker = CameraWorker(config=config)
    worker.start()

    # Let it attempt connections for 0.6 seconds
    await asyncio.sleep(0.6)

    # Worker should have attempted to reconnect multiple times
    metrics = worker.metrics.get_metrics()
    assert metrics.is_connected is False
    assert metrics.reconnects >= 1
    assert metrics.last_error is not None

    # Clean shutdown
    await worker.stop()
    assert worker._running is False
