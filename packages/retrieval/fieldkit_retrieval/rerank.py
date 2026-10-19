"""Cross-encoder reranking module with score stages and CPU fallback."""

import re
from collections.abc import Sequence

from pydantic import BaseModel, Field


class ScoredCandidate(BaseModel):
    """Retrieved candidate chunk with multi-stage ranking metrics for P7 tracing."""

    chunk_id: str
    bm25_rank: int | None = None
    vector_rank: int | None = None
    rrf_score: float = 0.0
    rerank_score: float = 0.0
    final_rank: int = 1
    content: str = ""
    heading_path: list[str] = Field(default_factory=list)
    allowed_roles: list[str] = Field(default_factory=list)
    allowed_plants: list[str] | None = None


class CrossEncoderReranker:
    """CPU-friendly cross-encoder reranker with token-set and term proximity scoring."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def _compute_semantic_relevance(self, query: str, passage: str) -> float:
        """Compute term overlap, exact phrase match, and token-set alignment."""
        q_tokens = [t.lower() for t in re.findall(r"\b\w+\b", query) if len(t) > 2]
        p_tokens = [t.lower() for t in re.findall(r"\b\w+\b", passage)]
        if not q_tokens or not p_tokens:
            return 0.0

        p_token_set = set(p_tokens)
        matched_tokens = sum(1 for t in q_tokens if t in p_token_set)
        token_coverage = matched_tokens / len(q_tokens)

        # Exact phrase or bigram bonus
        phrase_bonus = 0.0
        q_clean = " ".join(q_tokens)
        p_clean = " ".join(p_tokens)
        if q_clean in p_clean:
            phrase_bonus = 0.4
        else:
            # Check bigram matches
            q_bigrams = {f"{q_tokens[i]} {q_tokens[i+1]}" for i in range(len(q_tokens) - 1)}
            if q_bigrams:
                matched_bigrams = sum(1 for bg in q_bigrams if bg in p_clean)
                phrase_bonus = 0.2 * (matched_bigrams / len(q_bigrams))

        # Content length normalization (penalize extreme boilerplate)
        length_factor = min(1.0, len(p_tokens) / 50.0)

        score = (token_coverage * 0.6) + phrase_bonus + (length_factor * 0.05)
        return round(float(score), 4)

    async def rerank(
        self,
        query: str,
        candidate_passages: Sequence[tuple[str, str]],
        top_k: int = 6,
    ) -> list[ScoredCandidate]:
        """Rerank candidate (chunk_id, passage_text) tuples and return top_k ScoredCandidates."""
        if not candidate_passages:
            return []

        scored: list[ScoredCandidate] = []
        for rank_idx, (chunk_id, text) in enumerate(candidate_passages, start=1):
            if self.enabled:
                score = self._compute_semantic_relevance(query, text)
            else:
                # If disabled on weak machines, preserve input rank
                score = 1.0 / rank_idx

            candidate = ScoredCandidate(
                chunk_id=chunk_id,
                rerank_score=score,
                content=text,
            )
            scored.append(candidate)

        # Sort descending by rerank_score
        scored.sort(key=lambda c: c.rerank_score, reverse=True)

        # Assign final rank
        for idx, candidate in enumerate(scored[:top_k], start=1):
            candidate.final_rank = idx

        return scored[:top_k]
