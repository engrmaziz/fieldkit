"""Data models and schemas for documents, chunks, and ACL permissions."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import (
    ARRAY,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class DocumentType(StrEnum):
    REGULATION = "regulation"
    STANDARD = "standard"
    FILING = "filing"
    SOP = "sop"
    POLICY = "policy"


class DocumentInput(BaseModel):
    """Input payload for a document prior to parsing and chunking."""

    title: str
    doc_type: DocumentType
    source_url: str
    content: str
    allowed_roles: list[str] = Field(
        default_factory=lambda: ["admin", "quality", "support", "legal"]
    )
    allowed_plants: list[str] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProcessedChunk(BaseModel):
    """Structured chunk ready for vectorization and relational persistence."""

    chunk_id: str
    doc_id: str
    chunk_index: int
    heading_path: list[str]
    content: str
    token_count: int
    language: str
    tsv_config: str
    allowed_roles: list[str]
    allowed_plants: list[str] | None = None


# ---------------------------------------------------------------------------
# SQLAlchemy Declarative Models (docs and chunks tables)
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    pass


class DocModel(Base):
    __tablename__ = "docs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    doc_type: Mapped[DocumentType] = mapped_column(
        SAEnum(DocumentType, name="doc_type_enum"), nullable=False
    )
    source_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    allowed_roles: Mapped[list[str]] = mapped_column(ARRAY(String(64)), nullable=False)
    allowed_plants: Mapped[list[str] | None] = mapped_column(ARRAY(String(32)), nullable=True)
    meta_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    chunks: Mapped[list["ChunkModel"]] = relationship(
        "ChunkModel", back_populates="document", cascade="all, delete-orphan"
    )


class ChunkModel(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    doc_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("docs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    heading_path: Mapped[list[str]] = mapped_column(ARRAY(String(256)), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str] = mapped_column(String(8), nullable=False)
    tsv_config: Mapped[str] = mapped_column(String(32), nullable=False)
    allowed_roles: Mapped[list[str]] = mapped_column(ARRAY(String(64)), nullable=False)
    allowed_plants: Mapped[list[str] | None] = mapped_column(ARRAY(String(32)), nullable=True)
    tsv_content: Mapped[Any | None] = mapped_column(TSVECTOR, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    document: Mapped[DocModel] = relationship("DocModel", back_populates="chunks")

    __table_args__ = (
        Index("idx_chunks_doc_chunk_idx", "doc_id", "chunk_index"),
        Index("idx_chunks_allowed_roles", "allowed_roles", postgresql_using="gin"),
        Index("idx_chunks_allowed_plants", "allowed_plants", postgresql_using="gin"),
        Index("idx_chunks_tsv_content", "tsv_content", postgresql_using="gin"),
    )
