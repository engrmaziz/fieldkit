"""Base connector abstractions and RawBatch protocol."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RawBatch:
    """A batch of raw data extracted from an enterprise source."""

    source_id: str
    batch_no: int
    raw_bytes: bytes
    records: list[dict[str, Any]]
    source_row_ref: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class IngestContext:
    """Context and runtime options for an ingestion run."""

    run_id: str
    source_name: str
    batch_size: int = 5000
    options: dict[str, Any] = field(default_factory=dict)


class Connector(ABC):
    """Abstract connector protocol for Halden Industrie source ingestion."""

    @abstractmethod
    def extract(self, ctx: IngestContext) -> AsyncIterator[RawBatch]:
        """Extracts raw batches from the data source."""
        ...
