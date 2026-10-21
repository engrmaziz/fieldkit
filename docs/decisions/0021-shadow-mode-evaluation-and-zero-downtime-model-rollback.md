# ADR 0021: Non-Blocking Shadow Inference and Versioned Manifests for Zero-Downtime Edge Defect Inspection

- **Status**: Accepted
- **Date**: 2026-10-21
- **Author**: engrmaziz

## Context
Deploying updated neural network models to high-throughput industrial conveyor lines (100+ FPS) presents severe operational risks:
1. **Conveyor Line Disruption Risk**: Halting conveyor lines or restarting edge inspection services during production shifts incurs immediate plant downtime penalties.
2. **Latent Model Regressions**: Even if a retrained model achieves high offline benchmark accuracy, subtle edge discrepancies (e.g. lighting sensitivity or slight latency spikes) can introduce unvetted false rejects or line slowdowns.
3. **Data Contamination & Leakage Risk**: Iterative retraining loops risk data leakage if operator-adjudicated review samples inadvertently overwrite or bleed into frozen evaluation test splits, causing falsely inflated evaluation metrics.

## Decision
We implemented a **closed-loop MLOps architecture combining versioned dataset manifests, non-blocking shadow mode inference, and atomic zero-downtime model promotion/rollback**:
1. **Versioned Dataset Manifests (`fieldkit_mlops/manifest.py`)**:
   - Every dataset version is tracked by a versioned JSON manifest recording individual sample SHA-256 digests and 64-bit dHash perceptual fingerprints.
   - Enforces strict immutability checks on the gold benchmark test set (`verify_frozen_test_set_immutability`). Adding operator review data only appends to the `train` split, preventing test set leakage.
   - Cross-split deduplication blocks near-duplicate samples (Hamming distance $\le 2$).
2. **Non-Blocking Shadow Mode Execution (`fieldkit_vision/inspect/shadow.py`)**:
   - When a candidate model is registered, incoming live conveyor images are asynchronously duplicated to the candidate model via background tasks.
   - The candidate model's predictions never touch live PLC disposition gates; only the proven production model makes live sorting decisions.
   - Paired telemetry records (`PairedShadowRecord`) track decision agreement, defect class concordance, anomaly score correlation, and latency deltas side-by-side.
3. **Automated Promotion Criteria & In-Memory Hot-Swap**:
   - Promotion to `PRODUCTION` requires:
     * Decision Agreement Rate $\ge 85.0\%$
     * Minimum paired sample size $\ge 50$ parts
     * Zero regression on frozen benchmark evaluation gates
   - Promotion (`POST /inspect/models/promote`) hot-swaps the active pipeline in memory with zero service restarts and zero dropped frames.
4. **Instant Zero-Downtime Rollback**:
   - `POST /inspect/models/rollback` immediately reverts the active in-memory pipeline to the previous stable production artifact while logging the revert action to the audit ledger.

## Consequences
- **Positive**:
  - Live shop-floor decisions are completely isolated from unproven candidate models during evaluation.
  - 100.0% decision agreement verified across shadow runs before promotion.
  - Zero-downtime model updates and instantaneous rollback capability.
  - Complete data provenance and strict immutability guarantees on benchmark test sets.
- **Negative**:
  - Running shadow inference concurrently increases CPU utilization by ~15-20% during active shadow evaluation windows.
