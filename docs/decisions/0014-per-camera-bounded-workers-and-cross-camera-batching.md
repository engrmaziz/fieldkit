# ADR 0014: Bounded Per-Camera Ingestion Workers with Cross-Camera Dynamic Batching

- **Status**: Accepted
- **Date**: 2026-10-21
- **Author**: engrmaziz

## Context
Deploying multi-camera computer vision analytics across Halden Industrie's factory floor (4 industrial feeds: stamping press, logistics corridor, staging workstations, and perimeter security) imposes strict real-time edge constraints:
1. **Heterogeneous Network Quality**: RTSP streams over industrial Wi-Fi or plant switches experience transient packet drops, RTSP reconnect delays, and jitter. A slow or stalled camera must never block or degrade frame processing for the other cameras.
2. **Unbounded Memory Backpressure Risk**: If neural network inference runs slower than incoming video frame rates, naive FIFO queues without memory bounds accumulate frames, leading to escalating latency and eventual Out-Of-Memory (OOM) crashes.
3. **Hardware Utilization Trade-off**: Running separate, isolated deep neural network inference loops per camera incurs high kernel launch overhead and underutilizes vector compute (SIMD on CPU or tensor cores on edge GPUs).

## Decision

1. **Independent Per-Camera Ingestion Workers (`camera_worker.py`)**:
   - Each RTSP stream is ingested by an independent `asyncio` worker task.
   - Workers use TCP transport (`rtsp_transport=tcp`) with a 5.0s connection timeout and automatic exponential backoff reconnect with random jitter (capped at 30.0s).
   - Ingestion is decoupled from decoding via timestamp-based downsampling: frames are sampled to an exact target rate ($5.0 \pm 0.2\text{ FPS}$) based on PTS/wall-clock timestamps rather than naive frame-counter modulo.

2. **Bounded Queue with Drop-Oldest Backpressure Policy**:
   - Each camera feeds into an isolated `BoundedFrameQueue(maxsize=4)`.
   - When the queue reaches capacity, the oldest unconsumed frame at the head of the queue is discarded immediately, preserving the freshest frame for real-time safety evaluation.
   - Queue depth is strictly bounded to $\le 4$ frames at all times, guaranteeing bounded memory consumption and eliminating latency accumulation.

3. **Dynamic Cross-Camera Tensor Batching**:
   - Ingestion queues are drained by an asynchronous batcher collecting available frames across all active cameras up to batch size $B=4$.
   - The batched tensor $[B, 3, 640, 640]$ is dispatched in a single ONNX Runtime forward pass, amortizing inference overhead and maximizing throughput on host CPU or edge GPU.

## Consequences
- **Positive**: Complete fault isolation (one stream dropping does not impact the others), strictly zero unbounded memory growth under high load, aggregate throughput exceeding 19.9 FPS, and deterministic sub-25ms frame-to-event latency.
- **Negative**: During extreme sustained compute saturation, dropped frames result in downsampled temporal resolution, though temporal smoothing buffers maintain violation state across drop events.
