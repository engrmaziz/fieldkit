"""Fieldkit Hello Service - test endpoint using common and llm packages."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fieldkit_common.health import health_router
from fieldkit_common.logging import get_logger, setup_logging
from fieldkit_common.otel import init_tracer
from fieldkit_common.settings import get_common_settings
from fieldkit_llm.client import get_llm_client
from pydantic import BaseModel

settings = get_common_settings()
setup_logging(service_name="hello-service", log_level=settings.log_level)
logger = get_logger("fieldkit.hello")
tracer = init_tracer("hello-service", settings.otel_exporter_otlp_endpoint)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("service_started", service="hello-service", environment=settings.environment)
    yield
    logger.info("service_stopped", service="hello-service")


app = FastAPI(
    title="Fieldkit Hello Service",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)


class EchoRequest(BaseModel):
    input: str


class EchoResponse(BaseModel):
    text: str


PROMPT_TEMPLATE = Path(__file__).parent.parent / "prompts" / "echo.jinja"


@app.post("/echo", response_model=EchoResponse)
async def echo(payload: EchoRequest) -> EchoResponse:
    """Ask Ollama via fieldkit-llm to echo input using Jinja prompt template and structured output."""
    client = get_llm_client()
    try:
        response = await client.structured_output_from_template(
            template_path=PROMPT_TEMPLATE,
            template_vars={"user_input": payload.input},
            response_model=EchoResponse,
            task="hello_echo",
        )
        return response
    except Exception as exc:
        logger.error("echo_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=f"LLM generation failed: {exc}") from exc
