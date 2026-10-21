"""Deterministic rules engine, temporal smoothing, spatial containment, and alert cooldown."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from fieldkit_vision.homography import CameraHomography, compute_metric_distance
from fieldkit_vision.models import CameraConfig, RuleConfig, ZoneConfig
from fieldkit_vision.tracker import TrackedEntity

logger = logging.getLogger("fieldkit.vision.rules")


def point_in_polygon(point: tuple[float, float], polygon: list[list[int]] | list[list[float]]) -> bool:
    """Ray-casting algorithm to test whether a 2D point is inside a polygon."""
    x, y = point
    n = len(polygon)
    inside = False
    if n < 3:
        return False

    p1x, p1y = polygon[0]
    for i in range(n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    xints = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x if p1y != p2y else p1x
                    if p1x == p2x or x <= xints:
                        inside = not inside
        p1x, p1y = p2x, p2y

    return inside


def ccw(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> bool:
    return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])


def segments_intersect(
    p1: tuple[float, float] | list[float],
    p2: tuple[float, float] | list[float],
    p3: tuple[float, float] | list[float],
    p4: tuple[float, float] | list[float],
) -> bool:
    """Return True if line segment (p1, p2) intersects line segment (p3, p4)."""
    pt1 = (float(p1[0]), float(p1[1]))
    pt2 = (float(p2[0]), float(p2[1]))
    pt3 = (float(p3[0]), float(p3[1]))
    pt4 = (float(p4[0]), float(p4[1]))
    return ccw(pt1, pt3, pt4) != ccw(pt2, pt3, pt4) and ccw(pt1, pt2, pt3) != ccw(pt1, pt2, pt4)


class CooldownManager:
    """Manages alert suppression cooldowns per (camera, rule, target) tuple."""

    def __init__(self, default_cooldown_sec: float = 30.0) -> None:
        self.default_cooldown_sec = default_cooldown_sec
        self._last_alert: dict[tuple[str, str, str], float] = {}

    def is_in_cooldown(
        self,
        camera_id: str,
        rule_id: str,
        target_key: str,
        timestamp: float,
        cooldown_sec: float | None = None,
    ) -> bool:
        """Return True if the rule alert is currently suppressed by cooldown."""
        cooldown = cooldown_sec if cooldown_sec is not None else self.default_cooldown_sec
        key = (camera_id, rule_id, target_key)
        last_time = self._last_alert.get(key)
        if last_time is None:
            return False
        return (timestamp - last_time) < cooldown

    def record_alert(self, camera_id: str, rule_id: str, target_key: str, timestamp: float) -> None:
        """Record timestamp of emitted alert."""
        key = (camera_id, rule_id, target_key)
        self._last_alert[key] = timestamp


@dataclass
class RuleViolation:
    """Safety violation event emitted by deterministic rules engine."""

    camera_id: str
    rule_id: str
    rule_type: str
    severity: str
    track_id: int
    timestamp: float
    related_track_id: int | None = None
    zone_id: str | None = None
    metric_distance: float | None = None
    metric_speed: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class DeterministicRulesEngine:
    """Evaluates safety rules with temporal smoothing and 30s cooldown filter."""

    def __init__(
        self,
        camera_config: CameraConfig,
        homography: CameraHomography | None = None,
        cooldown_manager: CooldownManager | None = None,
    ) -> None:
        self.config = camera_config
        self.homography = homography
        self.cooldown = cooldown_manager or CooldownManager(default_cooldown_sec=30.0)

        # Lookup maps
        self.zones: dict[str, ZoneConfig] = {z.id: z for z in camera_config.zones}
        self.rules: list[RuleConfig] = camera_config.rules

        # Internal tracking state for temporal rules
        self._zone_dwell_start: dict[tuple[int, str], float] = {}
        self._proximity_start: dict[tuple[int, int], float] = {}

    def evaluate(self, tracks: list[TrackedEntity], timestamp: float) -> list[RuleViolation]:
        """Evaluate all active camera rules against current frame tracks."""
        violations: list[RuleViolation] = []

        # Update floor coordinates if homography is available
        if self.homography:
            for t in tracks:
                try:
                    t.floor_coord = self.homography.image_to_floor(t.foot_point)
                except Exception:
                    t.floor_coord = None

        for rule in self.rules:
            if rule.type == "zone_ppe_missing":
                violations.extend(self._eval_zone_ppe_missing(rule, tracks, timestamp))
            elif rule.type == "proximity":
                violations.extend(self._eval_proximity(rule, tracks, timestamp))
            elif rule.type == "dwell":
                violations.extend(self._eval_dwell(rule, tracks, timestamp))
            elif rule.type == "line_cross":
                violations.extend(self._eval_line_cross(rule, tracks, timestamp))

        return violations

    def _eval_zone_ppe_missing(
        self,
        rule: RuleConfig,
        tracks: list[TrackedEntity],
        timestamp: float,
    ) -> list[RuleViolation]:
        violations: list[RuleViolation] = []
        zone = self.zones.get(rule.zone_id or "")
        if not zone or not zone.polygon:
            return violations

        ppe_class = rule.ppe_class or "helmet"
        target_tracks = [t for t in tracks if t.class_name == "person"]

        for track in target_tracks:
            # 1. Spatial containment check: worker foot point in zone polygon
            if not point_in_polygon(track.foot_point, zone.polygon):
                continue

            # 2. Temporal smoothing compliance check over rolling window
            if ppe_class == "helmet":
                comp_ratio = track.helmet_compliance_ratio
            else:
                comp_ratio = track.vest_compliance_ratio

            violation_ratio = 1.0 - comp_ratio

            # 3. Threshold check (e.g. >= 70% violation over 2s window)
            if violation_ratio >= rule.min_violation_ratio:
                target_key = f"track_{track.track_id}"
                cooldown_sec = rule.cooldown_sec or 30.0

                if not self.cooldown.is_in_cooldown(
                    self.config.camera_id, rule.id, target_key, timestamp, cooldown_sec
                ):
                    self.cooldown.record_alert(self.config.camera_id, rule.id, target_key, timestamp)
                    violations.append(
                        RuleViolation(
                            camera_id=self.config.camera_id,
                            rule_id=rule.id,
                            rule_type=rule.type,
                            severity="CRITICAL",
                            track_id=track.track_id,
                            timestamp=timestamp,
                            zone_id=zone.id,
                            metadata={
                                "ppe_class": ppe_class,
                                "violation_ratio": round(violation_ratio, 3),
                                "compliance_ratio": round(comp_ratio, 3),
                            },
                        )
                    )

        return violations

    def _eval_proximity(
        self,
        rule: RuleConfig,
        tracks: list[TrackedEntity],
        timestamp: float,
    ) -> list[RuleViolation]:
        violations: list[RuleViolation] = []
        if not self.homography:
            return violations

        class_a = rule.class_a or "person"
        class_b = rule.class_b or "forklift"
        max_dist = rule.max_distance_meters or 2.0
        min_speed = rule.min_forklift_speed_mps or 0.5
        min_dur = rule.min_duration_sec or 0.6
        cooldown_sec = rule.cooldown_sec or 30.0

        tracks_a = [t for t in tracks if t.class_name == class_a and t.floor_coord is not None]
        tracks_b = [t for t in tracks if t.class_name == class_b and t.floor_coord is not None]

        for ta in tracks_a:
            for tb in tracks_b:
                dist = compute_metric_distance(ta.floor_coord, tb.floor_coord)  # type: ignore[arg-type]
                pair_key = (min(ta.track_id, tb.track_id), max(ta.track_id, tb.track_id))

                if dist <= max_dist and tb.speed_mps >= min_speed:
                    # Check duration of proximity
                    if pair_key not in self._proximity_start:
                        self._proximity_start[pair_key] = timestamp

                    duration = timestamp - self._proximity_start[pair_key]
                    if duration >= (min_dur - 1e-4):
                        target_key = f"pair_{pair_key[0]}_{pair_key[1]}"
                        if not self.cooldown.is_in_cooldown(
                            self.config.camera_id, rule.id, target_key, timestamp, cooldown_sec
                        ):
                            self.cooldown.record_alert(
                                self.config.camera_id, rule.id, target_key, timestamp
                            )
                            violations.append(
                                RuleViolation(
                                    camera_id=self.config.camera_id,
                                    rule_id=rule.id,
                                    rule_type=rule.type,
                                    severity="CRITICAL",
                                    track_id=ta.track_id,
                                    related_track_id=tb.track_id,
                                    timestamp=timestamp,
                                    metric_distance=round(dist, 3),
                                    metric_speed=round(tb.speed_mps, 3),
                                    metadata={
                                        "forklift_speed_mps": round(tb.speed_mps, 3),
                                        "distance_meters": round(dist, 3),
                                        "duration_sec": round(duration, 2),
                                    },
                                )
                            )
                else:
                    self._proximity_start.pop(pair_key, None)

        return violations

    def _eval_dwell(
        self,
        rule: RuleConfig,
        tracks: list[TrackedEntity],
        timestamp: float,
    ) -> list[RuleViolation]:
        violations: list[RuleViolation] = []
        zone = self.zones.get(rule.zone_id or "")
        if not zone or not zone.polygon:
            return violations

        min_dwell = rule.min_dwell_sec or 60.0
        cooldown_sec = rule.cooldown_sec or 30.0

        for track in tracks:
            key = (track.track_id, zone.id)
            is_inside = point_in_polygon(track.foot_point, zone.polygon)

            if is_inside:
                if key not in self._zone_dwell_start:
                    self._zone_dwell_start[key] = timestamp

                dwell_duration = timestamp - self._zone_dwell_start[key]
                if dwell_duration >= (min_dwell - 1e-4):
                    target_key = f"dwell_{track.track_id}_{zone.id}"
                    if not self.cooldown.is_in_cooldown(
                        self.config.camera_id, rule.id, target_key, timestamp, cooldown_sec
                    ):
                        self.cooldown.record_alert(self.config.camera_id, rule.id, target_key, timestamp)
                        violations.append(
                            RuleViolation(
                                camera_id=self.config.camera_id,
                                rule_id=rule.id,
                                rule_type=rule.type,
                                severity="WARNING",
                                track_id=track.track_id,
                                timestamp=timestamp,
                                zone_id=zone.id,
                                metadata={"dwell_sec": round(dwell_duration, 1)},
                            )
                        )
            else:
                self._zone_dwell_start.pop(key, None)

        return violations

    def _eval_line_cross(
        self,
        rule: RuleConfig,
        tracks: list[TrackedEntity],
        timestamp: float,
    ) -> list[RuleViolation]:
        violations: list[RuleViolation] = []
        if not rule.line or len(rule.line) < 2:
            return violations

        line_p1 = (float(rule.line[0][0]), float(rule.line[0][1]))
        line_p2 = (float(rule.line[1][0]), float(rule.line[1][1]))
        cooldown_sec = rule.cooldown_sec or 30.0

        for track in tracks:
            if len(track.trajectory) < 2:
                continue

            # Check segment between last two trajectory foot points
            prev_pt = (track.trajectory[-2][1], track.trajectory[-2][2])
            curr_pt = (track.trajectory[-1][1], track.trajectory[-1][2])

            if segments_intersect(prev_pt, curr_pt, line_p1, line_p2):
                target_key = f"cross_{track.track_id}_{rule.id}"
                if not self.cooldown.is_in_cooldown(
                    self.config.camera_id, rule.id, target_key, timestamp, cooldown_sec
                ):
                    self.cooldown.record_alert(self.config.camera_id, rule.id, target_key, timestamp)
                    violations.append(
                        RuleViolation(
                            camera_id=self.config.camera_id,
                            rule_id=rule.id,
                            rule_type=rule.type,
                            severity="WARNING",
                            track_id=track.track_id,
                            timestamp=timestamp,
                            metadata={"direction": rule.direction or "entry"},
                        )
                    )

        return violations
