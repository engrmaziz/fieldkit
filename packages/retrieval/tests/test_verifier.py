"""Tests for deterministic grounding and citation verifier."""

import pytest
from fieldkit_retrieval.schemas import (
    ChunkCitation,
    GroundedAnswer,
    SentenceWithCitations,
)
from fieldkit_retrieval.verifier import CitationVerifier


@pytest.fixture
def sample_citations() -> list[ChunkCitation]:
    return [
        ChunkCitation(
            citation_index=1,
            chunk_id="chunk-101",
            title="SOP-HAM-201: Plant Hamburg Honing Surface Finish",
            heading_path=["Plant Hamburg", "Machining Operations", "Surface Finish"],
            content="Honing surface roughness Ra must be between 0.20 and 0.40 um for hydraulic cylinder barrels in Hamburg DE-HAM.",
            allowed_roles=["quality", "admin"],
            allowed_plants=["DE-HAM"],
        ),
        ChunkCitation(
            citation_index=2,
            chunk_id="chunk-102",
            title="Global Safety Guideline: PPE",
            heading_path=["Global SOP", "General", "PPE Requirements"],
            content="Personal protective equipment mandatory: EN 388 nitrile gloves and EN 166 safety goggles during fluid transfers.",
            allowed_roles=["admin", "quality", "support"],
            allowed_plants=None,
        ),
    ]


def test_citation_bounds_validation(sample_citations: list[ChunkCitation]) -> None:
    """Verify that citations outside the available chunk indices [1..n] are stripped."""
    verifier = CitationVerifier()
    answer = GroundedAnswer(
        answer_sentences=[
            SentenceWithCitations(
                text="Honing surface roughness must meet Ra 0.20 um specifications in Hamburg.",
                citations=[1, 99],  # 99 is out of bounds (only 1, 2 exist)
            ),
        ],
        insufficient=False,
    )

    result = verifier.verify(answer, sample_citations)
    assert len(result.sentence_verifications) == 1
    s_verif = result.sentence_verifications[0]
    assert 1 in s_verif.valid_citations
    assert 99 not in s_verif.valid_citations
    assert s_verif.is_supported is True


def test_token_and_entity_overlap_supported(sample_citations: list[ChunkCitation]) -> None:
    """Verify that a sentence accurately citing factual contents is verified as supported."""
    verifier = CitationVerifier()
    answer = GroundedAnswer(
        answer_sentences=[
            SentenceWithCitations(
                text="In plant Hamburg, hydraulic cylinder barrels require honing surface roughness Ra between 0.20 and 0.40 um.",
                citations=[1],
            ),
            SentenceWithCitations(
                text="Operators must wear EN 388 nitrile gloves and EN 166 safety goggles during fluid transfers.",
                citations=[2],
            ),
        ],
        insufficient=False,
    )

    result = verifier.verify(answer, sample_citations)
    assert result.is_supported is True
    assert result.supported_ratio == 1.0
    assert result.unsupported_count == 0


def test_numeric_precision_mismatch_flags_unsupported(sample_citations: list[ChunkCitation]) -> None:
    """Verify that hallucinated numerical values not found in cited chunk fail verification."""
    verifier = CitationVerifier()
    answer = GroundedAnswer(
        answer_sentences=[
            SentenceWithCitations(
                text="Honing surface roughness Ra must be 0.85 um according to plant rules.",  # 0.85 um does not exist in chunk (0.20-0.40)
                citations=[1],
            ),
        ],
        insufficient=False,
    )

    result = verifier.verify(answer, sample_citations)
    s_verif = result.sentence_verifications[0]
    assert s_verif.numeric_match is False
    assert s_verif.is_supported is False
    assert result.is_supported is False


def test_unsupported_ratio_threshold(sample_citations: list[ChunkCitation]) -> None:
    """Verify that if > 30% of sentences are unsupported, overall result is marked unsupported."""
    verifier = CitationVerifier(max_unsupported_ratio=0.30)
    answer = GroundedAnswer(
        answer_sentences=[
            SentenceWithCitations(
                text="Honing surface roughness Ra is between 0.20 and 0.40 um in Hamburg.",
                citations=[1],
            ),
            SentenceWithCitations(
                text="The secret nuclear submarine blueprint is stored in vault 42.",  # Hallucinated
                citations=[1],
            ),
        ],
        insufficient=False,
    )

    result = verifier.verify(answer, sample_citations)
    # 1 supported, 1 unsupported -> 50% unsupported (> 30%)
    assert result.unsupported_count == 1
    assert result.supported_ratio == 0.5
    assert result.is_supported is False


def test_insufficient_answer_bypasses_citations() -> None:
    """Verify that an explicit refusal (insufficient=True) is accepted as valid without citations."""
    verifier = CitationVerifier()
    answer = GroundedAnswer(
        answer_sentences=[],
        insufficient=True,
        refusal_reason="I am sorry, but the requested information is not found in the documents you are authorized to access.",
    )

    result = verifier.verify(answer, citations=[])
    assert result.is_supported is True
    assert result.supported_ratio == 1.0
    assert result.unsupported_count == 0
