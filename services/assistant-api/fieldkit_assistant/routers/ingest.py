"""Ingestion router for RAG corpus and documents."""

import json
from pathlib import Path

import anyio
from fastapi import APIRouter, Depends, HTTPException, status
from fieldkit_assistant.settings import settings
from fieldkit_common.auth import Principal, current_principal
from fieldkit_retrieval.chunker import StructureAwareChunker
from fieldkit_retrieval.models import DocumentInput, DocumentType, ProcessedChunk
from pydantic import BaseModel

router = APIRouter(prefix="/api/assistant", tags=["Ingest"])


class IngestSummary(BaseModel):
    total_documents: int
    processed_documents: int
    skipped_documents: int
    total_chunks: int
    total_tokens: int


# In-memory document & chunk registry for development and test assertions
DOC_CACHE: dict[str, dict] = {}
CHUNK_CACHE: dict[str, list[ProcessedChunk]] = {}


def _sync_ingest(manifest_file: Path, force_rechunk: bool) -> IngestSummary:
    chunker = StructureAwareChunker(target_tokens=400, max_tokens=512, overlap_pct=0.15)
    processed = 0
    skipped = 0
    total_chunks = 0
    total_tokens = 0

    with open(manifest_file, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            item = json.loads(line)
            doc_sha = item["sha256"]
            doc_file = Path(item["file_path"])

            if not force_rechunk and doc_sha in DOC_CACHE:
                skipped += 1
                chunks = CHUNK_CACHE.get(doc_sha, [])
                total_chunks += len(chunks)
                total_tokens += sum(c.token_count for c in chunks)
                continue

            if not doc_file.exists():
                continue

            with open(doc_file, encoding="utf-8") as df:
                content = df.read()

            doc_input = DocumentInput(
                title=item["title"],
                doc_type=DocumentType(item["doc_type"]),
                source_url=item["source_url"],
                content=content,
                allowed_roles=item.get("allowed_roles", ["admin"]),
                allowed_plants=item.get("allowed_plants"),
            )

            chunks = chunker.chunk_document(doc_input)
            DOC_CACHE[doc_sha] = item
            CHUNK_CACHE[doc_sha] = chunks

            processed += 1
            total_chunks += len(chunks)
            total_tokens += sum(c.token_count for c in chunks)

    return IngestSummary(
        total_documents=processed + skipped,
        processed_documents=processed,
        skipped_documents=skipped,
        total_chunks=total_chunks,
        total_tokens=total_tokens,
    )


@router.post("/ingest", response_model=IngestSummary)
async def ingest_corpus(
    force_rechunk: bool = False,
    principal: Principal = Depends(current_principal(required_roles=["admin"])),
) -> IngestSummary:
    """Ingest cached documents from manifest into structure-aware chunks with ACLs (Admin only)."""
    manifest_file = Path(settings.corpus_dir) / "manifest.jsonl"
    if not manifest_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Corpus manifest not found at {manifest_file}. Run scripts/fetch_corpus.py first.",
        )

    return await anyio.to_thread.run_sync(_sync_ingest, manifest_file, force_rechunk)


@router.get("/chunks", response_model=list[ProcessedChunk])
async def list_chunks(
    principal: Principal = Depends(current_principal(required_roles=["admin"])),
) -> list[ProcessedChunk]:
    """Retrieve all ingested chunks (Admin inspection)."""
    all_chunks = []
    for chunk_list in CHUNK_CACHE.values():
        all_chunks.extend(chunk_list)
    return all_chunks
