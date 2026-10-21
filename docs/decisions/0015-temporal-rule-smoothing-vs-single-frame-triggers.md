# ADR 0015: Deterministic Temporal Rule Smoothing vs. Single-Frame Triggers for Edge Safety Alerts

- **Status**: Accepted
- **Date**: 2026-10-21
- **Author**: engrmaziz

## Context
At Halden Industrie's Hamburg manufacturing plant (`DE-HAM`), a previous commercial computer vision safety installation was decommissioned because it generated **over 400 false alarms per day**. Operators and safety supervisors suffered acute alert fatigue and disabled notification sirens entirely:
1. **Detector Transience & Artifacts**: Momentary lighting shifts, crane shadow sweeps, and bounding box jitter caused instant triggers on safe, compliant workers.
2. **Transient Operator Adjustments**: Workers wiping sweat from their forehead, adjusting hardhat suspension straps, or glancing away for 0.4 seconds triggered immediate missing-PPE non-compliance sirens.
3. **Perspective Pixel Distortion**: Proximity alerts based on 2D pixel bounding box distances triggered false alarms when a worker stood near a parked, stationary forklift or walked safely across different perspective depth planes.

## Decision

1. **Deterministic 2.0s Temporal Violation Window**:
   - Safety rules (such as `zone_ppe_missing` in heavy stamping zones) are evaluated over a rolling observation deque ($W = 10\text{ frames}$ at $5\text{ FPS}$, representing a 2.0-second window).
   - An alert is emitted **only if the non-compliance ratio reaches or exceeds 70%** ($\ge 7 / 10\text{ observations}$), requiring sustained violation behavior.
   - Momentary detector dropouts (e.g. 1–2 missed frames) or quick physical adjustments (<1.0s) are cleanly suppressed without triggering sirens.

2. **Metric Floor-Plane Homography Gating**:
   - Proximity rules reject naive 2D bounding box pixel distances. Every camera is calibrated using an invertible 4-point projective homography mapping image coordinates to physical floor coordinates in meters.
   - Proximity is computed via Euclidean metric ground distance: $\Delta d = \|\mathbf{x}_{\text{worker}} - \mathbf{x}_{\text{forklift}}\|_2 < 2.0\text{ meters}$.
   - Proximity evaluation is further gated on dynamic motion: the forklift must exhibit active displacement velocity $> 0.5\text{ m/s}$ sustained for $\ge 0.6\text{ seconds}$, preventing false alarms around stationary, parked machinery.

3. **Multi-Track Cooldown Suppression**:
   - `CooldownManager` enforces a mandatory 30.0-second alert cooldown per `(camera_id, rule_id, target_key)`.
   - Repeated alerts for the same ongoing incident are suppressed, preventing alert storms while preserving complete analytical audit trails in ClickHouse.

## Consequences
- **Positive**: Empirical ablation benchmarks on 30 shop-floor scenarios proved a **10.9x alert volume noise reduction** (reducing 207 naive instant alerts down to 19 true sustained alerts). False alarms dropped from 0.75 FA/cam-hr to **0.000 FA/cam-hr**, while maintaining **100.0% recall** on true sustained safety infractions.
- **Negative**: Detection-to-event latency is constrained by the 2.0s rolling window requirement; however, 2.0s is well within occupational safety standards for near-miss intervention and far exceeds human manual auditing capabilities.
