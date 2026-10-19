"""OpenTelemetry initialization and telemetry governance helpers."""

from __future__ import annotations

import os
import re
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import (
    DEPLOYMENT_ENVIRONMENT,
    SERVICE_NAME,
    SERVICE_VERSION,
    Resource,
)
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Pre-compiled PII detection regular expressions
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
IBAN_REGEX = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")
CREDIT_CARD_REGEX = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")
PHONE_REGEX = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b")


def mask_pii(text: str) -> str:
    """Mask common PII patterns (emails, IBANs, phone numbers, credit cards)."""
    if not text:
        return ""
    masked = EMAIL_REGEX.sub("[EMAIL]", text)
    masked = IBAN_REGEX.sub("[IBAN]", masked)
    masked = CREDIT_CARD_REGEX.sub("[CREDIT_CARD]", masked)
    masked = PHONE_REGEX.sub("[PHONE]", masked)
    return masked


def sanitize_and_truncate(text: str, max_bytes: int = 4096) -> str:
    """Mask PII and truncate text to a maximum byte length for span events."""
    masked = mask_pii(text)
    encoded = masked.encode("utf-8")
    if len(encoded) <= max_bytes:
        return masked
    suffix = "... [truncated]"
    truncated_raw = encoded[:max_bytes].decode("utf-8", errors="ignore")
    return f"{truncated_raw}{suffix}"


def init_tracer(
    service_name: str,
    version: str = "0.1.0",
    environment: str = "development",
    endpoint: str | None = None,
) -> trace.Tracer:
    """Initialize OpenTelemetry tracer provider with standard Fieldkit resource attributes."""
    target_endpoint = endpoint or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")

    resource_attributes: dict[str, Any] = {
        SERVICE_NAME: service_name,
        SERVICE_VERSION: version,
        DEPLOYMENT_ENVIRONMENT: environment,
    }
    resource = Resource.create(resource_attributes)
    provider = TracerProvider(resource=resource)

    if target_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,  # type: ignore[import-not-found]
            )

            exporter = OTLPSpanExporter(endpoint=target_endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(exporter))
        except ImportError:
            # Fall back gracefully if OTLP gRPC package is not in minimal environment
            pass

    trace.set_tracer_provider(provider)
    return trace.get_tracer(service_name)


def get_tracer(service_name: str) -> trace.Tracer:
    """Get an OpenTelemetry tracer for the given service name."""
    return trace.get_tracer(service_name)
