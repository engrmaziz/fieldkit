"""OpenTelemetry initialization helper."""

from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def init_tracer(service_name: str, endpoint: str | None = None) -> trace.Tracer:
    """Initialize OpenTelemetry tracer provider and return tracer."""
    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)

    if endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,  # type: ignore[import-not-found]
            )

            exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(exporter))
        except ImportError:
            # Fall back to console or noop if OTLP exporter not installed
            pass

    trace.set_tracer_provider(provider)
    return trace.get_tracer(service_name)
