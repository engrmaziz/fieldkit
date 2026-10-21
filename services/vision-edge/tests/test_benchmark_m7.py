"""Unit and integration tests for Project 5 Milestone 7 evaluation benchmark and load testing."""

from __future__ import annotations

import pytest

from evals.p5.dataset import BENCHMARK_30_CLIPS
from evals.p5.eval_rules_ablation import run_ablation_study
from evals.p5.load_test_benchmark import run_sustained_load_test


def test_benchmark_30_clips_dataset_integrity() -> None:
    """Verify 30 annotated benchmark clips dataset structure and metadata."""
    assert len(BENCHMARK_30_CLIPS) == 30

    categories = {c.category for c in BENCHMARK_30_CLIPS}
    assert "proximity" in categories
    assert "ppe" in categories
    assert "line_cross" in categories
    assert "dwell" in categories
    assert "camera_health" in categories

    cameras = {c.camera_id for c in BENCHMARK_30_CLIPS}
    assert "cam1_press" in cameras
    assert "cam2_logistics" in cameras
    assert "cam3_assembly" in cameras
    assert "cam4_perimeter" in cameras

    # Test that each clip generator produces non-empty frames
    for clip in BENCHMARK_30_CLIPS[:5]:
        frames = clip.generate_frames()
        assert len(frames) > 0
        assert frames[0].timestamp > 0.0


def test_ablation_study_execution() -> None:
    """Verify temporal smoothing vs single-frame ablation study benchmark."""
    report = run_ablation_study()

    assert report.total_clips == 30
    assert report.pass_gate is True

    temp_m = report.temporal_metrics
    assert temp_m.precision >= 0.90
    assert temp_m.recall >= 0.90
    assert temp_m.false_alarms_per_camera_hour <= 0.50

    # Single-frame baseline produces significantly more noise
    single_m = report.single_frame_metrics
    assert report.alert_reduction_factor >= 5.0
    assert single_m.total_alerts > temp_m.total_alerts


@pytest.mark.asyncio
async def test_sustained_load_test_execution() -> None:
    """Verify 4-camera concurrent ingestion, backpressure, and latency."""
    res = await run_sustained_load_test(duration_sec=1.5, target_fps=5.0)

    assert res.total_cameras == 4
    assert res.total_frames_processed > 0
    assert res.queue_backpressure_passed is True
    assert res.p95_latency_passed is True
    assert res.all_targets_met is True

    for stat in res.camera_stats:
        assert stat.max_queue_depth <= 4
        assert stat.p95_latency_ms < 1000.0
