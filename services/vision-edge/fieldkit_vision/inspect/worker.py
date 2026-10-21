"""Inspection worker orchestrating multi-product edge inference, storage, and metrics."""

from __future__ import annotations

import logging
import time
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
import yaml
from fieldkit_mlops.thresholds import CostMatrixConfig
from fieldkit_mlops.train_anomaly import train_patchcore_model

from evals.p6.dataset import _generate_synthetic_component_image
from fieldkit_vision.inspect.anomaly import PatchCoreAnomalyDetector
from fieldkit_vision.inspect.classifier import (
    DEFAULT_DEFECT_CLASSES,
    DefectClassifier,
)
from fieldkit_vision.inspect.decision import (
    InspectionDecisionEngine,
)
from fieldkit_vision.inspect.metrics import (
    INSPECTION_ANOMALY_SCORE,
    INSPECTION_LATENCY_SECONDS,
    INSPECTION_REQUESTS_TOTAL,
    INSPECTION_REVIEW_QUEUE_DEPTH,
)
from fieldkit_vision.inspect.models import (
    InspectionRecord,
    InspectionResponse,
    InspectionReviewUpdate,
)
from fieldkit_vision.inspect.preprocess import InspectionPreprocessor
from fieldkit_vision.inspect.storage import HeatmapStorageManager

logger = logging.getLogger("fieldkit.vision.inspect.worker")


class ProductPipeline:
    """Pre-loaded model ensemble for a specific manufacturing SKU."""

    def __init__(self, product_id: str, config_path: Path | str | None = None) -> None:
        self.product_id = product_id
        self.config_path = Path(config_path) if config_path else None
        self.config = self._load_config()

        # 1. Preprocessor with ROI
        roi_cfg = self.config.get("roi")
        roi_box = [roi_cfg["x1"], roi_cfg["y1"], roi_cfg["x2"], roi_cfg["y2"]] if roi_cfg else None
        self.preprocessor = InspectionPreprocessor(target_size=(256, 256), roi=roi_box)

        # 2. PatchCore Anomaly Detector
        anom_cfg = self.config.get("anomaly_model", {})
        t_pass = anom_cfg.get("threshold_pass", 0.35)
        t_reject = anom_cfg.get("threshold_reject", 0.65)

        # Generate / load calibrated baseline bundle
        good_imgs = [_generate_synthetic_component_image(product_id, None, seed=200 + i)[0] for i in range(5)]
        bundle = train_patchcore_model(good_imgs, category=product_id, coreset_ratio=0.15)
        self.detector = PatchCoreAnomalyDetector(
            bundle=bundle,
            category=product_id,
            threshold_pass=t_pass,
            threshold_reject=t_reject,
            patch_size=16,
            stride=16,
        )

        # 3. Supervised Defect Classifier
        cls_cfg = self.config.get("classifier_model", {})
        temp = cls_cfg.get("temperature_calibration", 1.34)
        self.classifier = DefectClassifier(classes=DEFAULT_DEFECT_CLASSES, temperature=temp)

        # 4. Decision Engine
        cost_dict = self.config.get("cost_matrix", {})
        cost_matrix = CostMatrixConfig(
            cost_false_pass=cost_dict.get("cost_escape", 500.0),
            cost_false_reject=cost_dict.get("cost_false_reject", 25.0),
            cost_review=cost_dict.get("cost_review", 5.0),
            max_review_budget=cost_dict.get("max_review_rate", 0.08),
        )
        self.decision_engine = InspectionDecisionEngine(
            threshold_pass=t_pass,
            threshold_reject=t_reject,
            threshold_classifier_conf=0.85,
            audit_rate=cost_dict.get("random_audit_ratio", 0.02),
            cost_matrix=cost_matrix,
        )

    def _load_config(self) -> dict:
        if self.config_path and self.config_path.exists():
            return yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}

        # Default fallback config path
        fallback = Path(f"configs/inspection/{self.product_id}.yaml")
        if fallback.exists():
            return yaml.safe_load(fallback.read_text(encoding="utf-8")) or {}

        return {}


