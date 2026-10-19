"""Feedback router for capturing user thumbs up/down responses."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import anyio
from fastapi import APIRouter, Depends
from fieldkit_common.auth import Principal, get_current_principal
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/assistant", tags=["Feedback"])

FEEDBACK_FILE = Path("data/feedback.jsonl")


def _append_feedback(record: dict[str, Any]) -> None:
    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


class FeedbackRequest(BaseModel):
    """User feedback payload."""

    trace_id: str = Field(..., description="OpenTelemetry trace identifier or request ID")
    thumbs: Literal["up", "down"] = Field(..., description="Binary rating")
    comment: str | None = Field(default=None, description="Optional text critique or comment")
    route: str | None = Field(default=None, description="Execution route (rag, sql, both)")
    query: str | None = Field(default=None, description="Original user query")


class FeedbackResponse(BaseModel):
    """Feedback submission confirmation."""

    id: str
    status: Literal["recorded"] = "recorded"
    timestamp: str


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    request: FeedbackRequest,
    principal: Principal = Depends(get_current_principal),
) -> FeedbackResponse:
    """Submit thumbs up/down feedback for assistant interaction."""
    feedback_id = str(uuid.uuid4())
    ts = datetime.now(UTC).isoformat()

    record = {
        "id": feedback_id,
        "trace_id": request.trace_id,
        "thumbs": request.thumbs,
        "comment": request.comment,
        "route": request.route,
        "query": request.query,
        "username": principal.username,
        "roles": principal.roles,
        "plant": principal.plant,
        "created_at": ts,
    }

    await anyio.to_thread.run_sync(_append_feedback, record)

    return FeedbackResponse(
        id=feedback_id,
        status="recorded",
        timestamp=ts,
    )
