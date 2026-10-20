"""Data models and schemas for Document Intelligence."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class DocumentType(StrEnum):
    DELIVERY_NOTE = "delivery_note"
    CONTRACT = "contract"
    OTHER = "other"


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class WordBox(BaseModel):
    """Bounding box and confidence for an individual extracted word."""

    text: str
    bbox: list[int] = Field(description="[x0, y0, x1, y1] pixel coordinates")
    confidence: float = Field(ge=0.0, le=1.0)


class LayoutBlock(BaseModel):
    """Segmented visual or semantic layout block on a document page."""

    block_id: str
    page_idx: int
    block_type: str = Field(description="header, paragraph, table, key_value, footer")
    bbox: list[int] = Field(description="[x0, y0, x1, y1] pixel coordinates")
    text: str = ""
    confidence: float = 1.0
    cells: list[list[str]] | None = None  # Table cells if block_type == 'table'


class PageResult(BaseModel):
    """Processed page artifact with text, OCR bounding boxes, and layout."""

    page_idx: int
    width: int
    height: int
    text: str
    source: str = "native"  # 'native' or 'tesseract'
    deskew_angle: float = 0.0
    is_scanned: bool = False
    word_boxes: list[WordBox] = Field(default_factory=list)
    layout_blocks: list[LayoutBlock] = Field(default_factory=list)


class DocumentStep(BaseModel):
    """Audited execution step in the document pipeline."""

    step_id: str
    document_id: str
    step_name: str
    status: StepStatus = StepStatus.PENDING
    duration_ms: float = 0.0
    error: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    completed_at: str | None = None


class DocumentRecord(BaseModel):
    """Persistent document metadata entity."""

    document_id: str
    sha256: str
    filename: str
    mime_type: str
    file_size_bytes: int
    page_count: int = 0
    document_type: DocumentType = DocumentType.OTHER
    status: DocumentStatus = DocumentStatus.UPLOADED
    error: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    pages: list[PageResult] = Field(default_factory=list)