class InspectionWorker:
    """Production runtime service managing live component inspection requests."""

    def __init__(
        self,
        config_dir: Path | str = "configs/inspection",
        storage_manager: HeatmapStorageManager | None = None,
        max_record_history: int = 1000,
    ) -> None:
        self.config_dir = Path(config_dir)
        self.storage = storage_manager or HeatmapStorageManager()
        self.records: deque[InspectionRecord] = deque(maxlen=max_record_history)
        self.records_by_id: dict[str, InspectionRecord] = {}

        # Pre-load available product pipelines
        self.pipelines: dict[str, ProductPipeline] = {}
        self._init_pipelines()

    def _init_pipelines(self) -> None:
        """Scan configs directory and initialize model pipelines."""
        if not self.config_dir.exists():
            logger.warning("Configs directory %s not found, loading defaults", self.config_dir)
            self.pipelines["metal_nut"] = ProductPipeline("metal_nut")
            self.pipelines["steel_sheet"] = ProductPipeline("steel_sheet")
            return

        for p_file in self.config_dir.glob("*.yaml"):
            prod_id = p_file.stem
            try:
                self.pipelines[prod_id] = ProductPipeline(prod_id, config_path=p_file)
                logger.info("Loaded inspection pipeline for product: %s", prod_id)
            except Exception as e:
                logger.error("Failed to load pipeline for %s: %s", prod_id, e)

        if not self.pipelines:
            self.pipelines["metal_nut"] = ProductPipeline("metal_nut")
            self.pipelines["steel_sheet"] = ProductPipeline("steel_sheet")

    def inspect_image(
        self,
        product_id: str,
        image_bytes: bytes,
        part_id: str | None = None,
        plant_id: str = "DE-HAM",
    ) -> InspectionResponse:
        """Execute full edge inspection pipeline on incoming component image bytes."""
        t0 = time.perf_counter()

        # 1. Decode image
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Failed to decode uploaded image data")

        # 2. Retrieve or lazy-load product pipeline
        if product_id not in self.pipelines:
            self.pipelines[product_id] = ProductPipeline(product_id)
        pipeline = self.pipelines[product_id]

        inspection_id = str(uuid4())
        now_utc = datetime.now(UTC)
        eff_part_id = part_id or f"{product_id}_{now_utc.strftime('%Y%m%d_%H%M%S')}_{inspection_id[:6]}"

        # 3. Preprocess & Align
        prep_res = pipeline.preprocessor.preprocess(img)

        # 4. Anomaly Localization
        anom_res = pipeline.detector.predict(prep_res.image)

        # 5. Defect Classification
        cls_res = pipeline.classifier.predict(prep_res.image)

        # 6. Decision Engine State Machine
        dec = pipeline.decision_engine.evaluate(
            prep_result=prep_res,
            anomaly_result=anom_res,
            defect_prediction=cls_res,
            item_id=eff_part_id,
        )

        t_elapsed = (time.perf_counter() - t0) * 1000.0

        # 7. Heatmap Overlay Storage
        uri, _ = self.storage.save_heatmap_overlay(
            product_id=product_id,
            inspection_id=inspection_id,
            image=prep_res.image,
            heatmap=anom_res.heatmap,
        )

        # 8. Record Telemetry Metrics
        INSPECTION_REQUESTS_TOTAL.labels(product_id=product_id, disposition=dec.action.value).inc()
        INSPECTION_LATENCY_SECONDS.labels(product_id=product_id).observe(t_elapsed / 1000.0)
        INSPECTION_ANOMALY_SCORE.labels(product_id=product_id).set(anom_res.anomaly_score)

        if dec.action.value == "review":
            review_count = sum(1 for r in self.records if r.disposition == "review" and r.operator_label is None)
            INSPECTION_REVIEW_QUEUE_DEPTH.labels(product_id=product_id).set(review_count + 1)

        # 9. Build and Store Record
        rec = InspectionRecord(
            inspection_id=inspection_id,
            product_id=product_id,
            part_id=eff_part_id,
            plant_id=plant_id,
            timestamp=now_utc,
            disposition=dec.action.value,
            disposition_reason=dec.reason.value,
            anomaly_score=anom_res.anomaly_score,
            defect_class=cls_res.predicted_class,
            defect_confidence=cls_res.confidence,
            is_audit_sample=dec.is_audit_sample,
            heatmap_url=uri,
            latency_ms=round(t_elapsed, 2),
            details=dec.details,
        )

        self.records.appendleft(rec)
        self.records_by_id[inspection_id] = rec

        return InspectionResponse(
            inspection_id=inspection_id,
            product_id=product_id,
            part_id=eff_part_id,
            plant_id=plant_id,
            timestamp=rec.timestamp,
            disposition=dec.action.value,
            disposition_reason=dec.reason.value,
            anomaly_score=anom_res.anomaly_score,
            defect_class=cls_res.predicted_class,
            defect_confidence=cls_res.confidence,
            is_audit_sample=dec.is_audit_sample,
            heatmap_url=uri,
            latency_ms=round(t_elapsed, 2),
            details=dec.details,
        )

    def get_records(
        self,
        product_id: str | None = None,
        disposition: str | None = None,
        limit: int = 50,
    ) -> list[InspectionRecord]:
        """Query recent inspection history filtered by product or disposition."""
        res: list[InspectionRecord] = []
        for r in self.records:
            if product_id and r.product_id != product_id:
                continue
            if disposition and r.disposition != disposition:
                continue
            res.append(r)
            if len(res) >= limit:
                break
        return res

    def get_record(self, inspection_id: str) -> InspectionRecord | None:
        """Fetch single inspection record by UUID."""
        return self.records_by_id.get(inspection_id)

    def update_record_review(
        self,
        inspection_id: str,
        update: InspectionReviewUpdate,
    ) -> InspectionRecord | None:
        """Apply operator review label and notes to pending review record."""
        rec = self.records_by_id.get(inspection_id)
        if not rec:
            return None

        rec.operator_label = update.operator_label
        rec.operator_notes = update.operator_notes
        rec.reviewed_by = update.reviewed_by
        rec.reviewed_at = datetime.now(UTC)

        # Update review queue depth metric
        review_count = sum(1 for r in self.records if r.disposition == "review" and r.operator_label is None)
        INSPECTION_REVIEW_QUEUE_DEPTH.labels(product_id=rec.product_id).set(review_count)
        return rec

    def get_heatmap_bytes(self, inspection_id: str) -> bytes | None:
        """Retrieve binary JPEG heatmap overlay bytes."""
        return self.storage.get_heatmap_bytes(inspection_id)

    def list_supported_products(self) -> list[str]:
        """List all active product pipeline identifiers."""
        return list(self.pipelines.keys())
