"""Permission-aware hybrid search engine combining BM25, vector search, and RRF."""

import math
import re

from fieldkit_common.auth import Principal
from fieldkit_llm.client import get_llm_client

from fieldkit_retrieval.models import ProcessedChunk
from fieldkit_retrieval.rerank import CrossEncoderReranker, ScoredCandidate


def compute_rrf_score(rank_bm25: int | None, rank_vector: int | None, k: int = 60) -> float:
    """Calculate Reciprocal Rank Fusion (RRF) score across two ranked result sets."""
    score = 0.0
    if rank_bm25 is not None and rank_bm25 > 0:
        score += 1.0 / (k + rank_bm25)
    if rank_vector is not None and rank_vector > 0:
        score += 1.0 / (k + rank_vector)
    return score


class HybridSearchEngine:
    """Hybrid search engine with SQL-grade ACL filtering, BM25, vector search, and RRF."""

    def __init__(self, k_rrf: int = 60, reranker_enabled: bool = True) -> None:
        self.k_rrf = k_rrf
        self.reranker = CrossEncoderReranker(enabled=reranker_enabled)
        self.llm_client = get_llm_client()
        self._chunks: dict[str, ProcessedChunk] = {}
        self._embeddings: dict[str, list[float]] = {}
        self._doc_frequencies: dict[str, int] = {}
        self._avg_doc_len: float = 50.0

    def load_in_memory_index(
        self,
        chunks: list[ProcessedChunk],
        embeddings: dict[str, list[float]] | None = None,
    ) -> None:
        """Load chunks into local inverted index and cache vectors."""
        self._chunks = {c.chunk_id: c for c in chunks}
        if embeddings:
            self._embeddings = dict(embeddings)

        # Build vocabulary document frequencies for in-memory BM25
        doc_freqs: dict[str, int] = {}
        total_tokens = 0
        for chunk in chunks:
            tokens = set(re.findall(r"\b\w+\b", chunk.content.lower()))
            total_tokens += len(tokens)
            for t in tokens:
                doc_freqs[t] = doc_freqs.get(t, 0) + 1

        self._doc_frequencies = doc_freqs
        self._avg_doc_len = total_tokens / max(1, len(chunks))

    def _is_accessible(self, chunk: ProcessedChunk, principal: Principal) -> bool:
        """Enforce strict ACL check: user roles overlap AND plant matches or user is admin."""
        # 1. Role check: caller must possess at least one permitted role (or admin)
        role_allowed = any(principal.has_role(r) for r in chunk.allowed_roles)
        if not role_allowed:
            return False

        # 2. Plant check: if document is plant-scoped, caller must belong to that plant or be admin
        if chunk.allowed_plants:
            if principal.has_role("admin"):
                return True
            if not principal.plant or principal.plant not in chunk.allowed_plants:
                return False

        return True

    def _score_bm25(self, query: str, content: str) -> float:
        """Compute standard Okapi BM25 score for a document."""
        q_tokens = [t.lower() for t in re.findall(r"\b\w+\b", query) if len(t) > 2]
        if not q_tokens:
            return 0.0

        p_tokens = [t.lower() for t in re.findall(r"\b\w+\b", content)]
        doc_len = len(p_tokens)
        if doc_len == 0:
            return 0.0

        # Term frequency counts
        tf_counts: dict[str, int] = {}
        for t in p_tokens:
            tf_counts[t] = tf_counts.get(t, 0) + 1

        n_docs = max(1, len(self._chunks))
        k1 = 1.5
        b = 0.75
        score = 0.0

        for q in q_tokens:
            tf = tf_counts.get(q, 0)
            if tf == 0:
                continue
            df = self._doc_frequencies.get(q, 1)
            idf = math.log((n_docs - df + 0.5) / (df + 0.5) + 1.0)
            numerator = tf * (k1 + 1.0)
            denominator = tf + k1 * (1.0 - b + b * (doc_len / max(1.0, self._avg_doc_len)))
            score += idf * (numerator / denominator)

        return score

    @staticmethod
    def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
        norm_a = math.sqrt(sum(a * a for a in vec_a)) or 1.0
        norm_b = math.sqrt(sum(b * b for b in vec_b)) or 1.0
        return dot / (norm_a * norm_b)

    async def search(
        self,
        query: str,
        principal: Principal,
        k: int = 6,
        rerank: bool = True,
        mode: str = "hybrid_rerank",
    ) -> list[ScoredCandidate]:
        """Execute permission-aware hybrid search with BM25, vector search, and RRF."""
        # 1. Filter chunks by principal permissions
        accessible_chunks = [c for c in self._chunks.values() if self._is_accessible(c, principal)]
        if not accessible_chunks:
            return []

        # 2. Score via BM25
        bm25_scored: list[tuple[str, float]] = []
        for c in accessible_chunks:
            score = self._score_bm25(query, c.content)
            bm25_scored.append((c.chunk_id, score))

        bm25_scored.sort(key=lambda x: x[1], reverse=True)
        bm25_ranks = {chunk_id: rank for rank, (chunk_id, score) in enumerate(bm25_scored, start=1)}

        # 3. Score via Vector similarity
        query_vectors = await self.llm_client.embed(query, is_query=True, task="retrieval_query")
        query_vec = query_vectors[0] if query_vectors else []

        vector_scored: list[tuple[str, float]] = []
        for c in accessible_chunks:
            # Fetch cached vector or generate
            if c.chunk_id not in self._embeddings:
                emb_res = await self.llm_client.embed(
                    c.content, is_query=False, task="retrieval_doc"
                )
                self._embeddings[c.chunk_id] = emb_res[0] if emb_res else []

            sim = self._cosine_similarity(query_vec, self._embeddings[c.chunk_id])
            vector_scored.append((c.chunk_id, sim))

        vector_scored.sort(key=lambda x: x[1], reverse=True)
        vector_ranks = {
            chunk_id: rank for rank, (chunk_id, sim) in enumerate(vector_scored, start=1)
        }

        # 4. Combine via Reciprocal Rank Fusion (RRF k=60)
        rrf_candidates: list[tuple[str, float]] = []
        for c in accessible_chunks:
            cid = c.chunk_id
            b_rank = bm25_ranks.get(cid)
            v_rank = vector_ranks.get(cid)
            score = compute_rrf_score(b_rank, v_rank, k=self.k_rrf)
            rrf_candidates.append((cid, score))

        rrf_candidates.sort(key=lambda x: x[1], reverse=True)
        top_20 = rrf_candidates[:20]

        # 5. Route selection based on mode and rerank flag
        effective_mode = mode
        if not rerank and effective_mode == "hybrid_rerank":
            effective_mode = "hybrid"

        if effective_mode == "bm25":
            selected = bm25_scored[:k]
            reranked = [
                ScoredCandidate(chunk_id=cid, content=self._chunks[cid].content, final_rank=idx)
                for idx, (cid, _) in enumerate(selected, start=1)
            ]
        elif effective_mode == "vector":
            selected = vector_scored[:k]
            reranked = [
                ScoredCandidate(chunk_id=cid, content=self._chunks[cid].content, final_rank=idx)
                for idx, (cid, _) in enumerate(selected, start=1)
            ]
        elif effective_mode == "hybrid":
            selected = rrf_candidates[:k]
            reranked = [
                ScoredCandidate(chunk_id=cid, content=self._chunks[cid].content, final_rank=idx)
                for idx, (cid, _) in enumerate(selected, start=1)
            ]
        else:  # hybrid_rerank
            passages_for_rerank = [(cid, self._chunks[cid].content) for cid, _ in top_20]
            reranked = await self.reranker.rerank(query, passages_for_rerank, top_k=k)

        # 6. Hydrate stage scores and metadata
        for candidate in reranked:
            cid = candidate.chunk_id
            chunk = self._chunks[cid]
            candidate.bm25_rank = bm25_ranks.get(cid)
            candidate.vector_rank = vector_ranks.get(cid)
            candidate.rrf_score = next((score for c_id, score in top_20 if c_id == cid), 0.0)
            candidate.heading_path = chunk.heading_path
            candidate.allowed_roles = chunk.allowed_roles
            candidate.allowed_plants = chunk.allowed_plants

        return reranked
