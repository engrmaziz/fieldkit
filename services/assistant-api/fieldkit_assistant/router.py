"""Hybrid Query Router (Rules + LLM Fallback) for Fieldkit Assistant."""

from __future__ import annotations

import re
from typing import Literal

import structlog
from fieldkit_llm.client import LLMClient
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

RouteType = Literal["rag", "sql", "both"]


class RouteDecision(BaseModel):
    """Routing determination result."""

    route: RouteType = Field(..., description="Determined route: 'rag', 'sql', or 'both'")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Routing confidence score")
    reasoning: str = Field(
        default="", description="Explanation or rule fired for the routing decision"
    )
    method: Literal["rule", "llm", "default"] = Field(
        default="rule", description="Method used to classify"
    )


# Explicit Regex Patterns
SQL_PATTERNS = [
    r"\b(how many|how much|total number of|sum of|average|avg|mean)\b",
    r"\b(top \d+|bottom \d+|highest|lowest|most expensive|cheapest)\b",
    r"\b(most frequent|least frequent|fastest|slowest)\b",
    r"\b(defect rate|defect metrics|late delivery frequency|late deliveries|delivery delay)\b",
    r"\b(spend|cost|total spend|unit cost|purchase order total|total amount)\b",
    r"\b(which (\d+|five|ten)?\s*(suppliers|parts|shipments|plants|purchase orders|quality incidents))\b",
    r"\b(list (\d+|all)?\s*(suppliers|parts|shipments|plants|purchase orders|incidents))\b",
    r"\b(po-\d+|shp-\d+|part-[a-z0-9]+|supp-[a-z0-9]+|inc-\d+)\b",
    r"\b(in q[1-4]|last quarter|last month|in 202[0-9]|in 201[0-9])\b",
    r"\b(group by|ordered by|sorted by|breakdown by|count by)\b",
    r"\b(delivered to (hamburg|stuttgart|munich|berlin|katowice))\b",
]

RAG_PATTERNS = [
    r"\b(what does (the )?.* (mandate|require|specify|say about|dictate))\b",
    r"\b(according to|under (the )?.* (regulation|directive|standard|law))\b",
    r"\b(eu machinery regulation|2023/1230|reach|gdpr|osha|pressure equipment|2014/68/eu)\b",
    r"\b(sec edgar|10-k( filing)?|annual report|filing)\b",
    r"\b(sop|standard operating procedure|quality policy|safety guideline|protocol)\b",
    r"\b(emergency shut-off|physical guard|lockout|tagout|ppe requirements)\b",
    r"\b(quarantine procedure|quarantine protocol|inspection steps|calibration protocol|audit checklist)\b",
    r"\b(iso 9001|iso 14001|iso 45001|din en|ce marking)\b",
    r"\b(legal obligations|regulatory requirements|compliance standard|export control)\b",
    r"\b(legal procedure|warranty claim|master contract|master services agreement)\b",
    r"\b(what is the procedure for|how should an operator|steps to report)\b",
]

BOTH_PATTERNS = [
    r"\b(and what (does|is) (the|our) (sop|policy|regulation|standard|procedure|manual))\b",
    r"\b(compare (our|the) (actual|metrics?|data) with (the )?(standard|regulation|sop|10-k|reported))\b",
    r"\b(how many .* and what (is|are) the (steps|rules|requirements))\b",
    r"\b(defects? .* and what does the quality manual require)\b",
]


