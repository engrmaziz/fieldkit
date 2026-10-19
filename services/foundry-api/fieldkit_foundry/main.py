"""Fieldkit Foundry API Service."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fieldkit_common.health import health_router
from fieldkit_common.logging import get_logger, setup_logging
from fieldkit_common.otel import init_tracer
from fieldkit_common.settings import get_common_settings

from fieldkit_foundry.routers.drift import router as drift_router
from fieldkit_foundry.routers.objects import router as objects_router

settings = get_common_settings()
setup_logging(service_name="foundry-api", log_level=settings.log_level)
logger = get_logger("fieldkit.foundry")
tracer = init_tracer("foundry-api", settings.otel_exporter_otlp_endpoint)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("service_started", service="foundry-api", environment=settings.environment)
    yield
    logger.info("service_stopped", service="foundry-api")


app = FastAPI(
    title="Fieldkit Foundry API",
    version="0.1.0",
    description="Data fusion, lineage, governance, and drift API for Halden Industrie",
    lifespan=lifespan,
)

# Standard endpoints
app.include_router(health_router)
app.include_router(drift_router)
app.include_router(objects_router)
