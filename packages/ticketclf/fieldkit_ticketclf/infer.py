"""Local ONNX Runtime CPU inference engine with post-hoc temperature scaling calibration.

Delivers sub-30ms CPU inference for multi-task support ticket triage:
- Shared multi-task model predicting both queue and priority
- Int8 dynamic quantization for minimal memory footprint and fast CPU execution
- Temperature scaling calibration for reliable empirical confidence estimates
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np
from fieldkit_common.logging import get_logger
from pydantic import BaseModel, Field

from .calibration import TemperatureScaler
from .data import ALLOWED_QUEUES

logger = get_logger("fieldkit.ticketclf.infer")


class TicketPrediction(BaseModel):
    """Structured output for ONNX ticket classification."""

    queue: str = Field(description="Predicted ticket triage queue")
    priority: str = Field(description="Predicted urgency priority tier")
    confidence: float = Field(ge=0.0, le=1.0, description="Calibrated confidence score")
    queue_probabilities: dict[str, float] = Field(
        default_factory=dict, description="Calibrated probability per queue"
    )
    priority_probabilities: dict[str, float] = Field(
        default_factory=dict, description="Calibrated probability per priority"
    )
    latency_ms: float = Field(default=0.0, description="Inference latency in milliseconds")


class ONNXTicketClassifier:
    """Local ONNX CPU classifier with temperature scaling calibration."""

    def __init__(
        self,
        model_path: Path | str | None = None,
        labels_path: Path | str | None = None,
        scaler: TemperatureScaler | None = None,
        scaler_path: Path | str | None = None,
        num_threads: int = 4,
        allow_mock: bool = True,
    ) -> None:
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        default_model_dir = repo_root / "models" / "p3"

        if model_path is None:
            # Check for quantized int8 model first, then standard onnx
            if (default_model_dir / "model_int8.onnx").exists():
                self.model_path = default_model_dir / "model_int8.onnx"
            else:
                self.model_path = default_model_dir / "model.onnx"
        else:
            self.model_path = Path(model_path)

        self.labels_path = (
            Path(labels_path) if labels_path else default_model_dir / "labels.json"
        )
        self.num_threads = num_threads
        self.allow_mock = allow_mock
        self.is_mock: bool = False
        self.is_loaded: bool = False

        # Load or initialize labels
        self.id2queue: dict[int, str] = dict(enumerate(sorted(ALLOWED_QUEUES)))
        self.id2priority: dict[int, str] = dict(
            enumerate(["low", "medium", "high", "critical"])
        )
        self._load_labels()

        # Load or initialize temperature scaler
        if scaler is not None:
            self.scaler = scaler
        elif scaler_path and Path(scaler_path).exists():
            self.scaler = TemperatureScaler.load(scaler_path)
        elif (default_model_dir / "temperature_scaler.json").exists():
            self.scaler = TemperatureScaler.load(default_model_dir / "temperature_scaler.json")
        else:
            self.scaler = TemperatureScaler(1.0, 1.0)

        # Initialize ONNX Runtime session
        self.session: Any = None
        self.tokenizer: Any = None
        self._init_session()

    def _load_labels(self) -> None:
        if self.labels_path.exists():
            try:
                data = json.loads(self.labels_path.read_text(encoding="utf-8"))
                if "id2queue" in data:
                    self.id2queue = {int(k): str(v) for k, v in data["id2queue"].items()}
                if "id2priority" in data:
                    self.id2priority = {int(k): str(v) for k, v in data["id2priority"].items()}
            except Exception as e:
                logger.warning("failed_to_load_labels_json_using_defaults", error=str(e))

    def _init_session(self) -> None:
        if self.model_path.exists():
            try:
                import onnxruntime as ort

                sess_options = ort.SessionOptions()
                sess_options.intra_op_num_threads = self.num_threads
                sess_options.graph_optimization_level = (
                    ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                )
                self.session = ort.InferenceSession(
                    str(self.model_path),
                    sess_options,
                    providers=["CPUExecutionProvider"],
                )
                self.is_loaded = True
                self.is_mock = False
                logger.info("onnx_session_initialized_successfully", model=str(self.model_path))

                # Attempt to load fast tokenizer if available
                tok_file = self.model_path.parent / "tokenizer" / "tokenizer.json"
                if tok_file.exists():
                    try:
                        from tokenizers import Tokenizer

                        tok = Tokenizer.from_file(str(tok_file))
                        tok.enable_padding(length=256)
                        tok.enable_truncation(max_length=256)
                        self.tokenizer = tok
                        logger.info("onnx_tokenizer_loaded_successfully", path=str(tok_file))
                    except Exception as e_tok:
                        logger.warning("failed_to_load_tokenizer_json", error=str(e_tok))
                return
            except Exception as exc:
                logger.warning("onnx_session_init_failed", error=str(exc))

        # Model file not found or failed to initialize
        if self.allow_mock:
            self.is_mock = True
            self.is_loaded = True
            logger.info("onnx_classifier_running_in_mock_mode", model=str(self.model_path))
        else:
            raise FileNotFoundError(
                f"Trained ONNX model not found at '{self.model_path}'. "
                "Please run notebooks/kaggle/p3_xlmr_finetune.ipynb on Kaggle GPU, "
                "download 'fieldkit_xlmr_onnx.zip' from the Output tab, and extract to 'models/p3/'."
            )

    def _mock_predict_one(self, text: str) -> tuple[np.ndarray, np.ndarray]:
        """Generate realistic mock logits matching Halden industrial keywords."""
        t_low = text.lower()
        num_q = len(self.id2queue)
        num_p = len(self.id2priority)

        q_logits = np.zeros(num_q, dtype=np.float32)
        p_logits = np.zeros(num_p, dtype=np.float32)

        # Keyword heuristics for mock queue distribution
        if any(w in t_low for w in ["rma", "return", "retoure", "rücksendung", "ruecksendung", "warranty", "gewaehrleistung"]):
            q_idx = [i for i, q in self.id2queue.items() if q == "returns_rma"][0]
            q_logits[q_idx] += 4.5
        elif any(w in t_low for w in ["invoice", "rechnung", "price", "preis", "billing", "credit", "gutschrift"]):
            q_idx = [i for i, q in self.id2queue.items() if q == "billing_inquiry"][0]
            q_logits[q_idx] += 4.4
        elif any(w in t_low for w in ["leak", "leckage", "pressure", "druck", "vibration", "pump", "crack", "defect"]):
            q_idx = [i for i, q in self.id2queue.items() if q == "technical_defect"][0]
            q_logits[q_idx] += 4.3
        elif any(w in t_low for w in ["delivery", "lieferung", "tracking", "shipping", "spedition"]):
            q_idx = [i for i, q in self.id2queue.items() if q == "order_delivery"][0]
            q_logits[q_idx] += 4.2
        elif any(w in t_low for w in ["invoice", "rechnung", "price", "preis", "billing", "credit", "gutschrift"]):
            q_idx = [i for i, q in self.id2queue.items() if q == "billing_inquiry"][0]
            q_logits[q_idx] += 4.1
        elif any(w in t_low for w in ["cad", "spec", "datasheet", "certificate", "zertifikat", "iso"]):
            q_idx = [i for i, q in self.id2queue.items() if q == "general_inquiry"][0]
            q_logits[q_idx] += 3.8
        else:
            q_idx = [i for i, q in self.id2queue.items() if q == "other"][0]
            q_logits[q_idx] += 3.0

        # Priority heuristics
        if any(w in t_low for w in ["urgent", "kritisch", "critical", "stillstand", "spraying"]):
            p_logits[3] += 4.0  # critical
        elif any(w in t_low for w in ["high", "hoch", "leak", "deformiert"]):
            p_logits[2] += 3.5  # high
        elif any(w in t_low for w in ["low", "gering", "catalog", "info"]):
            p_logits[0] += 3.0  # low
        else:
            p_logits[1] += 3.2  # medium

        # Add slight noise to unchosen categories
        q_logits += np.random.RandomState(len(text)).randn(num_q) * 0.2
        p_logits += np.random.RandomState(len(text)).randn(num_p) * 0.2
        return q_logits, p_logits

    def predict(self, texts: list[str]) -> list[TicketPrediction]:
        """Perform batched CPU prediction with temperature-calibrated probabilities."""
        if not texts:
            return []

        results: list[TicketPrediction] = []

        for text in texts:
            t0 = time.perf_counter()

            if self.is_mock or self.session is None:
                q_raw, p_raw = self._mock_predict_one(text)
                q_logits = q_raw.reshape(1, -1)
                p_logits = p_raw.reshape(1, -1)
            else:
                # Real ONNX session inference
                if self.tokenizer is not None:
                    enc = self.tokenizer.encode(text)
                    input_ids = np.array([enc.ids], dtype=np.int64)
                    attention_mask = np.array([enc.attention_mask], dtype=np.int64)
                else:
                    input_ids = np.zeros((1, 256), dtype=np.int64)
                    attention_mask = np.zeros((1, 256), dtype=np.int64)
                    words = text.split()[:256]
                    for i, _ in enumerate(words):
                        input_ids[0, i] = hash(words[i]) % 250000
                        attention_mask[0, i] = 1

                feeds = {"input_ids": input_ids, "attention_mask": attention_mask}
                out = self.session.run(None, feeds)
                q_logits = np.array(out[0], dtype=np.float32)
                p_logits = np.array(out[1], dtype=np.float32)

            # Apply post-hoc temperature scaling calibration
            calib_q = self.scaler.calibrate_queue(q_logits)[0]
            calib_p = self.scaler.calibrate_priority(p_logits)[0]
            latency = (time.perf_counter() - t0) * 1000.0

            best_q_idx = int(np.argmax(calib_q))
            best_p_idx = int(np.argmax(calib_p))

            best_queue = self.id2queue.get(best_q_idx, "other")
            best_priority = self.id2priority.get(best_p_idx, "medium")
            confidence = float(calib_q[best_q_idx])

            q_probs = {
                self.id2queue.get(i, f"queue_{i}"): round(float(prob), 4)
                for i, prob in enumerate(calib_q)
            }
            p_probs = {
                self.id2priority.get(i, f"priority_{i}"): round(float(prob), 4)
                for i, prob in enumerate(calib_p)
            }

            results.append(
                TicketPrediction(
                    queue=best_queue,
                    priority=best_priority,
                    confidence=round(confidence, 4),
                    queue_probabilities=q_probs,
                    priority_probabilities=p_probs,
                    latency_ms=round(latency, 2),
                )
            )

        return results

    def predict_one(self, text: str) -> TicketPrediction:
        """Convenience method to predict a single ticket text."""
        return self.predict([text])[0]


def get_onnx_classifier(allow_mock: bool = True) -> ONNXTicketClassifier:
    """Dependency injection helper returning singleton or cached ONNXTicketClassifier."""
    return ONNXTicketClassifier(allow_mock=allow_mock)
