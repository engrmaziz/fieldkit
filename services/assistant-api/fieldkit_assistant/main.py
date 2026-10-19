"""Main FastAPI entrypoint for fieldkit-assistant-api."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fieldkit_common.logging import setup_logging

from fieldkit_assistant.routers import health, ingest
from fieldkit_assistant.settings import settings

setup_logging(service_name=settings.app_name)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup logic
    yield
    # Shutdown logic


app = FastAPI(
    title="Fieldkit Assistant API",
    description="Enterprise RAG and NL2SQL Assistant for Halden Industrie",
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

app.include_router(health.router)
app.include_router(ingest.router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Fieldkit Assistant API is running", "docs": "/docs"}
