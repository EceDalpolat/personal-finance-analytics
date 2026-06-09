# Observability — OTel setup + Grafana guide

- `logging.py` — structlog JSON, `request_id` + `trace_id` auto-injected
- `tracing.py` — OTel SDK, FastAPI + asyncpg + httpx auto-instrumented
- Stack: OpenTelemetry Collector → Prometheus (metrics) + Tempo (traces) → Grafana
- All Claude calls traced: duration, token count, model as span attributes
