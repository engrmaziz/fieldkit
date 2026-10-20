"""Fieldkit multilingual ticket classification package."""

from .baselines import (
    BaseClassifier,
    DenseEmbeddingBaseline,
    LLMFewShotBaseline,
    LLMZeroShotBaseline,
    TfidfBaseline,
    TicketClassificationOutput,
)
from .data import (
    ALLOWED_PRIORITIES,
    ALLOWED_QUEUES,
    QUEUE_DESCRIPTIONS,
    generate_ticket_corpus,
    load_parquet_records,
    normalize_ticket_record,
    prepare_and_split_dataset,
    stratified_split,
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
    "generate_ticket_corpus",
    "load_parquet_records",
    "normalize_ticket_record",
    "prepare_and_split_dataset",
    "stratified_split",
]
