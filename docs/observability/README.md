# Observability — OTel setup + Grafana guide

Stack: **OpenTelemetry Collector → Tempo (traces) + Prometheus (metrics) → Grafana**

- `logging.py` — structlog JSON, `request_id` + `trace_id` auto-injected
- `tracing.py` — OTel SDK; `configure_tracing()` sets the provider + OTLP exporter,
  `instrument_app()` auto-instruments FastAPI + asyncpg + httpx
- All Claude calls traced: duration, token count, model as span attributes

## Durum

| Parça | Durum |
|---|---|
| Trace akışı (collector → Tempo → Grafana) | ✅ kuruldu — bkz. `docs/build-log.md` adım 8 |
| Auto-instrumentation (FastAPI/asyncpg/httpx) | ✅ iki serviste aktif |
| Metrics (Prometheus + spanmetrics + dashboard) | 🔜 sıradaki dilim |

## Yerel kullanım

`make up` (veya `docker compose up`) ile stack ayağa kalkar. Trace'ler:

- **Grafana** → http://localhost:3000 (anonim erişim açık, login yok)
- **Explore → Tempo** datasource → son trace'ler; `service.name` ile `api` /
  `ai-engine` ayrışır.

Trace export'u `OTEL_EXPORTER_OTLP_ENDPOINT` ile kontrol edilir
(default `http://otel-collector:4317`). Boş bırakılırsa span'ler üretilir ama
gönderilmez — uygulama yine her yerde çalışır.

## Akış

```
api / ai-engine  --OTLP gRPC 4317-->  otel-collector  --OTLP-->  Tempo  <--query--  Grafana
   (instrument_app: FastAPI + asyncpg + httpx span'leri)
```
