"""Health and readiness endpoints for FastAPI services."""

from fastapi import APIRouter
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str


health_router = APIRouter(tags=["health"])


@health_router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    """Liveness probe."""
    return HealthResponse(status="ok", service="fieldkit")


@health_router.get("/readyz", response_model=HealthResponse)
async def readyz() -> HealthResponse:
    """Readiness probe."""
    return HealthResponse(status="ready", service="fieldkit")
