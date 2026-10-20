"""FastAPI route handlers for Document Intelligence."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fieldkit_common.logging import get_logger
from pydantic import BaseModel

from fieldkit_docai.config import settings
from fieldkit_docai.models import (
    DocumentStep,
    PageResult,
)
from fieldkit_docai.pipeline.classify import DocumentTypeException, validate_magic_bytes
from fieldkit_docai.storage import DocumentStore
from fieldkit_docai.worker import DocumentWorker

logger = get_logger("fieldkit.docai.api")
router = APIRouter()

# Global store and worker instances
store = DocumentStore()
worker = DocumentWorker(store=store)


class DocumentUploadResponse(BaseModel):
    document_id: str
    sha256: str
    filename: str
    mime_type: str
    file_size_bytes: int
    status: str
    message: str


class DocumentStatusResponse(BaseModel):
    document_id: str
    sha256: str
    filename: str
    mime_type: str
    file_size_bytes: int
    page_count: int
    document_type: str
    status: str
    error: str | None
    created_at: str
    updated_at: str


@router.post(
    "/documents",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_200_OK,
    tags=["Documents"],
)
async def upload_document(
    file: UploadFile = File(...),
) -> DocumentUploadResponse:
    """Upload document file (PDF/PNG/JPEG/TIFF, max 50 MB) with magic-byte validation and SHA-256 deduplication."""
    filename = file.filename or "uploaded_document"

    # 1. Read content
    content = await file.read()
    file_size = len(content)

    # 2. Enforce 50 MB size limit
    if file_size > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File size ({file_size / (1024 * 1024):.1f} MB) exceeds maximum allowed size (50 MB)",
        )

    # 3. Enforce magic-byte validation
    try:
        mime_type = validate_magic_bytes(content)
    except DocumentTypeException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid document type: magic bytes mismatch. {exc}",
        ) from exc

    # 4. Create document in store (with SHA-256 deduplication)
    doc = await store.create_document(
        filename=filename,
        content=content,
        mime_type=mime_type,
    )

    # 5. Kick off background processing
    asyncio.create_task(worker.process_document(doc.document_id))

    return DocumentUploadResponse(
        document_id=doc.document_id,
        sha256=doc.sha256,
        filename=doc.filename,
        mime_type=doc.mime_type,
        file_size_bytes=doc.file_size_bytes,
        status=doc.status.value,
        message="Document uploaded and queued for processing",
    )


@router.get(
    "/documents/{document_id}",
    response_model=DocumentStatusResponse,
    tags=["Documents"],
)
async def get_document_status(document_id: str) -> DocumentStatusResponse:
    """Retrieve document status, page count, and classification."""
    doc = await store.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    return DocumentStatusResponse(
        document_id=doc.document_id,
        sha256=doc.sha256,
        filename=doc.filename,
        mime_type=doc.mime_type,
        file_size_bytes=doc.file_size_bytes,
        page_count=doc.page_count,
        document_type=doc.document_type.value,
        status=doc.status.value,
        error=doc.error,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.get(
    "/documents/{document_id}/steps",
    response_model=list[DocumentStep],
    tags=["Documents"],
)
async def get_document_steps(document_id: str) -> list[DocumentStep]:
    """Retrieve audit timeline of all executed processing steps."""
    doc = await store.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    return await store.get_document_steps(document_id)


@router.get(
    "/documents/{document_id}/pages/{page_idx}",
    response_model=PageResult,
    tags=["Documents"],
)
async def get_document_page(document_id: str, page_idx: int) -> PageResult:
    """Retrieve OCR word boxes and layout blocks for a specific page."""
    doc = await store.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found",
        )
    if page_idx < 0 or page_idx >= len(doc.pages):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Page index {page_idx} out of range (document has {len(doc.pages)} pages)",
        )
    return doc.pages[page_idx]
