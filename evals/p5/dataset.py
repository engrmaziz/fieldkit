"""Benchmark dataset of 30 annotated synthetic video clips representing factory shop-floor scenarios.

Used for rigorous evaluation of deterministic safety rules, temporal smoothing vs single-frame triggers,
cross-camera Re-ID, and edge camera health monitoring at Halden Industrie (DE-HAM).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
from fieldkit_vision.tracker import TrackedEntity


@dataclass
class ClipFrameData:
    """Frame payload for synthetic clip evaluation."""

    timestamp: float
    tracks: list[TrackedEntity]
    image: np.ndarray | None = None


@dataclass
class ClipAnnotation:
    """Ground truth annotation and frame generator for a benchmark scenario."""

    clip_id: str
    camera_id: str
    scenario_name: str
    category: str  # "proximity", "ppe", "line_cross", "dwell", "camera_health"
    duration_sec: float
    fps: float
    expected_violation: bool
    expected_rule_type: str | None
    description: str
    generate_frames: Callable[[], list[ClipFrameData]] = field(repr=False)


def _create_blank_image(intensity: int = 120, noise: bool = True) -> np.ndarray:
    """Generate synthetic 640x480 frame with specified mean intensity."""
    img = np.full((480, 640, 3), intensity, dtype=np.uint8)
    if noise:
        noise_mat = np.random.randint(-15, 15, (480, 640, 3), dtype=np.int16)
        img = np.clip(img.astype(np.int16) + noise_mat, 0, 255).astype(np.uint8)
    return img


def _create_synthetic_test_frame(pattern_seed: int = 1) -> np.ndarray:
    """Generate realistic synthetic factory scene frame with textured corners for ORB tracking."""
    import cv2

    np.random.seed(pattern_seed)
    img = np.full((480, 640, 3), 120, dtype=np.uint8)
    cv2.rectangle(img, (50, 50), (250, 350), (120, 200, 80), -1)
    cv2.circle(img, (450, 240), 120, (50, 100, 220), -1)
    cv2.putText(
        img,
        "HALDEN DE-HAM PRESS 01",
        (100, 420),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (255, 255, 255),
        2,
    )
    for _ in range(100):
        x = int(np.random.randint(0, 640))
        y = int(np.random.randint(0, 480))
        cv2.circle(img, (x, y), 3, (255, 255, 0), -1)
    return img


def _create_synthetic_dataset_30_clips() -> list[ClipAnnotation]:
    """Build the standardized 30-clip benchmark suite for Project 5."""
    clips: list[ClipAnnotation] = []

    # -------------------------------------------------------------
    # 1. Proximity Scenarios (Clips 01 - 10)
    # -------------------------------------------------------------

    def gen_clip_01() -> list[ClipFrameData]:
        # Critical proximity: Forklift approaching pedestrian within 1.35m at 1.4 m/s for 1.2s (6 frames @ 5fps)
        frames = []
        for i in range(15):
            ts = 100.0 + i * 0.2
            # Person at floor coord (10.0, 5.0)
            p = TrackedEntity(1, "cam2_logistics", 0, "person", [200, 200, 250, 320], 0.95, ts)
            p.floor_coord = (10.0, 5.0)
            # Forklift moves closer: at frame 5-11, dist = 1.35m, speed = 1.4 m/s
            fl_x = 10.0 + (1.35 if i >= 5 and i <= 11 else 3.5)
            f = TrackedEntity(2, "cam2_logistics", 4, "forklift", [350, 200, 500, 350], 0.96, ts)
            f.floor_coord = (fl_x, 5.0)
            f.speed_mps = 1.4 if i >= 5 else 0.8
            frames.append(ClipFrameData(ts, [p, f]))
        return frames

    clips.append(
        ClipAnnotation(
            clip_id="clip_01",
            camera_id="cam2_logistics",
            scenario_name="Forklift-Pedestrian Overtake in Corridor",
            category="proximity",
            duration_sec=3.0,
            fps=5.0,
            expected_violation=True,
            expected_rule_type="proximity",
            description="Forklift approaches within 1.35m at 1.4 m/s for 1.2s",
            generate_frames=gen_clip_01,
        )
    )

    def gen_clip_02() -> list[ClipFrameData]:
        # Critical proximity: Fast forklift crossing path within 1.15m at 1.8 m/s for 0.8s
        frames = []
        for i in range(15):
            ts = 105.0 + i * 0.2
            p = TrackedEntity(10, "cam2_logistics", 0, "person", [180, 210, 230, 330], 0.94, ts)
            p.floor_coord = (12.0, 6.0)
            f_dist = 1.15 if 4 <= i <= 8 else 3.8
            f = TrackedEntity(20, "cam2_logistics", 4, "forklift", [300, 210, 480, 360], 0.97, ts)
            f.floor_coord = (12.0 + f_dist, 6.0)
            f.speed_mps = 1.8
            frames.append(ClipFrameData(ts, [p, f]))
        return frames

    clips.append(
        ClipAnnotation(
            clip_id="clip_02",
            camera_id="cam2_logistics",
            scenario_name="Fast Forklift Corridor Intersection Crossing",
            category="proximity",
            duration_sec=3.0,
            fps=5.0,
            expected_violation=True,
            expected_rule_type="proximity",
            description="Forklift breaches 1.15m separation at 1.8 m/s for 0.8s",
            generate_frames=gen_clip_02,
        )
    )

    def gen_clip_03() -> list[ClipFrameData]:
        # Critical proximity: Forklift reversing towards stationary technician (1.4m for 1.0s)
        frames = []
        for i in range(15):
            ts = 110.0 + i * 0.2
            p = TrackedEntity(12, "cam2_logistics", 0, "person", [220, 250, 270, 370], 0.96, ts)
            p.floor_coord = (6.0, 10.0)
            f_dist = 1.40 if 5 <= i <= 10 else 3.2
            f = TrackedEntity(22, "cam2_logistics", 4, "forklift", [350, 240, 500, 380], 0.95, ts)
            f.floor_coord = (6.0, 10.0 + f_dist)
            f.speed_mps = 1.1
            frames.append(ClipFrameData(ts, [p, f]))
        return frames

    clips.append(
        ClipAnnotation(
            clip_id="clip_03",
            camera_id="cam2_logistics",
            scenario_name="Forklift Reversing Toward Press Die Worker",
            category="proximity",
            duration_sec=3.0,
            fps=5.0,
            expected_violation=True,
            expected_rule_type="proximity",
            description="Forklift reverses within 1.40m at 1.1 m/s for 1.0s",
            generate_frames=gen_clip_03,
        )
    )

    def gen_clip_04() -> list[ClipFrameData]:
        # Critical proximity: Blind corner near-miss (1.25m at 1.3 m/s for 0.8s)
        frames = []
        for i in range(15):
            ts = 115.0 + i * 0.2
            p = TrackedEntity(14, "cam2_logistics", 0, "person", [200, 200, 250, 320], 0.95, ts)
            p.floor_coord = (14.0, 8.0)
            f_dist = 1.25 if 3 <= i <= 7 else 4.0
            f = TrackedEntity(24, "cam2_logistics", 4, "forklift", [320, 210, 470, 360], 0.96, ts)
            f.floor_coord = (14.0 + f_dist, 8.0)
            f.speed_mps = 1.3
            frames.append(ClipFrameData(ts, [p, f]))
        return frames

    clips.append(
        ClipAnnotation(
            clip_id="clip_04",
            camera_id="cam2_logistics",
            scenario_name="Blind Corner Forklift Pedestrian Conflict",
            category="proximity",
            duration_sec=3.0,
            fps=5.0,
            expected_violation=True,
            expected_rule_type="proximity",
            description="Blind corner encounter at 1.25m, speed 1.3 m/s for 0.8s",
            generate_frames=gen_clip_04,
        )
    )

    def gen_clip_05() -> list[ClipFrameData]:
        # Critical proximity: Proximity breach in Stamping Lane (1.55m at 0.9 m/s for 1.2s)
        frames = []
        for i in range(15):
            ts = 120.0 + i * 0.2
            p = TrackedEntity(16, "cam2_logistics", 0, "person", [200, 300, 250, 420], 0.93, ts)
            p.floor_coord = (7.0, 11.0)
            f_dist = 1.55 if 4 <= i <= 10 else 3.5
            f = TrackedEntity(26, "cam2_logistics", 4, "forklift", [350, 290, 520, 440], 0.95, ts)
            f.floor_coord = (7.0 + f_dist, 11.0)
            f.speed_mps = 0.9
            frames.append(ClipFrameData(ts, [p, f]))
        return frames

    clips.append(
        ClipAnnotation(
            clip_id="clip_05",
            camera_id="cam2_logistics",
            scenario_name="Stamping Supply Lane Proximity Breach",
            category="proximity",
            duration_sec=3.0,
            fps=5.0,
            expected_violation=True,
            expected_rule_type="proximity",
            description="Forklift approaches worker at 1.55m, speed 0.9 m/s for 1.2s",
            generate_frames=gen_clip_05,
        )
    )

    def gen_clip_06() -> list[ClipFrameData]:
        # Critical proximity: Sustained close-quarters following (1.45m at 1.1 m/s for 1.4s)
        frames = []
        for i in range(15):
            ts = 125.0 + i * 0.2
            p = TrackedEntity(18, "cam2_logistics", 0, "person", [210, 220, 260, 340], 0.95, ts)
            p.floor_coord = (15.0, 9.0)
            f_dist = 1.45 if 3 <= i <= 10 else 3.6
            f = TrackedEntity(28, "cam2_logistics", 4, "forklift", [340, 220, 490, 370], 0.98, ts)
            f.floor_coord = (15.0, 9.0 + f_dist)
            f.speed_mps = 1.1
            frames.append(ClipFrameData(ts, [p, f]))
        return frames

    clips.append(
        ClipAnnotation(
            clip_id="clip_06",
            camera_id="cam2_logistics",
            scenario_name="Close-Quarters Following in High-Bay Aisle",
            category="proximity",
            duration_sec=3.0,
            fps=5.0,
            expected_violation=True,
            expected_rule_type="proximity",
            description="Forklift trailing worker at 1.45m for 1.4s at 1.1 m/s",
            generate_frames=gen_clip_06,
        )
    )

    def gen_clip_07() -> list[ClipFrameData]:
        # Safe Passage: Forklift maintains 3.2m separation distance throughout
        frames = []
        for i in range(15):
            ts = 130.0 + i * 0.2
            p = TrackedEntity(30, "cam2_logistics", 0, "person", [200, 200, 250, 320], 0.95, ts)
            p.floor_coord = (10.0, 5.0)
            f = TrackedEntity(40, "cam2_logistics", 4, "forklift", [500, 200, 650, 350], 0.96, ts)
            f.floor_coord = (13.2, 5.0)  # 3.2m away
            f.speed_mps = 1.5
            frames.append(ClipFrameData(ts, [p, f]))
        return frames

    clips.append(
        ClipAnnotation(
            clip_id="clip_07",
            camera_id="cam2_logistics",
            scenario_name="Safe Forklift Corridor Transit (>3.0m)",
            category="proximity",
            duration_sec=3.0,
            fps=5.0,
            expected_violation=False,
            expected_rule_type=None,
            description="Forklift passes with safe 3.2m separation",
            generate_frames=gen_clip_07,
        )
    )

    def gen_clip_08() -> list[ClipFrameData]:
        # Stationary Forklift: Distance 1.1m but forklift speed is 0.0 m/s (engine parked/off)
        frames = []
        for i in range(15):
            ts = 135.0 + i * 0.2
            p = TrackedEntity(32, "cam2_logistics", 0, "person", [200, 200, 250, 320], 0.95, ts)
            p.floor_coord = (10.0, 5.0)
            f = TrackedEntity(42, "cam2_logistics", 4, "forklift", [320, 200, 470, 350], 0.96, ts)
            f.floor_coord = (11.1, 5.0)  # 1.1m away
            f.speed_mps = 0.0  # Stopped!
            frames.append(ClipFrameData(ts, [p, f]))
        return frames

    clips.append(
        ClipAnnotation(
            clip_id="clip_08",
            camera_id="cam2_logistics",
            scenario_name="Worker Walking Beside Parked Stationary Forklift",
            category="proximity",
            duration_sec=3.0,
            fps=5.0,
            expected_violation=False,
            expected_rule_type=None,
            description="Forklift parked (0.0 m/s); proximity speed gate prevents false alarm",
            generate_frames=gen_clip_08,
        )
    )

    def gen_clip_09() -> list[ClipFrameData]:
        # Momentary Transient Blip: Distance < 2.0m for only 1 frame (0.2s duration < 0.6s min)
        frames = []
        for i in range(15):
            ts = 140.0 + i * 0.2
            p = TrackedEntity(34, "cam2_logistics", 0, "person", [200, 200, 250, 320], 0.95, ts)
            p.floor_coord = (10.0, 5.0)
            # Only frame 5 is close
            dist = 1.3 if i == 5 else 3.5
            f = TrackedEntity(44, "cam2_logistics", 4, "forklift", [350, 200, 500, 350], 0.96, ts)
            f.floor_coord = (10.0 + dist, 5.0)
            f.speed_mps = 1.2
            frames.append(ClipFrameData(ts, [p, f]))
        return frames

    clips.append(
        ClipAnnotation(
            clip_id="clip_09",
            camera_id="cam2_logistics",
            scenario_name="Single-Frame Perspective Glitch / Transience",
            category="proximity",
            duration_sec=3.0,
            fps=5.0,
            expected_violation=False,
            expected_rule_type=None,
            description="Brief 0.2s perspective overlap; duration filter prevents false alarm",
            generate_frames=gen_clip_09,
        )
    )

    def gen_clip_10() -> list[ClipFrameData]:
        # Forklift in dedicated lane separated by 4.5m
        frames = []
        for i in range(15):
            ts = 145.0 + i * 0.2
            p = TrackedEntity(36, "cam1_press", 0, "person", [150, 450, 200, 580], 0.95, ts)
            p.floor_coord = (4.0, 12.0)
            f = TrackedEntity(46, "cam1_press", 4, "forklift", [550, 250, 720, 390], 0.96, ts)
            f.floor_coord = (8.5, 12.0)  # 4.5m away
            f.speed_mps = 1.4
            frames.append(ClipFrameData(ts, [p, f]))
        return frames

    clips.append(
        ClipAnnotation(
            clip_id="clip_10",
            camera_id="cam1_press",
            scenario_name="Dedicated Forklift Transit Lane Safe Passage",
            category="proximity",
            duration_sec=3.0,
            fps=5.0,
            expected_violation=False,
            expected_rule_type=None,
            description="Safe 4.5m separation between pedestrian walkway and forklift lane",
            generate_frames=gen_clip_10,
        )
    )

    # -------------------------------------------------------------
    # 2. PPE Compliance Scenarios (Clips 11 - 20)
    # -------------------------------------------------------------

    def gen_clip_11() -> list[ClipFrameData]:
        # True Violation: Worker in Press Bed Zone without hard hat for 12 frames (2.4s)
        frames = []
        for i in range(15):
            ts = 200.0 + i * 0.2
            # Foot point [350, 450] inside press bed danger zone
            p = TrackedEntity(50, "cam1_press", 0, "person", [300, 350, 400, 450], 0.95, ts)
            # 12 frames without helmet
            if i >= 3:
                for _ in range(8):
                    p.helmet_history.append(False)
                p.is_wearing_helmet = False
            else:
                p.helmet_history.append(True)
                p.is_wearing_helmet = True
            frames.append(ClipFrameData(ts, [p]))
        return frames

    clips.append(
        ClipAnnotation(
            clip_id="clip_11",
            camera_id="cam1_press",
            scenario_name="Press Bed Operator Sustained Missing Helmet",
            category="ppe",
            duration_sec=3.0,
            fps=5.0,
            expected_violation=True,
            expected_rule_type="zone_ppe_missing",
            description="Worker in press bed without helmet for 2.4s (>70% window)",
            generate_frames=gen_clip_11,
        )
    )

    def gen_clip_12() -> list[ClipFrameData]:
        # True Violation: Worker removes helmet in Press Bed Zone for 14 frames (2.8s)
        frames = []
        for i in range(15):
            ts = 205.0 + i * 0.2
            # Inside press bed danger zone [450, 500, 550, 650]
            p = TrackedEntity(52, "cam1_press", 0, "person", [450, 500, 550, 650], 0.95, ts)
            for _ in range(9):
                p.helmet_history.append(False)
            p.is_wearing_helmet = False
            frames.append(ClipFrameData(ts, [p]))
        return frames

    clips.append(
        ClipAnnotation(
            clip_id="clip_12",
            camera_id="cam1_press",
            scenario_name="Assembly Enclosure Helmet Removal",
            category="ppe",
            duration_sec=3.0,
            fps=5.0,
            expected_violation=True,
            expected_rule_type="zone_ppe_missing",
            description="Worker removes helmet inside mandatory press zone for 2.8s",
            generate_frames=gen_clip_12,
        )
    )

    def gen_clip_13() -> list[ClipFrameData]:
        # True Violation: Stamping tooling setup without hard hat for 10 frames (2.0s)
        frames = []
        for i in range(15):
            ts = 210.0 + i * 0.2
            p = TrackedEntity(54, "cam1_press", 0, "person", [320, 360, 410, 460], 0.94, ts)
            for _ in range(8):
                p.helmet_history.append(False)
            p.is_wearing_helmet = False
            frames.append(ClipFrameData(ts, [p]))
        return frames

    clips.append(
        ClipAnnotation(
            clip_id="clip_13",
            camera_id="cam1_press",
            scenario_name="Stamping Tooling Setup Missing Hard Hat",
            category="ppe",
            duration_sec=3.0,
            fps=5.0,
            expected_violation=True,
            expected_rule_type="zone_ppe_missing",
            description="Tooling technician unequipped inside danger zone for 2.0s",
            generate_frames=gen_clip_13,
        )
    )

    def gen_clip_14() -> list[ClipFrameData]:
        # True Violation: Contractor entering press bay unequipped for 11 frames (2.2s)
        frames = []
        for i in range(15):
            ts = 215.0 + i * 0.2
            p = TrackedEntity(56, "cam1_press", 0, "person", [450, 500, 550, 650], 0.96, ts)
            for _ in range(8):
                p.helmet_history.append(False)
            p.is_wearing_helmet = False
            frames.append(ClipFrameData(ts, [p]))
        return frames

    clips.append(
        ClipAnnotation(
            clip_id="clip_14",
            camera_id="cam1_press",
            scenario_name="Contractor Entering Assembly Line Without PPE",
            category="ppe",
            duration_sec=3.0,
            fps=5.0,
            expected_violation=True,
            expected_rule_type="zone_ppe_missing",
            description="Contractor enters press danger zone without safety helmet",
            generate_frames=gen_clip_14,
        )
    )

    def gen_clip_15() -> list[ClipFrameData]:
        # True Violation: Press bed die maintenance worker helmet removed for 15 frames (3.0s)
        frames = []
        for i in range(15):
            ts = 220.0 + i * 0.2
            p = TrackedEntity(58, "cam1_press", 0, "person", [340, 370, 420, 470], 0.97, ts)
            for _ in range(10):
                p.helmet_history.append(False)
            p.is_wearing_helmet = False
            frames.append(ClipFrameData(ts, [p]))
        return frames

    clips.append(
        ClipAnnotation(
            clip_id="clip_15",
            camera_id="cam1_press",
            scenario_name="Press Bed Die Inspection Missing PPE",
            category="ppe",
            duration_sec=3.0,
            fps=5.0,
            expected_violation=True,
            expected_rule_type="zone_ppe_missing",
            description="Worker inspecting hydraulic press die with helmet completely off",
            generate_frames=gen_clip_15,
        )
    )

    def gen_clip_16() -> list[ClipFrameData]:
        # Compliant: Worker wearing hard hat 100% of time
        frames = []
        for i in range(15):
            ts = 225.0 + i * 0.2
            p = TrackedEntity(60, "cam1_press", 0, "person", [300, 350, 400, 450], 0.95, ts)
            for _ in range(10):
                p.helmet_history.append(True)
            p.is_wearing_helmet = True
            frames.append(ClipFrameData(ts, [p]))
        return frames

    clips.append(
        ClipAnnotation(
            clip_id="clip_16",
            camera_id="cam1_press",
            scenario_name="Fully Compliant Press Operator",
            category="ppe",
            duration_sec=3.0,
            fps=5.0,
            expected_violation=False,
            expected_rule_type=None,
            description="Worker consistently wears required safety helmet in press zone",
            generate_frames=gen_clip_16,
        )
    )

    def gen_clip_17() -> list[ClipFrameData]:
        # Momentary Head Turn / Occlusion: 2 frames negative out of 10 (0.4s < 2.0s threshold)
        frames = []
        for i in range(15):
            ts = 230.0 + i * 0.2
            p = TrackedEntity(62, "cam1_press", 0, "person", [300, 350, 400, 450], 0.95, ts)
            # Only frames 6 and 7 show negative (head tilted down), rest positive (80% compliance)
            for _ in range(8):
                p.helmet_history.append(True)
            p.helmet_history.append(False)
            p.helmet_history.append(False)
            p.is_wearing_helmet = i not in (6, 7)
            frames.append(ClipFrameData(ts, [p]))
        return frames

    clips.append(
        ClipAnnotation(
            clip_id="clip_17",
            camera_id="cam1_press",
            scenario_name="Operator Head-Turn Occlusion Flicker",
            category="ppe",
            duration_sec=3.0,
            fps=5.0,
            expected_violation=False,
            expected_rule_type=None,
            description="Brief 0.4s head tilt; temporal smoothing suppresses false alarm",
            generate_frames=gen_clip_17,
        )
    )

    def gen_clip_18() -> list[ClipFrameData]:
        # Worker wipes forehead: Helmet lifted for 2 frames (0.4s), then immediately replaced
        frames = []
        for i in range(15):
            ts = 235.0 + i * 0.2
            p = TrackedEntity(64, "cam1_press", 0, "person", [450, 500, 550, 650], 0.95, ts)
            # 8 positive, 2 negative -> 80% compliance
            for _ in range(8):
                p.helmet_history.append(True)
            p.helmet_history.append(False)
            p.helmet_history.append(False)
            p.is_wearing_helmet = i not in (4, 5)
            frames.append(ClipFrameData(ts, [p]))
        return frames

    clips.append(
        ClipAnnotation(
            clip_id="clip_18",
            camera_id="cam1_press",
            scenario_name="Worker Forehead Wipe Adjustment",
            category="ppe",
            duration_sec=3.0,
            fps=5.0,
            expected_violation=False,
            expected_rule_type=None,
            description="Transient 0.4s helmet adjustment; temporal smoothing prevents alert",
            generate_frames=gen_clip_18,
        )
    )

    def gen_clip_19() -> list[ClipFrameData]:
        # Shadow flicker: Single-frame detector miss due to lighting variation
        frames = []
        for i in range(15):
            ts = 240.0 + i * 0.2
            p = TrackedEntity(66, "cam1_press", 0, "person", [300, 350, 400, 450], 0.95, ts)
            for _ in range(9):
                p.helmet_history.append(True)
            p.helmet_history.append(False)
            p.is_wearing_helmet = i != 8
            frames.append(ClipFrameData(ts, [p]))
        return frames

    clips.append(
        ClipAnnotation(
            clip_id="clip_19",
            camera_id="cam1_press",
            scenario_name="Overhead Lighting Shadow Detector Flicker",
            category="ppe",
            duration_sec=3.0,
            fps=5.0,
            expected_violation=False,
            expected_rule_type=None,
            description="Single-frame detector shadow artifact; 2s rolling window filters noise",
            generate_frames=gen_clip_19,
        )
    )

    def gen_clip_20() -> list[ClipFrameData]:
        # Worker outside danger zone: Inside walkway corridor where helmet is not required
        frames = []
        for i in range(15):
            ts = 245.0 + i * 0.2
            # Foot point [100, 100] is outside press bed danger zone
            p = TrackedEntity(68, "cam1_press", 0, "person", [80, 50, 140, 100], 0.95, ts)
            p.is_wearing_helmet = False
            frames.append(ClipFrameData(ts, [p]))
        return frames

    clips.append(
        ClipAnnotation(
            clip_id="clip_20",
            camera_id="cam1_press",
            scenario_name="Worker in Non-Hazard Pedestrian Corridor",
            category="ppe",
            duration_sec=3.0,
            fps=5.0,
            expected_violation=False,
            expected_rule_type=None,
            description="Worker without helmet in safe walkway; polygon containment filters alert",
            generate_frames=gen_clip_20,
        )
    )

    # -------------------------------------------------------------
    # 3. Line Crossing & Dwell Scenarios (Clips 21 - 25)
    # -------------------------------------------------------------

    def gen_clip_21() -> list[ClipFrameData]:
        # True Violation: Worker crossing perimeter boundary line [500, 600] -> [1400, 600]
        frames = []
        for i in range(15):
            ts = 300.0 + i * 0.2
            # Moves from y=560 (top) to y=644 (bottom) crossing line at y=600 with x=800
            y = 560 + i * 6
            p = TrackedEntity(70, "cam4_perimeter", 0, "person", [760, y - 60, 840, y], 0.95, ts)
            if i > 0:
                p.trajectory.append((ts - 0.2, 800.0, float(y - 6)))
            p.trajectory.append((ts, 800.0, float(y)))
            frames.append(ClipFrameData(ts, [p]))
        return frames

    clips.append(
        ClipAnnotation(
            clip_id="clip_21",
            camera_id="cam4_perimeter",
            scenario_name="Perimeter Boundary Intrusion",
            category="line_cross",
            duration_sec=3.0,
            fps=5.0,
            expected_violation=True,
            expected_rule_type="line_cross",
            description="Pedestrian trajectory intersects facility perimeter tripwire",
            generate_frames=gen_clip_21,
        )
    )

    def gen_clip_22() -> list[ClipFrameData]:
        # True Violation: Unauthorized night shift gate crossing
        frames = []
        for i in range(15):
            ts = 305.0 + i * 0.2
            y = 560 + i * 7
            p = TrackedEntity(72, "cam4_perimeter", 0, "person", [860, y - 60, 940, y], 0.96, ts)
            if i > 0:
                p.trajectory.append((ts - 0.2, 900.0, float(y - 7)))
            p.trajectory.append((ts, 900.0, float(y)))
            frames.append(ClipFrameData(ts, [p]))
        return frames

    clips.append(
        ClipAnnotation(
            clip_id="clip_22",
            camera_id="cam4_perimeter",
            scenario_name="North Security Gate Tripwire Breach",
            category="line_cross",
            duration_sec=3.0,
            fps=5.0,
            expected_violation=True,
            expected_rule_type="line_cross",
            description="Person crosses perimeter boundary tripwire outside operational window",
            generate_frames=gen_clip_22,
        )
    )

    def gen_clip_23() -> list[ClipFrameData]:
        # True Violation: Worker loitering in assembly conveyor zone for 210s (>120s threshold)
        frames = []
        for i in range(15):
            ts = 310.0 + i * 15.0  # Simulated 210s window (>120s dwell)
            p = TrackedEntity(74, "cam3_assembly", 0, "person", [600, 450, 700, 550], 0.95, ts)
            frames.append(ClipFrameData(ts, [p]))
        return frames

    clips.append(
        ClipAnnotation(
            clip_id="clip_23",
            camera_id="cam3_assembly",
            scenario_name="Assembly Staging Zone Excess Dwell",
            category="dwell",
            duration_sec=210.0,
            fps=5.0,
            expected_violation=True,
            expected_rule_type="dwell",
            description="Worker dwells in assembly conveyor buffer exceeding 120s limit",
            generate_frames=gen_clip_23,
        )
    )

    def gen_clip_24() -> list[ClipFrameData]:
        # Walking parallel to boundary: Foot point y=520 constantly (never crosses y=600)
        frames = []
        for i in range(15):
            ts = 315.0 + i * 0.2
            x = 600 + i * 15
            p = TrackedEntity(76, "cam4_perimeter", 0, "person", [x, 460, x + 50, 520], 0.95, ts)
            p.trajectory.append((ts, float(x + 25), 520.0))
            frames.append(ClipFrameData(ts, [p]))
        return frames

    clips.append(
        ClipAnnotation(
            clip_id="clip_24",
            camera_id="cam4_perimeter",
            scenario_name="Worker Walking Parallel to Perimeter Fence",
            category="line_cross",
            duration_sec=3.0,
            fps=5.0,
            expected_violation=False,
            expected_rule_type=None,
            description="Person moves parallel to boundary line without crossing",
            generate_frames=gen_clip_24,
        )
    )

    def gen_clip_25() -> list[ClipFrameData]:
        # Normal transit: Worker in zone for 20s (<120s dwell limit)
        frames = []
        for i in range(15):
            ts = 320.0 + i * 1.5  # 21s total (<120s dwell)
            p = TrackedEntity(78, "cam3_assembly", 0, "person", [600, 450, 700, 550], 0.95, ts)
            frames.append(ClipFrameData(ts, [p]))
        return frames

    clips.append(
        ClipAnnotation(
            clip_id="clip_25",
            camera_id="cam3_assembly",
            scenario_name="Normal Workstation Transit (30s)",
            category="dwell",
            duration_sec=30.0,
            fps=5.0,
            expected_violation=False,
            expected_rule_type=None,
            description="Standard transit through assembly cell well below loitering threshold",
            generate_frames=gen_clip_25,
        )
    )

    # -------------------------------------------------------------
    # 4. Camera Health Diagnostic Scenarios (Clips 26 - 30)
    # -------------------------------------------------------------

    def gen_clip_26() -> list[ClipFrameData]:
        # Frozen Stream: Consecutive frame diff is 0.0 for >10s duration
        frozen_img = _create_synthetic_test_frame(pattern_seed=1)
        return [ClipFrameData(400.0 + i * 1.0, [], frozen_img) for i in range(15)]

    clips.append(
        ClipAnnotation(
            clip_id="clip_26",
            camera_id="cam1_press",
            scenario_name="Frozen RTSP Video Stream Ingestion",
            category="camera_health",
            duration_sec=14.0,
            fps=5.0,
            expected_violation=True,
            expected_rule_type="camera_health_frozen",
            description="Identical frames with mean difference < 1.0 for 14s triggering freeze diagnostic",
            generate_frames=gen_clip_26,
        )
    )

    def gen_clip_27() -> list[ClipFrameData]:
        # Black / Covered Frame: Mean intensity = 0.0 (< 15.0 threshold)
        black_img = np.zeros((480, 640, 3), dtype=np.uint8)
        return [ClipFrameData(405.0 + i * 0.2, [], black_img) for i in range(15)]

    clips.append(
        ClipAnnotation(
            clip_id="clip_27",
            camera_id="cam2_logistics",
            scenario_name="Camera Lens Occlusion / Total Blackout",
            category="camera_health",
            duration_sec=3.0,
            fps=5.0,
            expected_violation=True,
            expected_rule_type="camera_health_black",
            description="Mean pixel brightness drops below 15.0 triggering occlusion alert",
            generate_frames=gen_clip_27,
        )
    )

    def gen_clip_28() -> list[ClipFrameData]:
        # Defocus Blur: Gaussian blurred frame causing Laplacian variance < 20.0
        import cv2

        base = _create_synthetic_test_frame(pattern_seed=1)
        blurred = cv2.GaussianBlur(base, (51, 51), 20.0)
        return [ClipFrameData(410.0 + i * 0.2, [], blurred) for i in range(15)]

    clips.append(
        ClipAnnotation(
            clip_id="clip_28",
            camera_id="cam3_assembly",
            scenario_name="Severe Lens Smear / Defocus Blur",
            category="camera_health",
            duration_sec=3.0,
            fps=5.0,
            expected_violation=True,
            expected_rule_type="camera_health_blur",
            description="Laplacian variance drops below 50.0 triggering defocus diagnostic",
            generate_frames=gen_clip_28,
        )
    )

    def gen_clip_29() -> list[ClipFrameData]:
        # Physical Camera View Shift: Tampered angle (low ORB feature inliers vs reference)
        import cv2

        shifted = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.rectangle(shifted, (300, 300), (600, 450), (200, 50, 50), -1)
        for _ in range(50):
            cv2.circle(
                shifted,
                (int(np.random.randint(0, 640)), int(np.random.randint(0, 480))),
                2,
                (0, 255, 255),
                -1,
            )
        return [ClipFrameData(415.0 + i * 0.2, [], shifted) for i in range(15)]

    clips.append(
        ClipAnnotation(
            clip_id="clip_29",
            camera_id="cam4_perimeter",
            scenario_name="Physical Camera View Shift / Tamper",
            category="camera_health",
            duration_sec=3.0,
            fps=5.0,
            expected_violation=True,
            expected_rule_type="camera_health_view_shift",
            description="ORB feature descriptor inliers drop below 30% indicating moved camera",
            generate_frames=gen_clip_29,
        )
    )

    def gen_clip_30() -> list[ClipFrameData]:
        # Clear, healthy camera baseline with rich features and normal motion
        import cv2

        base = _create_synthetic_test_frame(pattern_seed=1)
        frames = []
        for i in range(15):
            img = base.copy()
            # Minor motion: small circle moves slightly
            cv2.circle(img, (100 + i * 5, 450), 4, (0, 0, 0), -1)
            frames.append(ClipFrameData(420.0 + i * 0.2, [], img))
        return frames

    clips.append(
        ClipAnnotation(
            clip_id="clip_30",
            camera_id="cam1_press",
            scenario_name="Healthy Baseline Stream Ingestion",
            category="camera_health",
            duration_sec=3.0,
            fps=5.0,
            expected_violation=False,
            expected_rule_type=None,
            description="Nominal camera stream with active frame changes, clear sharpness, and stable view",
            generate_frames=gen_clip_30,
        )
    )

    return clips


BENCHMARK_30_CLIPS = _create_synthetic_dataset_30_clips()
