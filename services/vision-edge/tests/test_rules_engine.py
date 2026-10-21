"""Unit tests for deterministic safety rules engine, temporal smoothing, and 30s cooldown."""

from __future__ import annotations

from fieldkit_vision.homography import CameraHomography
from fieldkit_vision.models import CameraConfig, RuleConfig, ZoneConfig
from fieldkit_vision.rules_engine import (
    CooldownManager,
    DeterministicRulesEngine,
    point_in_polygon,
    segments_intersect,
)
from fieldkit_vision.tracker import TrackedEntity


def test_point_in_polygon() -> None:
    """Verify 2D ray-casting point-in-polygon spatial containment."""
    poly = [[100, 100], [300, 100], [300, 300], [100, 300]]

    # Point clearly inside
    assert point_in_polygon((200.0, 200.0), poly) is True

    # Point outside
    assert point_in_polygon((50.0, 50.0), poly) is False
    assert point_in_polygon((400.0, 200.0), poly) is False


def test_segments_intersect() -> None:
    """Verify 2D line segment intersection for tripwire/line crossing detection."""
    # Crossing line: horizontal line (100, 200) to (300, 200)
    line = ([100.0, 200.0], [300.0, 200.0])

    # Trajectory moving from top to bottom (200, 150) -> (200, 250)
    traj_cross = ((200.0, 150.0), (200.0, 250.0))
    assert segments_intersect(traj_cross[0], traj_cross[1], line[0], line[1]) is True

    # Trajectory that does not cross line
    traj_no_cross = ((200.0, 50.0), (200.0, 150.0))
    assert segments_intersect(traj_no_cross[0], traj_no_cross[1], line[0], line[1]) is False


def test_cooldown_manager() -> None:
    """Verify 30-second cooldown suppresses repeated alerts for the same track and rule."""
    cd = CooldownManager(default_cooldown_sec=30.0)

    # Initial alert at t=10.0s is allowed
    assert cd.is_in_cooldown("cam1", "rule_helmet", "track_1", timestamp=10.0) is False
    cd.record_alert("cam1", "rule_helmet", "track_1", timestamp=10.0)

    # Immediate follow-up alert at t=15.0s (5s later) is in cooldown
    assert cd.is_in_cooldown("cam1", "rule_helmet", "track_1", timestamp=15.0) is True

    # Alert at t=39.0s (29s later) is still in cooldown
    assert cd.is_in_cooldown("cam1", "rule_helmet", "track_1", timestamp=39.0) is True

    # Alert at t=40.5s (30.5s later) expires cooldown and is allowed
    assert cd.is_in_cooldown("cam1", "rule_helmet", "track_1", timestamp=40.5) is False

    # Different track ID at t=15.0s is NOT in cooldown
    assert cd.is_in_cooldown("cam1", "rule_helmet", "track_2", timestamp=15.0) is False


def test_zone_ppe_missing_rule_temporal_smoothing() -> None:
    """Verify zone_ppe_missing requires >= 70% violation over rolling window (avoiding single-frame flapping)."""
    camera_config = CameraConfig(
        camera_id="cam1_press",
        name="Press Zone",
        rtsp_url="rtsp://dummy",
        zones=[
            ZoneConfig(
                id="zone_press",
                name="Press Danger Bed",
                polygon=[[100, 100], [500, 100], [500, 500], [100, 500]],
                required_ppe=["helmet"],
            )
        ],
        rules=[
            RuleConfig(
                id="rule_press_helmet",
                type="zone_ppe_missing",
                zone_id="zone_press",
                ppe_class="helmet",
                min_violation_ratio=0.70,
                window_sec=2.0,
                cooldown_sec=30.0,
            )
        ],
    )

    engine = DeterministicRulesEngine(camera_config)

    # Worker located inside zone: foot_point=(250, 450)
    worker = TrackedEntity(
        track_id=1,
        camera_id="cam1_press",
        class_id=0,
        class_name="person",
        box=[200.0, 150.0, 300.0, 450.0],
        confidence=0.92,
        window_size=10,
    )

    # Case A: Worker is wearing helmet (8 of 10 observations positive)
    for _ in range(8):
        worker.add_helmet_observation(True, confidence=0.90)
    for _ in range(2):
        worker.add_helmet_observation(False, confidence=0.90)

    # Compliance ratio = 0.80 -> Violation ratio = 0.20 < 0.70
    violations_a = engine.evaluate(tracks=[worker], timestamp=10.0)
    assert len(violations_a) == 0

    # Case B: Worker removes helmet (8 of 10 observations missing)
    for _ in range(8):
        worker.add_helmet_observation(False, confidence=0.92)

    # Compliance ratio = 0.20 -> Violation ratio = 0.80 >= 0.70
    violations_b = engine.evaluate(tracks=[worker], timestamp=10.2)
    assert len(violations_b) == 1
    v = violations_b[0]
    assert v.rule_id == "rule_press_helmet"
    assert v.rule_type == "zone_ppe_missing"
    assert v.track_id == 1
    assert v.severity == "CRITICAL"

    # Case C: Cooldown kicks in for repeat evaluation 2 seconds later
    violations_c = engine.evaluate(tracks=[worker], timestamp=12.2)
    assert len(violations_c) == 0  # In 30s cooldown


