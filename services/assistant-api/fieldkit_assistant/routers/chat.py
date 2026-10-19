"""Unified Chat router providing Hybrid Routing, SSE streaming, and conversation memory."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse
from fieldkit_assistant.cache import ResponseCache, compute_cache_key
from fieldkit_assistant.composer import AnswerComposer, UnifiedResponse
from fieldkit_assistant.memory import ConversationManager, QuestionRewriter
from fieldkit_assistant.router import HybridRouter
from fieldkit_common.auth import Principal, get_current_principal
from fieldkit_nl2sql.executor import SQLExecutor
from fieldkit_nl2sql.generator import NL2SQLGenerator
from fieldkit_nl2sql.linker import SchemaLinker
from fieldkit_nl2sql.validator import SQLValidator
from fieldkit_retrieval.chunker import StructureAwareChunker
from fieldkit_retrieval.generator import RAGGenerator
from fieldkit_retrieval.hybrid import HybridSearchEngine
from fieldkit_retrieval.indexer import BatchIndexer
from fieldkit_retrieval.models import DocumentInput, DocumentType, ProcessedChunk
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/assistant", tags=["Chat"])

# Singletons
_composer: AnswerComposer | None = None
_conv_manager = ConversationManager(max_turns=4)
_rewriter = QuestionRewriter()
_cache = ResponseCache(default_ttl_seconds=3600)


def get_composer() -> AnswerComposer:
    """Retrieve or initialize singleton AnswerComposer."""
    global _composer
    if _composer is None:
        # Initialize RAG Engine
        engine = HybridSearchEngine(k_rrf=60)
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

            engine.load_in_memory_index(chunks, embeddings=cached_vectors)

        rag_gen = RAGGenerator(search_engine=engine)

        # Initialize SQL Generator
        linker = SchemaLinker()
        validator = SQLValidator()
        executor = SQLExecutor()
        sql_gen = NL2SQLGenerator(schema_linker=linker, validator=validator, executor=executor)

        # Router
        router_inst = HybridRouter()
        _composer = AnswerComposer(rag_generator=rag_gen, sql_generator=sql_gen, router=router_inst)

    return _composer


class ChatRequest(BaseModel):
    query: str
    session_id: str | None = None
    route: str | None = Field(
        default=None, description="Optional override: 'rag', 'sql', or 'both'"
    )
    top_k: int = Field(default=6, ge=1, le=20)
    bypass_cache: bool = False


@router.post("/chat", response_model=UnifiedResponse)
async def chat(
    request: ChatRequest,
    principal: Principal = Depends(get_current_principal),
    x_cache_bypass: str | None = Header(default=None, alias="X-Cache-Bypass"),
) -> UnifiedResponse:
    """Unified conversational assistant endpoint routing to RAG, SQL, or both with caching."""
    composer = get_composer()
    bypass = request.bypass_cache or (
        x_cache_bypass is not None and x_cache_bypass.lower() == "true"
    )

    # 1. Conversation History & Follow-Up Rewriting
    session_id = request.session_id or f"anon-{principal.username}"
    session = _conv_manager.get_session(session_id)
    history = session.get_history()

    rewritten_query, _ = await _rewriter.rewrite(request.query, history)

    # 2. Check Exact-Match Response Cache
    cache_key = compute_cache_key(rewritten_query, principal)
    if not bypass:
        cached_data = _cache.get(cache_key)
        if cached_data is not None:
            cached_resp = UnifiedResponse(**cached_data)
            cached_resp.cached = True
            cached_resp.session_id = session_id
            return cached_resp

    # 3. Answer Composition
    resp = await composer.compose(
        query=request.query,
        rewritten_query=rewritten_query,
        principal=principal,
        forced_route=request.route,
        top_k=request.top_k,
    )
    resp.session_id = session_id

    # 4. Save to Cache & Update Memory
    if not bypass:
        _cache.set(cache_key, resp.model_dump())

    session.add_turn("user", request.query, resp.route)
    session.add_turn("assistant", resp.answer, resp.route)

    return resp


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    raw_request: Request,
    principal: Principal = Depends(get_current_principal),
    x_cache_bypass: str | None = Header(default=None, alias="X-Cache-Bypass"),
) -> StreamingResponse:
    """Stream unified response via Server-Sent Events (SSE)."""
    composer = get_composer()
    bypass = request.bypass_cache or (
        x_cache_bypass is not None and x_cache_bypass.lower() == "true"
    )

    session_id = request.session_id or f"anon-{principal.username}"
    session = _conv_manager.get_session(session_id)
    history = session.get_history()

    rewritten_query, _ = await _rewriter.rewrite(request.query, history)

    async def sse_event_stream() -> AsyncGenerator[str, None]:
        # Check disconnect
        if await raw_request.is_disconnected():
            return

        cache_key = compute_cache_key(rewritten_query, principal)
        resp: UnifiedResponse | None = None

        if not bypass:
            cached_data = _cache.get(cache_key)
            if cached_data is not None:
                resp = UnifiedResponse(**cached_data)
                resp.cached = True

        if resp is None:
            resp = await composer.compose(
                query=request.query,
                rewritten_query=rewritten_query,
                principal=principal,
                forced_route=request.route,
                top_k=request.top_k,
            )
            resp.session_id = session_id
            if not bypass:
                _cache.set(cache_key, resp.model_dump())
            session.add_turn("user", request.query, resp.route)
            session.add_turn("assistant", resp.answer, resp.route)

        # 1. Event: Route
        route_payload = {
            "route": resp.route,
            "confidence": resp.confidence,
            "rewritten_query": resp.rewritten_query,
            "cached": resp.cached,
        }
        yield f"event: route\ndata: {json.dumps(route_payload)}\n\n"

        # 2. Event: Sources (if RAG or Both)
        if resp.citations:
            sources_data = [c.model_dump() for c in resp.citations]
            yield f"event: sources\ndata: {json.dumps(sources_data)}\n\n"

        # 3. Event: SQL (if SQL or Both)
        if resp.sql:
            sql_payload = {
                "sql": resp.sql,
                "tables_used": resp.tables_used,
            }
            yield f"event: sql\ndata: {json.dumps(sql_payload)}\n\n"

        # 4. Event: Rows Preview (if SQL or Both)
        if resp.columns or resp.rows:
            preview_payload = {
                "columns": resp.columns,
                "rows": resp.rows[:10],
                "row_count": resp.row_count,
            }
            yield f"event: rows_preview\ndata: {json.dumps(preview_payload)}\n\n"

        # 5. Event: Tokens (stream answer in chunks)
        words = resp.answer.split(" ")
        for i in range(0, len(words), 3):
            if await raw_request.is_disconnected():
                return
            chunk_text = " ".join(words[i : i + 3]) + " "
            yield f"event: token\ndata: {json.dumps({'text': chunk_text})}\n\n"

        # 6. Event: Verification (if available)
        if resp.verification:
            yield f"event: verification\ndata: {json.dumps(resp.verification.model_dump())}\n\n"

        # 7. Event: Done
        yield "event: done\ndata: [DONE]\n\n"

    return StreamingResponse(sse_event_stream(), media_type="text/event-stream")
