"""Fieldkit multilingual ticket classification package."""

from .baselines import (
    BaseClassifier,
    DenseEmbeddingBaseline,
    LLMFewShotBaseline,
    LLMZeroShotBaseline,
    TfidfBaseline,
    TicketClassificationOutput,
)
from .calibration import (
    TemperatureScaler,
    nll_loss,
    softmax,
)
from .data import (
    ALLOWED_PRIORITIES,
    ALLOWED_QUEUES,
    QUEUE_DESCRIPTIONS,
    generate_ticket_corpus,
    load_hf_dataset,
    load_parquet_records,
    normalize_hf_priority,
    normalize_hf_queue,
    normalize_ticket_record,
    prepare_and_split_dataset,
    stratified_split,
)
from .infer import (
    ONNXTicketClassifier,
    TicketPrediction,
    get_onnx_classifier,
)

__version__ = "0.1.0"

__all__ = [
    "ALLOWED_PRIORITIES",
    "ALLOWED_QUEUES",
    "QUEUE_DESCRIPTIONS",
    "BaseClassifier",
    "DenseEmbeddingBaseline",
    "LLMFewShotBaseline",
    "LLMZeroShotBaseline",
    "TfidfBaseline",
    "TicketClassificationOutput",
    "TemperatureScaler",
    "softmax",
    "nll_loss",
    "generate_ticket_corpus",
    "load_hf_dataset",
    "load_parquet_records",
    "normalize_hf_priority",
    "normalize_hf_queue",
    "normalize_ticket_record",
    "prepare_and_split_dataset",
    "stratified_split",
    "ONNXTicketClassifier",
    "TicketPrediction",
    "get_onnx_classifier",
]
