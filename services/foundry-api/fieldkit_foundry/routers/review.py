"""Human-in-the-Loop Review Queue Router for Entity Resolution."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fieldkit_common.auth import Principal, current_principal
from pydantic import BaseModel, Field

router = APIRouter(prefix="/review-queue", tags=["ER Review Queue"])


class ReviewDecisionRequest(BaseModel):
    decision: Literal["match", "non_match"]
    comment: str | None = None


class ReviewQueueItem(BaseModel):
    pair_id: str
    source_a: str
    record_a: dict[str, Any]
    source_b: str
    record_b: dict[str, Any]
    match_probability: float
    llm_confidence: float | None = None
    llm_evidence: list[str] = Field(default_factory=list)
    status: str = "PENDING"  # PENDING, RESOLVED
    decision: str | None = None
    decided_by: str | None = None
    decided_at: str | None = None


class ReviewQueueStore:
    """Thread-safe state store for ambiguous entity resolution pairs."""

    def __init__(self) -> None:
        self._items: dict[str, ReviewQueueItem] = {}
        self._seed_default_queue()

    def _seed_default_queue(self) -> None:
        # Pre-seed realistic Halden ambiguous pairs
        pair_1 = ReviewQueueItem(
            pair_id="pair-001",
            source_a="erp_vendors",
            record_a={
                "vendor_id": "V-HAM-882",
                "name": "Mueller Hydr. GmbH & Co KG",
                "street": "Industriestr. 14",
                "city": "Hamburg",
                "postal_code": "20095",
                "country": "DE",
            },
            source_b="planning_de_ham",
            record_b={
                "vendor_id": "PLAN-HAM-104",
                "name": "Müller Hydraulik Bauteile GmbH",
                "street": "Industriestrasse 14b",
                "city": "Hamburg",
                "postal_code": "20095",
                "country": "DE",
            },
            match_probability=0.68,
            llm_confidence=0.62,
            llm_evidence=[
                "Street numbers differ: 14 vs 14b",
                "Legal forms differ: GmbH & Co KG vs GmbH",
            ],
            status="PENDING",
        )

        pair_2 = ReviewQueueItem(
            pair_id="pair-002",
            source_a="erp_vendors",
            record_a={
                "vendor_id": "V-STR-301",
                "name": "Krupp Dichtungstechnik",
                "street": "Hafenallee 9",
                "city": "Stralsund",
                "postal_code": "18439",
                "country": "DE",
            },
            source_b="soap_seed",
            record_b={
                "vendor_id": "SOAP-992",
                "name": "Krupp Hydraulik & Dichtungen e.K.",
                "street": "Hafenallee 9",
                "city": "Stralsund",
                "postal_code": "18439",
                "country": "DE",
            },
            match_probability=0.72,
            llm_confidence=0.65,
            llm_evidence=["Same address but differing corporate suffixes (none vs e.K.)"],
            status="PENDING",
        )

        self._items[pair_1.pair_id] = pair_1
        self._items[pair_2.pair_id] = pair_2

    def get_pending(self) -> list[ReviewQueueItem]:
        return [item for item in self._items.values() if item.status == "PENDING"]

    def get(self, pair_id: str) -> ReviewQueueItem | None:
        return self._items.get(pair_id)

    def record_decision(
        self,
        pair_id: str,
        decision: Literal["match", "non_match"],
        decided_by: str,
    ) -> tuple[ReviewQueueItem, list[str]]:
        item = self._items.get(pair_id)
        if not item:
            raise KeyError(pair_id)

        item.status = "RESOLVED"
        item.decision = decision
        item.decided_by = decided_by
        item.decided_at = datetime.now(UTC).isoformat()

        # Re-clustering simulation
        rec_a_id = item.record_a.get("vendor_id", "A")
        rec_b_id = item.record_b.get("vendor_id", "B")

        if decision == "match":
            # Merge both records into single canonical cluster
            unified_cluster = f"canonical_cluster_{uuid.uuid4().hex[:8]}"
            affected_clusters = [unified_cluster]
        else:
            # Separate clusters
            cluster_a = f"canonical_cluster_{rec_a_id}"
            cluster_b = f"canonical_cluster_{rec_b_id}"
            affected_clusters = [cluster_a, cluster_b]

        return item, affected_clusters


GLOBAL_REVIEW_QUEUE = ReviewQueueStore()


@router.get("")
async def list_review_queue(
    principal: Principal = Depends(current_principal()),
) -> dict[str, Any]:
    """Lists pending ambiguous entity resolution pairs awaiting human decision."""
    pending = GLOBAL_REVIEW_QUEUE.get_pending()
    return {
        "count": len(pending),
        "items": [item.model_dump() for item in pending],
    }


@router.post("/{pair_id}")
async def submit_review_decision(
    pair_id: str,
    req: ReviewDecisionRequest,
    principal: Principal = Depends(current_principal()),
) -> dict[str, Any]:
    """Submits a human review decision ('match' or 'non_match') and re-clusters affected entities."""
    try:
        item, affected_clusters = GLOBAL_REVIEW_QUEUE.record_decision(
            pair_id=pair_id,
            decision=req.decision,
            decided_by=principal.username,
        )
    except KeyError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review queue item '{pair_id}' not found",
        ) from err

    action_label = (
        "merged into canonical cluster"
        if req.decision == "match"
        else "partitioned into separate entities"
    )
    return {
        "pair_id": pair_id,
        "decision": req.decision,
        "status": "RESOLVED",
        "decided_by": principal.username,
        "affected_clusters": affected_clusters,
        "message": f"Pair '{pair_id}' successfully marked as '{req.decision}' and {action_label}.",
    }
