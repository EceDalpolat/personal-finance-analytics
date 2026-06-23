"""OpenTelemetry tracing setup. Exports to the OTel collector when
OTEL_EXPORTER_OTLP_ENDPOINT is set; otherwise spans are created but not
exported (no-op exporter) so the app runs anywhere. Full collector wiring
and auto-instrumentation land in the observability step."""

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


def get_tracer(name: str = "api"):
    return trace.get_tracer(name)
