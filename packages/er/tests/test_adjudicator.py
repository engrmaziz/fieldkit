"""Tests for LLM Grey-Zone Adjudicator, Batching, and Human Review Queue Routing."""

from __future__ import annotations

import pytest
from fieldkit_er.adjudicator import (
    CandidatePair,
    LLMAdjudicator,
    PairVerdict,
)


def test_batching_into_chunks_of_8() -> None:
    pairs = [
        CandidatePair(
            pair_id=f"pair_{i}",
            name_a=f"Vendor A {i}",
            street_a="Hauptstr 1",
            city_a="Hamburg",
            postcode_a="20095",
            country_a="DE",
            name_b=f"Vendor B {i}",
            street_b="Hauptstr 1",
            city_b="Hamburg",
            postcode_b="20095",
            country_b="DE",
            splink_prob=0.55,
        )
        for i in range(20)
    ]

    batches = LLMAdjudicator.chunk_pairs(pairs, batch_size=8)
    assert len(batches) == 3
    assert len(batches[0]) == 8
    assert len(batches[1]) == 8
    assert len(batches[2]) == 4


@pytest.mark.asyncio
async def test_adjudicator_fallback_matching_pair() -> None:
    adjudicator = LLMAdjudicator()
    pair = CandidatePair(
        pair_id="p_match",
        name_a="Müller Hydraulik GmbH",
        street_a="Industriestr. 10",
        city_a="Hamburg",
        postcode_a="20095",
        country_a="DE",
        name_b="MUELLER HYDRAULIK",
        street_b="Industriestrasse 10",
        city_b="Hamburg",
        postcode_b="20095",
        country_b="DE",
        splink_prob=0.62,
    )

    verdict: PairVerdict = await adjudicator.adjudicate_single_pair(pair)
    assert verdict.pair_id == "p_match"
    assert verdict.same_entity is True
    assert verdict.confidence >= 0.70
    assert not verdict.needs_review


@pytest.mark.asyncio
async def test_adjudicator_fallback_hard_negative() -> None:
    adjudicator = LLMAdjudicator()
    # Different company names in same city
    pair = CandidatePair(
        pair_id="p_diff",
        name_a="Hanseatic Marine Tools GmbH",
        street_a="Hafenstrasse 12",
        city_a="Hamburg",
        postcode_a="20457",
        country_a="DE",
        name_b="Hanseatic Steel Supply AG",
        street_b="Alsterufer 4",
        city_b="Hamburg",
        postcode_b="20354",
        country_b="DE",
        splink_prob=0.48,
    )

    verdict = await adjudicator.adjudicate_single_pair(pair)
    assert verdict.pair_id == "p_diff"
    assert verdict.same_entity is False
    assert verdict.confidence >= 0.70
    assert not verdict.needs_review


@pytest.mark.asyncio
async def test_adjudicator_low_confidence_routes_to_review_queue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adjudicator = LLMAdjudicator()

    async def mock_low_confidence(*args: object, **kwargs: object) -> object:
        from fieldkit_er.adjudicator import BatchAdjudicationResult, PairVerdict

        return BatchAdjudicationResult(
            verdicts=[
                PairVerdict(
                    pair_id="p_ambig",
                    same_entity=False,
                    confidence=0.55,
                    evidence=["Borderline match probability, insufficient differentiating data"],
                )
            ]
        )

    monkeypatch.setattr(
        adjudicator.llm_client, "structured_output_from_template", mock_low_confidence
    )

    pair = CandidatePair(
        pair_id="p_ambig",
        name_a="Schmidt",
        street_a=None,
        city_a="Berlin",
        postcode_a=None,
        country_a="DE",
        name_b="Schmied",
        street_b=None,
        city_b="Berlin",
        postcode_b=None,
        country_b="DE",
        splink_prob=0.50,
    )

    verdict = await adjudicator.adjudicate_single_pair(pair)
    assert verdict.confidence < 0.70
    assert verdict.needs_review is True
