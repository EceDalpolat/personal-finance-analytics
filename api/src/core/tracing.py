"""OpenTelemetry tracing. configure_tracing() sets up the provider and exports
to the OTel collector when OTEL_EXPORTER_OTLP_ENDPOINT is set (otherwise spans
are created but not exported, so the app runs anywhere). instrument_app()
auto-instruments FastAPI + asyncpg + httpx."""

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_configured = False


def configure_tracing(service_name: str, otlp_endpoint: str | None) -> None:
    global _configured
    if _configured:
        return
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    if otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True))
        )
    trace.set_tracer_provider(provider)
    _configured = True


def instrument_app(app) -> None:
    """Auto-instrument the FastAPI app and its outbound clients (asyncpg for the
    DB pool, httpx for the ai-engine proxy and Superset calls). Call once when
    the app is created."""
    from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    FastAPIInstrumentor.instrument_app(app)
    AsyncPGInstrumentor().instrument()
    HTTPXClientInstrumentor().instrument()


def get_tracer(name: str = "api"):
    return trace.get_tracer(name)