class HybridRouter:
    """Hybrid query router combining deterministic rules with LLM fallback."""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm = llm_client or LLMClient()
        self._sql_regexes = [re.compile(p, re.IGNORECASE) for p in SQL_PATTERNS]
        self._rag_regexes = [re.compile(p, re.IGNORECASE) for p in RAG_PATTERNS]
        self._both_regexes = [re.compile(p, re.IGNORECASE) for p in BOTH_PATTERNS]

    def _match_rules(self, query: str) -> RouteDecision | None:
        """Evaluate deterministic regex and keyword rules with explicit priority."""
        # 1. Highest priority: explicit multi-intent / both patterns
        for pattern in self._both_regexes:
            if pattern.search(query):
                return RouteDecision(
                    route="both",
                    confidence=0.95,
                    reasoning=f"Matched explicit hybrid pattern: {pattern.pattern}",
                    method="rule",
                )

        # 2. Count rule matches for SQL and RAG
        sql_matches = [p.pattern for p in self._sql_regexes if p.search(query)]
        rag_matches = [p.pattern for p in self._rag_regexes if p.search(query)]

        # 3. If both match strongly -> Route "both"
        if sql_matches and rag_matches:
            return RouteDecision(
                route="both",
                confidence=0.88,
                reasoning=f"Matched both SQL rule ({sql_matches[0]}) and RAG rule ({rag_matches[0]})",
                method="rule",
            )

        # 4. Clear SQL match
        if sql_matches and not rag_matches:
            confidence = min(0.98, 0.85 + 0.05 * len(sql_matches))
            return RouteDecision(
                route="sql",
                confidence=confidence,
                reasoning=f"Matched SQL rule: {sql_matches[0]}",
                method="rule",
            )

        # 5. Clear RAG match
        if rag_matches and not sql_matches:
            confidence = min(0.98, 0.85 + 0.05 * len(rag_matches))
            return RouteDecision(
                route="rag",
                confidence=confidence,
                reasoning=f"Matched RAG rule: {rag_matches[0]}",
                method="rule",
            )

        # No rule matched
        return None

    async def route(self, query: str) -> RouteDecision:
        """Determine routing destination for a user query."""
        cleaned = query.strip()
        if not cleaned:
            return RouteDecision(
                route="rag",
                confidence=0.5,
                reasoning="Empty query defaulted to RAG",
                method="default",
            )

        # 1. Deterministic Rule Matching
        rule_decision = self._match_rules(cleaned)
        if rule_decision is not None:
            logger.info("router_rule_matched", query=cleaned, route=rule_decision.route)
            return rule_decision

        # 2. LLM Fallback Classifier
        logger.info("router_fallback_to_llm", query=cleaned)
        prompt = (
            "You are an enterprise query classifier for Halden Industrie GmbH.\n"
            "Classify the following user query into one of three execution routes:\n"
            "- 'rag': Questions asking about textual policies, regulations (EU Machinery, REACH, OSHA), "
            "SOPs, standards, inspection steps, or legal requirements.\n"
            "- 'sql': Questions asking about structured tabular operational data (suppliers, parts, plants, "
            "purchase orders, shipments, defect counts, quantities, delivery dates, or metric calculations).\n"
            "- 'both': Questions that require both tabular metrics and regulatory or procedural context to answer.\n\n"
            f'Query: "{cleaned}"\n\n'
            "Output your decision as a valid JSON object matching this schema:\n"
            '{"route": "rag" | "sql" | "both", "confidence": float, "reasoning": "brief reason"}'
        )

        try:
            raw_decision = await self.llm.structured_output(
                prompt=prompt,
                response_model=RouteDecision,
                temperature=0.0,
            )
            decision = RouteDecision.model_validate(raw_decision)
            # If LLM confidence is below threshold, safely default to 'both'
            if decision.confidence < 0.6:
                return RouteDecision(
                    route="both",
                    confidence=decision.confidence,
                    reasoning=f"LLM confidence {decision.confidence:.2f} < 0.6; defaulting to both. Detail: {decision.reasoning}",
                    method="llm",
                )
            decision.method = "llm"
            return decision
        except Exception as e:
            logger.warning("router_llm_failed_offline_fallback", error=str(e))
            # Fallback heuristic: check general question keywords
            lower = cleaned.lower()
            if any(w in lower for w in ["who", "what", "how", "why", "sop", "policy", "safe"]):
                return RouteDecision(
                    route="rag",
                    confidence=0.7,
                    reasoning="Offline fallback matched general information/procedural inquiry",
                    method="default",
                )
            return RouteDecision(
                route="sql",
                confidence=0.7,
                reasoning="Offline fallback matched structured data inquiry",
                method="default",
            )