def test_forklift_pedestrian_proximity_rule() -> None:
    """Verify metric proximity rule (< 2.0m on floor plane with forklift speed >= 0.5m/s and duration >= 0.6s)."""
    camera_config = CameraConfig(
        camera_id="cam2_logistics",
        name="Logistics Lane",
        rtsp_url="rtsp://dummy",
        rules=[
            RuleConfig(
                id="rule_forklift_prox",
                type="proximity",
                class_a="person",
                class_b="forklift",
                max_distance_meters=2.0,
                min_duration_sec=0.6,
                min_forklift_speed_mps=0.5,
                cooldown_sec=30.0,
            )
        ],
    )

    # 4-point homography calibration (trapezoid to 10m x 15m)
    homog = CameraHomography(
        image_points=[[180.0, 300.0], [1200.0, 300.0], [1400.0, 1000.0], [100.0, 1000.0]],
        floor_points_meters=[[0.0, 0.0], [10.0, 0.0], [10.0, 15.0], [0.0, 15.0]],
    )

    engine = DeterministicRulesEngine(camera_config, homography=homog)

    # Pedestrian standing at floor coordinate (5.0m, 6.0m)
    pedestrian_pixel = homog.floor_to_image((5.0, 6.0))
    pedestrian = TrackedEntity(
        track_id=10,
        camera_id="cam2_logistics",
        class_id=0,
        class_name="person",
        box=[pedestrian_pixel[0] - 20, pedestrian_pixel[1] - 80, pedestrian_pixel[0] + 20, pedestrian_pixel[1]],
        confidence=0.95,
    )

    # Forklift moving towards pedestrian:
    # At t=10.0s: forklift enters proximity zone at (5.0m, 7.5m) -> dist = 1.5m (< 2.0m)
    fl_px_1 = homog.floor_to_image((5.0, 7.5))
    forklift = TrackedEntity(
        track_id=20,
        camera_id="cam2_logistics",
        class_id=4,
        class_name="forklift",
        box=[fl_px_1[0] - 50, fl_px_1[1] - 100, fl_px_1[0] + 50, fl_px_1[1]],
        confidence=0.94,
    )
    forklift.speed_mps = 1.8  # 1.8 m/s > 0.5 m/s

    # Initial frame: duration = 0.0s < 0.6s -> no violation yet (duration threshold filter)
    violations_1 = engine.evaluate(tracks=[pedestrian, forklift], timestamp=10.0)
    assert len(violations_1) == 0

    # At t=10.6s: forklift continues in proximity at (5.0m, 7.0m) -> duration = 0.6s >= 0.6s
    fl_px_2 = homog.floor_to_image((5.0, 7.0))
    forklift.box = [fl_px_2[0] - 50, fl_px_2[1] - 100, fl_px_2[0] + 50, fl_px_2[1]]
    forklift.speed_mps = 1.5

    violations_2 = engine.evaluate(tracks=[pedestrian, forklift], timestamp=10.6)
    assert len(violations_2) == 1
    v = violations_2[0]
    assert v.rule_id == "rule_forklift_prox"
    assert v.track_id in (10, 20)
    assert v.related_track_id in (10, 20)
    assert v.metric_distance is not None
    assert v.metric_distance < 2.0
    assert v.metric_speed is not None
    assert v.metric_speed >= 0.5


def test_dwell_and_line_cross_rules() -> None:
    """Verify zone dwell threshold and line crossing trigger alerts."""
    camera_config = CameraConfig(
        camera_id="cam3_assembly",
        name="Assembly Line",
        rtsp_url="rtsp://dummy",
        zones=[
            ZoneConfig(
                id="zone_workcell",
                name="Workcell",
                polygon=[[0, 0], [1000, 0], [1000, 1000], [0, 1000]],
            )
        ],
        rules=[
            RuleConfig(
                id="rule_dwell",
                type="dwell",
                zone_id="zone_workcell",
                min_dwell_sec=5.0,  # 5s test dwell
                cooldown_sec=30.0,
            ),
            RuleConfig(
                id="rule_line_cross",
                type="line_cross",
                line=[[200, 500], [800, 500]],
                direction="entry",
                cooldown_sec=30.0,
            ),
        ],
    )

    engine = DeterministicRulesEngine(camera_config)

    worker = TrackedEntity(
        track_id=30,
        camera_id="cam3_assembly",
        class_id=0,
        class_name="person",
        box=[450.0, 400.0, 550.0, 480.0],
        confidence=0.90,
    )

    # Step 1: Enters zone at t=0.0s
    v_0 = engine.evaluate(tracks=[worker], timestamp=0.0)
    assert len(v_0) == 0

    # Step 2: Dwell at t=6.0s (dwell=6.0s > 5.0s)
    v_dwell = engine.evaluate(tracks=[worker], timestamp=6.0)
    assert any(v.rule_type == "dwell" for v in v_dwell)

    # Step 3: Line cross: moves from y=480 to y=550 (crossing horizontal line y=500)
    worker.box = [450.0, 500.0, 550.0, 550.0]
    worker.trajectory.append((7.0, 500.0, 550.0))
    v_cross = engine.evaluate(tracks=[worker], timestamp=7.0)
    assert any(v.rule_type == "line_cross" for v in v_cross)
