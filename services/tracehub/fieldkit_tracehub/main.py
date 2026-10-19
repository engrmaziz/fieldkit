"""FastAPI application for Fieldkit Tracehub (Project 7)."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fieldkit_common.logging import get_logger, setup_logging
from fieldkit_common.otel import init_tracer
from pydantic import BaseModel

from fieldkit_tracehub.config import settings
from fieldkit_tracehub.routers import evals, prompts, traces

setup_logging(service_name=settings.service_name)
logger = get_logger("tracehub")
tracer = init_tracer(
    service_name=settings.service_name,
    environment=settings.environment,
    endpoint=settings.otel_exporter_endpoint,
)


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info(
        "tracehub_starting",
        clickhouse_host=settings.clickhouse_host,
        clickhouse_port=settings.clickhouse_port,
        kafka_brokers=settings.kafka_brokers,
    )
    yield
    logger.info("tracehub_shutting_down")


app = FastAPI(
    title="Fieldkit Tracehub",
    description="On-premises LLM Observability, Evaluation & Anomaly Alerting Platform",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(traces.router)
app.include_router(prompts.router)
app.include_router(evals.router)


@app.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    """Liveness probe."""
    return HealthResponse(status="healthy", service="tracehub", version="0.1.0")


@app.get("/readyz", response_model=HealthResponse)
async def readyz() -> HealthResponse:
    """Readiness probe."""
    return HealthResponse(status="ready", service="tracehub", version="0.1.0")


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": "Fieldkit Tracehub",
        "description": "LLM Observability & Anomaly Alerting Platform",
        "docs": "/docs",
    }
