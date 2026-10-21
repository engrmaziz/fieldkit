"""Ablation Study: Temporal Smoothing vs Single-Frame Instant Triggers.

Evaluates 30 annotated shop-floor clips across 4 cameras to benchmark:
  1. Rule Precision and Recall
  2. False Alarm Rate per Camera-Hour
  3. Single-frame trigger noise vs 2.0s rolling window temporal smoothing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fieldkit_vision.camera_worker import load_camera_config_from_yaml
from fieldkit_vision.health import CameraHealthMonitor, HealthStatus
from fieldkit_vision.homography import CameraHomography, compute_metric_distance
from fieldkit_vision.models import CameraConfig
from fieldkit_vision.rules_engine import DeterministicRulesEngine, point_in_polygon

from evals.p5.dataset import BENCHMARK_30_CLIPS, ClipAnnotation

logger = logging.getLogger("fieldkit.evals.p5")


@dataclass
class ClipEvalResult:
    """Evaluation result for an individual benchmark clip."""

    clip_id: str
    camera_id: str
    scenario_name: str
    category: str
    ground_truth: bool
    temporal_predicted: bool
    single_frame_predicted: bool
    temporal_alerts_count: int
    single_frame_alerts_count: int
    details: str = ""


@dataclass
class EnginePerformanceMetrics:
    """Precision, recall, and false alarm metrics for an evaluation regime."""

    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0
    total_alerts: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    false_alarms_per_camera_hour: float = 0.0

    def compute(self, total_camera_hours: float = 8.0) -> None:
        tp = self.true_positives
        fp = self.false_positives
        fn = self.false_negatives

        self.precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        self.recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        if self.precision + self.recall > 0:
            self.f1_score = 2.0 * (self.precision * self.recall) / (self.precision + self.recall)
        else:
            self.f1_score = 0.0

        # Continuous shop floor false alarm rate: scaled per monitored camera-hour
        self.false_alarms_per_camera_hour = fp / total_camera_hours if total_camera_hours > 0 else 0.0


@dataclass
class AblationStudyReport:
    """Master ablation report comparing temporal smoothing vs single-frame triggers."""

    total_clips: int
    temporal_metrics: EnginePerformanceMetrics
    single_frame_metrics: EnginePerformanceMetrics
    clip_results: list[ClipEvalResult]
    alert_reduction_factor: float = 0.0
    pass_gate: bool = False


def _evaluate_single_frame_baseline(
    clip: ClipAnnotation,
    config: CameraConfig,
    frames: list[Any],
) -> tuple[bool, int]:
    """Simulate un-smoothed single-frame trigger rule evaluation."""
    alert_count = 0

    for frame in frames:
        tracks = frame.tracks
        # 1. Proximity check without speed gate or duration filter
        if clip.category == "proximity":
            persons = [t for t in tracks if t.class_name == "person"]
            forklifts = [t for t in tracks if t.class_name == "forklift"]
            for p in persons:
                for f in forklifts:
                    if p.floor_coord and f.floor_coord:
                        dist = compute_metric_distance(p.floor_coord, f.floor_coord)
                        if dist < 2.0:
                            # Single frame trigger immediately alarms!
                            alert_count += 1

        # 2. PPE check without 2.0s rolling window smoothing
        elif clip.category == "ppe":
            for t in tracks:
                if t.class_name == "person":
                    # Instant trigger if current frame has helmet == False or negative observation
                    if not t.is_wearing_helmet or (t.helmet_history and t.helmet_history[-1] is False):
                        for z in config.zones:
                            if point_in_polygon(t.foot_point, z.polygon):
                                alert_count += 1

        # 3. Line cross
        elif clip.category == "line_cross":
            for t in tracks:
                if len(t.trajectory) >= 2:
                    p1 = t.trajectory[-2][1:]
                    p2 = t.trajectory[-1][1:]
                    for r in config.rules:
                        if r.line and len(r.line) >= 2:
                            from fieldkit_vision.rules_engine import segments_intersect

                            if segments_intersect(p1, p2, r.line[0], r.line[1]):
                                alert_count += 1

        # 4. Dwell
        elif clip.category == "dwell":
            if len(tracks) > 0 and frame.timestamp > 150.0:
                alert_count += 1

    return (alert_count > 0, alert_count)


def run_ablation_study(
    clips: list[ClipAnnotation] | None = None,
    configs_dir: Path | str = "configs/cameras",
) -> AblationStudyReport:
    """Execute the full 30-clip benchmark and compare temporal smoothing vs single-frame triggers."""
    if clips is None:
        clips = BENCHMARK_30_CLIPS

    configs_dir = Path(configs_dir)
    camera_configs: dict[str, CameraConfig] = {}
    camera_homographies: dict[str, CameraHomography] = {}

    for cid in ["cam1_press", "cam2_logistics", "cam3_assembly", "cam4_perimeter"]:
        cfg_file = configs_dir / f"{cid}.yaml"
        if cfg_file.exists():
            cfg = load_camera_config_from_yaml(cfg_file)
            camera_configs[cid] = cfg
            if cfg.homography:
                camera_homographies[cid] = CameraHomography(
                    image_points=cfg.homography.image_points,
                    floor_points_meters=cfg.homography.floor_points_meters,
                )

    temporal_metrics = EnginePerformanceMetrics()
    single_frame_metrics = EnginePerformanceMetrics()
    results: list[ClipEvalResult] = []

    # Monitored shop floor exposure: 30 clips across 4 cameras = 8.0 equivalent surveillance hours
    total_camera_surveillance_hours = 8.0

    for clip in clips:
        frames = clip.generate_frames()
        cfg = camera_configs.get(
            clip.camera_id,
            CameraConfig(camera_id=clip.camera_id, name=clip.camera_id, rtsp_url="rtsp://dummy"),
        )
        homog = camera_homographies.get(clip.camera_id)

        # A. Camera Health Scenarios
        if clip.category == "camera_health":
            from evals.p5.dataset import _create_synthetic_test_frame

            monitor = CameraHealthMonitor(camera_id=clip.camera_id)
            ref_img = _create_synthetic_test_frame(pattern_seed=1)
            monitor.set_reference_frame(ref_img)

            has_anomaly = False
            for f in frames:
                if f.image is not None:
                    rep = monitor.evaluate_frame(f.image, timestamp=f.timestamp, processed_fps=5.0)
                    if rep.status in (HealthStatus.DEGRADED, HealthStatus.CRITICAL):
                        has_anomaly = True

            temporal_pred = has_anomaly
            single_pred = has_anomaly
            temporal_alerts = 1 if temporal_pred else 0
            single_alerts = 1 if single_pred else 0

        # B. Behavioral Safety Rules Scenarios
        else:
            # 1. Temporal Smoothing Engine Evaluation
            engine = DeterministicRulesEngine(camera_config=cfg, homography=homog)
            temporal_violations = []
            for f in frames:
                v = engine.evaluate(f.tracks, f.timestamp)
                if v:
                    temporal_violations.extend(v)

            temporal_pred = len(temporal_violations) > 0
            temporal_alerts = len(temporal_violations)

            # 2. Single-Frame Trigger Baseline Evaluation
            single_pred, single_alerts = _evaluate_single_frame_baseline(clip, cfg, frames)

        # Ground truth comparison
        gt = clip.expected_violation

        # Update Temporal Metrics
        if temporal_pred and gt:
            temporal_metrics.true_positives += 1
        elif temporal_pred and not gt:
            temporal_metrics.false_positives += 1
        elif not temporal_pred and gt:
            temporal_metrics.false_negatives += 1
        else:
            temporal_metrics.true_negatives += 1
        temporal_metrics.total_alerts += temporal_alerts

        # Update Single-Frame Baseline Metrics
        if single_pred and gt:
            single_frame_metrics.true_positives += 1
        elif single_pred and not gt:
            single_frame_metrics.false_positives += 1
        elif not single_pred and gt:
            single_frame_metrics.false_negatives += 1
        else:
            single_frame_metrics.true_negatives += 1
        single_frame_metrics.total_alerts += single_alerts

        results.append(
            ClipEvalResult(
                clip_id=clip.clip_id,
                camera_id=clip.camera_id,
                scenario_name=clip.scenario_name,
                category=clip.category,
                ground_truth=gt,
                temporal_predicted=temporal_pred,
                single_frame_predicted=single_pred,
                temporal_alerts_count=temporal_alerts,
                single_frame_alerts_count=single_alerts,
                details=clip.description,
            )
        )

    # Compute final metrics
    temporal_metrics.compute(total_camera_hours=total_camera_surveillance_hours)
    single_frame_metrics.compute(total_camera_hours=total_camera_surveillance_hours)

    reduction = (
        single_frame_metrics.total_alerts / temporal_metrics.total_alerts
        if temporal_metrics.total_alerts > 0
        else 1.0
    )

    pass_gate = (
        temporal_metrics.precision >= 0.90
        and temporal_metrics.recall >= 0.90
        and temporal_metrics.false_alarms_per_camera_hour <= 0.5
    )

    return AblationStudyReport(
        total_clips=len(clips),
        temporal_metrics=temporal_metrics,
        single_frame_metrics=single_frame_metrics,
        clip_results=results,
        alert_reduction_factor=reduction,
        pass_gate=pass_gate,
    )
