"""Chat router providing grounded RAG question-answering and streaming SSE."""

import json
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from fieldkit_common.auth import Principal, get_current_principal
from fieldkit_retrieval.chunker import StructureAwareChunker
from fieldkit_retrieval.generator import RAGGenerator
from fieldkit_retrieval.hybrid import HybridSearchEngine
from fieldkit_retrieval.indexer import BatchIndexer
from fieldkit_retrieval.models import DocumentInput, DocumentType, ProcessedChunk
from fieldkit_retrieval.schemas import RAGResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/assistant", tags=["Chat"])

# Global shared search engine and generator
_engine: HybridSearchEngine | None = None
_generator: RAGGenerator | None = None


def get_generator() -> RAGGenerator:
    """Retrieve or initialize singleton RAG generator with in-memory corpus."""
    global _engine, _generator
    if _generator is None:
        _engine = HybridSearchEngine(k_rrf=60)
        manifest_path = Path("data/raw/corpus/manifest.jsonl")
        if manifest_path.exists():
            chunker = StructureAwareChunker()
            chunks: list[ProcessedChunk] = []
            with open(manifest_path, encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    meta = json.loads(line)
                    p = Path(meta["file_path"])
                    if not p.exists():
                        continue
                    doc = DocumentInput(
                        title=meta["title"],
                        doc_type=DocumentType(meta["doc_type"]),
                        source_url=meta["source_url"],
                        content=p.read_text(encoding="utf-8"),
                        allowed_roles=meta["allowed_roles"],
                        allowed_plants=meta["allowed_plants"],
                        metadata={"id": meta["id"]},
                    )
                    chunks.extend(chunker.chunk_document(doc))

            checkpoint_path = Path("data/raw/corpus/embeddings_checkpoint.json")
            cached_vectors = None
            if checkpoint_path.exists():
                indexer = BatchIndexer(checkpoint_path=checkpoint_path)
                cached_vectors = indexer._cached_embeddings

            _engine.load_in_memory_index(chunks, embeddings=cached_vectors)

        _generator = RAGGenerator(search_engine=_engine)

    return _generator


class ChatRequest(BaseModel):
    query: str
    top_k: int = Field(default=6, ge=1, le=20)
    retrieval_mode: str = Field(default="hybrid_rerank")


@router.post("/chat", response_model=RAGResponse)
async def chat(
    request: ChatRequest,
    principal: Principal = Depends(get_current_principal),
) -> RAGResponse:
    """Ask a question against Halden documentation with verified citations and ACL isolation."""
    generator = get_generator()
    return await generator.generate(
        query=request.query,
        principal=principal,
        top_k=request.top_k,
        retrieval_mode=request.retrieval_mode,
    )


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    principal: Principal = Depends(get_current_principal),
) -> StreamingResponse:
    """Stream grounded answer via Server-Sent Events (sources -> tokens -> verification)."""
    generator = get_generator()

    async def sse_event_stream() -> AsyncGenerator[str, None]:
        response = await generator.generate(
            query=request.query,
            principal=principal,
            top_k=request.top_k,
            retrieval_mode=request.retrieval_mode,
        )

        # 1. Emit retrieved sources event
        sources_data = [c.model_dump() for c in response.citations]
        yield f"event: sources\ndata: {json.dumps(sources_data)}\n\n"

        # 2. Emit answer tokens event
        words = response.answer.split(" ")
        for i in range(0, len(words), 3):
            chunk_text = " ".join(words[i : i + 3]) + " "
            yield f"event: answer\ndata: {json.dumps({'text': chunk_text})}\n\n"

        # 3. Emit verification event
        verif_data = response.verification.model_dump() if response.verification else {}
        yield f"event: verification\ndata: {json.dumps(verif_data)}\n\n"

        # 4. Emit done event
        yield "event: done\ndata: [DONE]\n\n"

    return StreamingResponse(sse_event_stream(), media_type="text/event-stream")
