"""Deterministic online citation and grounding verifier for RAG answers."""

import re

from fieldkit_retrieval.schemas import (
    ChunkCitation,
    GroundedAnswer,
    SentenceVerification,
    VerificationResult,
)


class CitationVerifier:
    """Validates citations, lexical overlap, and numerical precision of generated answers."""

    def __init__(
        self,
        min_overlap_score: float = 0.25,
        max_unsupported_ratio: float = 0.30,
    ) -> None:
        self.min_overlap_score = min_overlap_score
        self.max_unsupported_ratio = max_unsupported_ratio

    def _extract_numeric_tokens(self, text: str) -> set[str]:
        """Extract numeric quantities, measurements, and tolerances."""
        raw = re.findall(r"\b\d+(?:[\.,]\d+)?\b", text)
        # Normalize commas to dots for German floats (e.g. 0,20 -> 0.20)
        return {r.replace(",", ".") for r in raw}

    def _compute_token_overlap(self, sentence: str, reference: str) -> float:
        """Compute proportion of significant query words present in reference text."""
        s_words = [
            w.lower()
            for w in re.findall(r"\b[A-Za-z0-9\-ÄÖÜäöüß]+\b", sentence)
            if len(w) > 2
        ]
        if not s_words:
            return 1.0

        ref_words = {
            w.lower() for w in re.findall(r"\b[A-Za-z0-9\-ÄÖÜäöüß]+\b", reference)
        }
        matched = sum(1 for w in s_words if w in ref_words)
        return round(float(matched / len(s_words)), 4)

    def verify(
        self,
        answer: GroundedAnswer,
        citations: list[ChunkCitation],
    ) -> VerificationResult:
        """Verify grounding of every sentence against authorized cited context chunks."""
        # 1. Handle explicit refusal
        if answer.insufficient or not answer.answer_sentences:
            return VerificationResult(
                is_supported=True,
                supported_ratio=1.0,
                unsupported_count=0,
                sentence_verifications=[],
            )

        chunk_map = {c.citation_index: c for c in citations}
        valid_indices = set(chunk_map.keys())

        verifications: list[SentenceVerification] = []
        unsupported_count = 0

        for idx, s in enumerate(answer.answer_sentences, start=1):
            clean_text = s.text.strip()
            if not clean_text:
                continue

            valid_cits = [c for c in s.citations if c in valid_indices]

            if not valid_cits:
                # No valid citation provided for this sentence
                verifications.append(
                    SentenceVerification(
                        sentence_index=idx,
                        text=clean_text,
                        citations=s.citations,
                        valid_citations=[],
                        overlap_score=0.0,
                        numeric_match=False,
                        is_supported=False,
                        flag="missing_or_out_of_bounds_citation",
                    )
                )
                unsupported_count += 1
                continue

            # Concatenate cited chunk contents
            cited_reference = " ".join(
                f"{chunk_map[c].title} {' '.join(chunk_map[c].heading_path)} {chunk_map[c].content}"
                for c in valid_cits
            )

            # Check numerical claims
            s_nums = self._extract_numeric_tokens(clean_text)
            # Remove citation index numbers themselves from checking
            s_nums -= {str(c) for c in valid_cits}
            ref_nums = self._extract_numeric_tokens(cited_reference)

            numeric_match = True
            if s_nums:
                missing_nums = s_nums - ref_nums
                if missing_nums:
                    numeric_match = False

            # Check lexical overlap
            overlap = self._compute_token_overlap(clean_text, cited_reference)

            is_supported = (overlap >= self.min_overlap_score) and numeric_match
            flag = None
            if not is_supported:
                unsupported_count += 1
                if not numeric_match:
                    flag = "numeric_mismatch"
                else:
                    flag = "insufficient_overlap"

            verifications.append(
                SentenceVerification(
                    sentence_index=idx,
                    text=clean_text,
                    citations=s.citations,
                    valid_citations=valid_cits,
                    overlap_score=overlap,
                    numeric_match=numeric_match,
                    is_supported=is_supported,
                    flag=flag,
                )
            )

        total_sentences = max(1, len(verifications))
        supported_count = total_sentences - unsupported_count
        supported_ratio = round(supported_count / total_sentences, 4)
        unsupported_ratio = unsupported_count / total_sentences

        is_supported = unsupported_ratio <= self.max_unsupported_ratio

        return VerificationResult(
            is_supported=is_supported,
            supported_ratio=supported_ratio,
            unsupported_count=unsupported_count,
            sentence_verifications=verifications,
        )
