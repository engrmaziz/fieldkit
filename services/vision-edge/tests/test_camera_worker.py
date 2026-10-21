"""Integration tests for camera worker lifecycle, decoding, and chaos simulation."""

import asyncio
from pathlib import Path

import pytest
from fieldkit_vision.camera_worker import CameraWorker, load_camera_config_from_yaml
from fieldkit_vision.models import CameraConfig

from scripts.generate_p5_synth_video import generate_plant_clip


@pytest.fixture(scope="module")
def sample_video_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    tmp_dir = tmp_path_factory.mktemp("video_test")
    p = tmp_dir / "test_stream.mp4"
    generate_plant_clip(p, "cam_test_fixture", duration_sec=2.0, fps=25.0)
    return p


@pytest.mark.asyncio
async def test_camera_worker_synthetic_stream(sample_video_path: Path) -> None:
    """Test camera worker successfully ingests and samples a simulated video stream."""
    config = CameraConfig(
        camera_id="cam_synthetic",
        name="Synthetic Plant Test",
        rtsp_url=str(sample_video_path),
        target_fps=5.0,
    )

    worker = CameraWorker(config=config)
    worker.start()

    # Allow worker to process for ~0.8s
    await asyncio.sleep(0.8)

    # Verify connection was established
    assert worker.metrics.is_connected is True
    assert worker.metrics.total_decoded > 0
    assert worker.metrics.total_processed > 0

    # Verify frame packet format
    packet = worker.latest_frame
    assert packet is not None
    assert packet.camera_id == "cam_synthetic"
    assert packet.image is not None
    assert packet.width > 0
    assert packet.height > 0

    # Verify queue has frames ready for downstream consumer
    assert not worker.queue.empty()
    queued_frame = await worker.queue.get()
    assert queued_frame.camera_id == "cam_synthetic"

    await worker.stop()
    assert worker.metrics.is_connected is False


@pytest.mark.asyncio
async def test_camera_worker_chaos_injection(sample_video_path: Path) -> None:
    """Test chaos injection forces periodic disconnect and automatic reconnect."""
    config = CameraConfig(
        camera_id="cam_chaos",
        name="Chaos Injected Camera",
        rtsp_url=str(sample_video_path),
        target_fps=5.0,
    )

    # Set chaos kill interval to 0.3 seconds
    worker = CameraWorker(config=config, chaos_kill_interval_sec=0.3)
    worker.start()

    # Sleep long enough for connection -> chaos kill -> reconnect
    await asyncio.sleep(1.0)

    # Reconnects should have been triggered by chaos termination
    metrics = worker.metrics.get_metrics()
    assert metrics.reconnects >= 1

    await worker.stop()


def test_load_camera_config_from_yaml() -> None:
    """Test loading valid camera config from YAML file."""
    yaml_file = Path("configs/cameras/cam1_press.yaml")
    if yaml_file.exists():
        cfg = load_camera_config_from_yaml(yaml_file)
        assert cfg.camera_id == "cam1_press"
        assert cfg.target_fps == 5.0
        assert len(cfg.zones) >= 1
        assert len(cfg.rules) >= 1
