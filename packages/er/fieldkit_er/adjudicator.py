"""LLM Grey-Zone Adjudicator for Entity Resolution.

Evaluates ambiguous candidate supplier pairs with match probability in [T_low, T_high).
Batches up to 8 pairs per prompt to minimize latency and token overhead.
Pairs with confidence < 0.70 are routed to the human review queue.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fieldkit_llm.client import LLMClient
from pydantic import BaseModel, Field

from fieldkit_er.normalize import normalize_name, normalize_street, normalize_text


class PairVerdict(BaseModel):
    """Verdict for an individual candidate supplier pair."""

    pair_id: str = Field(description="Unique ID of the candidate pair")
    same_entity: bool = Field(description="True if both records represent the exact same entity")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")
    evidence: list[str] = Field(default_factory=list, description="Key supporting evidence")

    @property
    def needs_review(self) -> bool:
        """Threshold: pairs with confidence < 0.70 require human review."""
        return self.confidence < 0.70


class BatchAdjudicationResult(BaseModel):
    """Structured Pydantic response for batch of adjudicated pairs."""

    verdicts: list[PairVerdict] = Field(description="List of pair verdicts")


@dataclass
class CandidatePair:
    """Pair of candidate supplier records for adjudication."""

    pair_id: str
    name_a: str | None
    street_a: str | None
    city_a: str | None
    postcode_a: str | None
    country_a: str | None
    name_b: str | None
    street_b: str | None
    city_b: str | None
    postcode_b: str | None
    country_b: str | None
    splink_prob: float = 0.50

    def to_dict(self) -> dict[str, Any]:
        return {
            "pair_id": self.pair_id,
            "name_a": self.name_a or "",
            "street_a": self.street_a or "",
            "city_a": self.city_a or "",
            "postcode_a": self.postcode_a or "",
            "country_a": self.country_a or "",
            "name_b": self.name_b or "",
            "street_b": self.street_b or "",
            "city_b": self.city_b or "",
            "postcode_b": self.postcode_b or "",
            "country_b": self.country_b or "",
            "splink_prob": self.splink_prob,
        }


class LLMAdjudicator:
    """Batched LLM Adjudicator with deterministic fallback."""

    def __init__(self, prompt_template_path: Path | str | None = None) -> None:
        self.template_path = Path(
            prompt_template_path or "packages/llm/prompts/er_adjudicate.jinja"
        )
        self.llm_client = LLMClient()

    @staticmethod
    def chunk_pairs(pairs: list[CandidatePair], batch_size: int = 8) -> list[list[CandidatePair]]:
        """Splits pairs into batches of at most batch_size (default: 8)."""
        return [pairs[i : i + batch_size] for i in range(0, len(pairs), batch_size)]

    async def adjudicate_batch(self, pairs: list[CandidatePair]) -> list[PairVerdict]:
        """Adjudicates a batch of up to 8 candidate pairs using packages/llm."""
        if not pairs:
            return []

        dict_pairs = [p.to_dict() for p in pairs]

        try:
            res = await self.llm_client.structured_output_from_template(
                template_path=self.template_path,
                template_vars={"pairs": dict_pairs},
                response_model=BatchAdjudicationResult,
                task="er_adjudicate",
                model=os.getenv("OLLAMA_MODEL_DEFAULT", "qwen3.5:4b"),
                temperature=0.0,
            )
            # Map verdicts by pair_id
            verdict_map = {v.pair_id: v for v in res.verdicts}
            return [verdict_map.get(p.pair_id) or self._fallback_adjudicate_pair(p) for p in pairs]
        except Exception:
            # Deterministic heuristic fallback
            return [self._fallback_adjudicate_pair(p) for p in pairs]

    async def adjudicate_single_pair(self, pair: CandidatePair) -> PairVerdict:
        """Adjudicates a single candidate pair."""
        results = await self.adjudicate_batch([pair])
        return results[0]

    def _fallback_adjudicate_pair(self, pair: CandidatePair) -> PairVerdict:
        """Deterministic heuristic rule fallback when LLM is unavailable."""
        n_a = normalize_name(pair.name_a)
        n_b = normalize_name(pair.name_b)
        st_a = normalize_street(pair.street_a)
        st_b = normalize_street(pair.street_b)
        c_a = normalize_text(pair.city_a)
        c_b = normalize_text(pair.city_b)
        pc_a = normalize_text(pair.postcode_a)
        pc_b = normalize_text(pair.postcode_b)

        # 1. Sparse attributes check -> Low confidence -> Review queue
        if (not st_a and not st_b) and (not pc_a and not pc_b) and (n_a != n_b):
            return PairVerdict(
                pair_id=pair.pair_id,
                same_entity=False,
                confidence=0.55,
                evidence=["Sparse address attributes; ambiguous name similarity requires review"],
            )

        # 2. Strong match on normalized names + address
        names_match = (n_a == n_b) or (n_a in n_b) or (n_b in n_a)
        cities_match = (c_a == c_b) and bool(c_a)
        postcodes_match = (pc_a == pc_b) and bool(pc_a)

        if names_match and (postcodes_match or cities_match):
            return PairVerdict(
                pair_id=pair.pair_id,
                same_entity=True,
                confidence=0.92,
                evidence=[
                    f"Normalized names aligned ('{n_a}' ~ '{n_b}')",
                    f"Location matches: city='{c_a}', postcode='{pc_a}'",
                ],
            )

        # 3. Hard negative: distinct addresses or distinct specific tokens in same city
        tokens_a = set(n_a.split())
        tokens_b = set(n_b.split())
        token_overlap = len(tokens_a & tokens_b)
        different_postcodes = bool(pc_a and pc_b and pc_a != pc_b)
        different_streets = bool(st_a and st_b and st_a != st_b)
        distinct_tokens = tokens_a ^ tokens_b

        if cities_match and (
            token_overlap == 0
            or (len(distinct_tokens) >= 2 and (different_postcodes or different_streets))
        ):
            return PairVerdict(
                pair_id=pair.pair_id,
                same_entity=False,
                confidence=0.88,
                evidence=[
                    f"Distinct supplier attributes ('{n_a}' at '{st_a}', '{pc_a}' vs '{n_b}' at '{st_b}', '{pc_b}') in same city ('{c_a}')",
                ],
            )

        # 4. Default based on splink_prob
        is_same = pair.splink_prob >= 0.50
        conf = 0.72 if (pair.splink_prob >= 0.75 or pair.splink_prob <= 0.25) else 0.60
        return PairVerdict(
            pair_id=pair.pair_id,
            same_entity=is_same,
            confidence=conf,
            evidence=[f"Heuristic fallback using link probability {pair.splink_prob:.2f}"],
        )
