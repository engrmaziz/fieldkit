"""Conveyor Belt High-Throughput Load and Latency Benchmark.

Simulates industrial high-speed conveyor line inspection (Plant Hamburg DE-HAM)
executing continuous dual-engine inference (PatchCore anomaly + ResNet-18 classification),
cost-based decision routing, and Jet colormap heatmap overlay generation.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from fieldkit_vision.inspect.storage import HeatmapStorageManager
from fieldkit_vision.inspect.worker import InspectionWorker

from evals.p6.dataset import _generate_synthetic_component_image

logger = logging.getLogger("fieldkit.evals.p6.load")


@dataclass
class InspectionLoadTestResult:
    """Benchmark metrics for industrial edge inspection service under sustained load."""

    total_inspections: int
    total_duration_seconds: float
    throughput_fps: float
    mean_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    max_latency_ms: float
    pass_count: int
    review_count: int
    reject_count: int
    audit_count: int
    heatmaps_generated: int
    zero_errors: bool
    latency_target_passed: bool   # P95 < 100 ms
    throughput_target_passed: bool # > 15 FPS
    all_targets_met: bool


def run_conveyor_load_benchmark(
    num_items: int = 60,
    storage_dir: Path | None = None,
) -> InspectionLoadTestResult:
    """Execute high-throughput simulated conveyor belt inspection run.

    Generates a stream of normal and defective parts (metal_nut and steel_sheet),
    measures end-to-end processing latencies including image decoding, PatchCore
    embedding, ONNX classification, cost matrix evaluation, and Jet heatmap generation.
    """
    logger.info("Initializing InspectionWorker with HeatmapStorageManager...")
    storage = HeatmapStorageManager(local_dir=storage_dir or Path("data/p6/heatmaps_loadtest"))
    worker = InspectionWorker(storage_manager=storage)

    products = ["steel_sheet", "metal_nut"]
    latencies: list[float] = []
    pass_count = 0
    review_count = 0
    reject_count = 0
    audit_count = 0
    heatmaps_generated = 0
    zero_errors = True

    # Pre-generate image byte buffers to simulate camera stream arrival
    pregenerated_buffers: list[tuple[str, str, bytes, bool]] = []
    for i in range(num_items):
        product = products[i % len(products)]
        part_id = f"HAM_CONV_{i:04d}"
        is_defective = (i % 5 == 0) or (i % 7 == 0)
        defect_type = "scratch" if is_defective else None

        img_bgr, _ = _generate_synthetic_component_image(
            category=product if product != "steel_sheet" else "metal_nut",
            defect_type=defect_type,
            seed=1000 + i,
        )
        # If steel sheet and defective, add distinct rolling mark
        if product == "steel_sheet" and is_defective:
            cv2.line(img_bgr, (20, 120), (230, 120), (30, 30, 30), 3)

        _, enc = cv2.imencode(".png", img_bgr)
        pregenerated_buffers.append((product, part_id, enc.tobytes(), is_defective))

    # Benchmark sustained execution
    start_time = time.perf_counter()
    for product, part_id, img_bytes, _ in pregenerated_buffers:
        t0 = time.perf_counter()
        try:
            resp = worker.inspect_image(
                product_id=product,
                image_bytes=img_bytes,
                part_id=part_id,
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            latencies.append(elapsed_ms)

            if resp.disposition == "pass":
                pass_count += 1
            elif resp.disposition == "review":
                review_count += 1
            elif resp.disposition == "reject":
                reject_count += 1

            if resp.is_audit_sample:
                audit_count += 1

            if resp.heatmap_url:
                heatmaps_generated += 1

        except Exception as e:
            logger.error(f"Error inspecting part {part_id}: {e}")
            zero_errors = False

    total_duration = time.perf_counter() - start_time
    throughput_fps = len(latencies) / max(total_duration, 0.001)

    lat_arr = np.array(latencies)
    mean_lat = float(np.mean(lat_arr)) if len(lat_arr) > 0 else 0.0
    p50_lat = float(np.percentile(lat_arr, 50)) if len(lat_arr) > 0 else 0.0
    p95_lat = float(np.percentile(lat_arr, 95)) if len(lat_arr) > 0 else 0.0
    p99_lat = float(np.percentile(lat_arr, 99)) if len(lat_arr) > 0 else 0.0
    max_lat = float(np.max(lat_arr)) if len(lat_arr) > 0 else 0.0

    latency_target_passed = p95_lat < 100.0
    throughput_target_passed = throughput_fps >= 15.0  # sustained > 15 FPS
    all_targets_met = zero_errors and latency_target_passed and throughput_target_passed

    logger.info(
        f"Conveyor Load Benchmark Complete: {len(latencies)} parts in {total_duration:.2f}s "
        f"({throughput_fps:.1f} FPS, P95: {p95_lat:.1f}ms, P50: {p50_lat:.1f}ms)"
    )

    return InspectionLoadTestResult(
        total_inspections=len(latencies),
        total_duration_seconds=total_duration,
        throughput_fps=throughput_fps,
        mean_latency_ms=mean_lat,
        p50_latency_ms=p50_lat,
        p95_latency_ms=p95_lat,
        p99_latency_ms=p99_lat,
        max_latency_ms=max_lat,
        pass_count=pass_count,
        review_count=review_count,
        reject_count=reject_count,
        audit_count=audit_count,
        heatmaps_generated=heatmaps_generated,
        zero_errors=zero_errors,
        latency_target_passed=latency_target_passed,
        throughput_target_passed=throughput_target_passed,
        all_targets_met=all_targets_met,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    res = run_conveyor_load_benchmark(num_items=50)
    print(f"Throughput: {res.throughput_fps:.1f} FPS")
    print(f"P95 Latency: {res.p95_latency_ms:.1f} ms")
    print(f"Pass: {res.pass_count}, Review: {res.review_count}, Reject: {res.reject_count}")
    print(f"All targets met: {res.all_targets_met}")
