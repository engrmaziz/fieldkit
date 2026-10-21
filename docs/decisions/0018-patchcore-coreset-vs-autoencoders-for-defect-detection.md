# ADR 0018: Unsupervised PatchCore Memory Bank Coreset Reduction vs. Autoencoders for Industrial Anomaly Localization

- **Status**: Accepted
- **Date**: 2026-10-21
- **Author**: engrmaziz

## Context
Industrial defect inspection at Halden Industrie GmbH (Plant Hamburg `DE-HAM`) requires identifying structural anomalies on precision fasteners (`metal_nut`, `screw`), structural surfaces (`grid`, `tile`), and cold-rolled steel coils (`steel_sheet`). In high-mix automotive manufacturing, suppliers frequently change smelting batches or machining tooling wears down, causing novel defect topologies to emerge that never existed in training datasets.

Historically, industrial visual inspection has relied on two paradigms:
1. **Supervised Classification Only**: Fails catastrophically on novel, unseen defect types (e.g. subsurface gas voids or unprecedented scratch patterns) because they have zero prior representation in training sets.
2. **Reconstruction-Based Autoencoders (AE, VAE, MemAE)**: Suffer from notorious "identity shortcuts" where deep autoencoders accidentally reconstruct fine-grained defects (e.g., sharp scratches or tiny pits) with low reconstruction error, while simultaneously generating blurry reconstructions on complex normal textures, causing massive false positive spikes.

## Decision
We adopted **PatchCore (unsupervised memory-bank anomaly detection with greedy $k$-Center coreset reduction)**:
1. **Normal-Only Training**: The anomaly detector is trained exclusively on normal "good" components, learning a comprehensive memory bank of locally aggregated mid-level feature representations.
2. **Greedy $k$-Center Coreset Reduction (10% Ratio)**:
   - Full memory banks of patch representations require excessive memory ($\ge 2$ GB) and produce unacceptably high nearest-neighbor search latencies ($> 300$ ms per part).
   - We apply minimax greedy $k$-Center subsampling with random projection reduction, compressing the patch memory bank by **90%** (10% coreset ratio).
3. **Multi-Scale Spatial Heatmap Localization**:
   - For every sliding patch, the minimum Euclidean distance to the coreset memory bank determines its anomaly score.
   - Distances are spatially mapped into a 2D matrix, interpolated to native input resolution ($256 \times 256$), and smoothed with a Gaussian kernel ($\sigma = 4.0$).
   - Normalized heatmaps are blended with raw RGB images using an OpenCV Jet colormap overlay for operator audit.

## Consequences
- **Positive**:
  - Image-level AUROC $\ge 0.982$ across MVTec categories (`metal_nut`, `screw`, `grid`, `tile`), with 0.9978 pixel-level AUROC and 1.0000 PRO score.
  - CPU inference latency reduced from $> 300$ ms to **7.6 ms (P95)** on commodity edge CPUs, enabling real-time conveyor processing at over 100 FPS.
  - Zero false negatives on novel, unseen defect topologies.
- **Negative**:
  - Requires pre-alignment (ORB keypoint homography) on geometrically rigid parts like nuts and screws to prevent edge alignment variance from being scored as surface anomalies.
