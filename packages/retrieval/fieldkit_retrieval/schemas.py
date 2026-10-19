"""Pydantic schemas for RAG generation, citation tracking, and grounding verification."""

from pydantic import BaseModel, Field


class SentenceWithCitations(BaseModel):
    """Individual answer sentence with explicit numeric citation indices."""

    text: str
    citations: list[int] = Field(default_factory=list)


class GroundedAnswer(BaseModel):
    """Structured response model output by LLM generation."""

    answer_sentences: list[SentenceWithCitations] = Field(default_factory=list)
    insufficient: bool = False
    refusal_reason: str | None = None

    def formatted_text(self) -> str:
        """Render sentences with inline bracketed citation markers."""
        if self.insufficient:
            return (
                self.refusal_reason
                or "I am sorry, but the requested information is not found in the documents you are authorized to access."
            )

        parts: list[str] = []
        for s in self.answer_sentences:
            clean_text = s.text.strip()
            if not clean_text:
                continue
            if s.citations:
                c_str = ", ".join(str(c) for c in sorted(set(s.citations)))
                parts.append(f"{clean_text} [{c_str}]")
            else:
                parts.append(clean_text)

        return " ".join(parts)


class SentenceVerification(BaseModel):
    """Fine-grained verification telemetry for an individual answer sentence."""

    sentence_index: int
    text: str
    citations: list[int]
    valid_citations: list[int]
    overlap_score: float
    numeric_match: bool
    is_supported: bool
    flag: str | None = None


class VerificationResult(BaseModel):
    """Aggregate result from deterministic grounding and citation verifier."""

    is_supported: bool
    supported_ratio: float
    unsupported_count: int
    sentence_verifications: list[SentenceVerification] = Field(default_factory=list)


class ChunkCitation(BaseModel):
    """Authoritative context passage metadata corresponding to a citation index."""

    citation_index: int
    chunk_id: str
    title: str
    heading_path: list[str] = Field(default_factory=list)
    content: str
    allowed_roles: list[str] = Field(default_factory=list)
    allowed_plants: list[str] | None = None


class RAGResponse(BaseModel):
    """End-to-end response payload returned by assistant service."""

    query: str
    answer: str
    sentences: list[SentenceWithCitations] = Field(default_factory=list)
    citations: list[ChunkCitation] = Field(default_factory=list)
    is_grounded: bool = True
    insufficient: bool = False
    retrieval_mode: str = "hybrid_rerank"
    verification: VerificationResult | None = None
