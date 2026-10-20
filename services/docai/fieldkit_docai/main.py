"""FastAPI application entrypoint for Fieldkit DocAI service (P4)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fieldkit_common.logging import get_logger

from fieldkit_docai.api import router

logger = get_logger("fieldkit.docai.main")

app = FastAPI(
    title="Fieldkit Document Intelligence API",
    description="Contract and Document Intelligence Engine with Span Grounding (Project 4)",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz", tags=["Probes"])
async def healthz() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "healthy", "service": "docai", "version": "0.1.0"}


@app.get("/readyz", tags=["Probes"])
async def readyz() -> dict[str, str]:
    """Readiness probe."""
    return {"status": "ready"}


app.include_router(router)
