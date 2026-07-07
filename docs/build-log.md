# Build Log — Progress Record

A cumulative record of which step the project is on.
Each step: **what was done**, **why**, and a **commit** reference. Upcoming items at the top.

Ordering follows the data flow in `docs/architecture.md`:
`mock-data → source-db → analytics-db (FDW) → dbt → ai-engine → api → superset → observability`

---

## 🔜 Next steps

- [ ] **Superset dashboard content** — create datasets + charts + a dashboard on the `analytics` datasource (via the UI or a `superset import-dashboards` export) and wire the `dashboard_id` into the embed flow. (Infrastructure — service, embedded config, guest tokens — was completed in step 10.)
- [ ] **Scheduled runners** — ai-engine has anomaly/recommendation runner classes but no scheduler triggering them on a timer inside the container (CLAUDE.md: "scheduled runners run on a timer inside the container").

---

## ✅ Completed

### 10. Superset — service + embedded infrastructure
**Commit:** _(not committed yet)_

Superset added to the compose stack; embedded dashboard + guest token infrastructure is in place.
- `superset/superset_config.py` — from TODO to a real config: `EMBEDDED_SUPERSET` feature flag, `GUEST_ROLE_NAME=Gamma`, 300s guest token TTL, Talisman disabled + CORS enabled for iframe embeds; metadata DB is SQLite on the `superset-data` volume (analytical data already lives in analytics-db).
- `superset/init.sh` — idempotent bootstrap: `db upgrade` → admin user → `superset init` → registers analytics-db as the `analytics` datasource via `set_database_uri`.
- `docker-compose.yml` — `superset-init` (one-shot, after analytics-db is healthy) + `superset` (starts once init completes successfully, `apache/superset:4.1.2`) services, `superset-data` volume; `8088:8088` in the override.
- The api side was already done (step 7): `superset_service.py` login → guest_token flow, RLS `user_id` scoping.
- Verification: `docker compose config -q` valid, `bash -n init.sh` and `py_compile superset_config.py` clean. (Docker daemon was down — end-to-end `make up` verification pending on first startup.)

**Why:** the Superset service backing the guest tokens minted by the api was missing from the stack; with this step the infrastructure to serve embeddable, RLS-scoped dashboards is complete. Dashboard content (datasets/charts) is the next step.

### 9. Observability — metrics slice
**Commit:** `9472d0f` (PR #8 → merged to main as `677a521`)

RED metrics (rate/error/duration) derived from spans wired into Prometheus and a Grafana dashboard.
- `observability/otel-collector/config.yaml` — added the `spanmetrics` connector; the traces pipeline also exports to spanmetrics, and a new `metrics` pipeline (otlp + spanmetrics → `prometheus` exporter :8889).
- `observability/prometheus/prometheus.yml` — from TODO to a real config: `otel-collector:8889` + self-scrape, 15s interval.
- `observability/grafana/provisioning/datasources/datasources.yaml` — Prometheus datasource (`uid: prometheus`).
- `observability/grafana/provisioning/dashboards/dashboards.yaml` + `observability/grafana/dashboards/service-overview.json` — auto-provisioned "Service Overview" dashboard: request rate, error rate, and p95 latency per service (+ per endpoint).
- `docker-compose.yml` — `prometheus` service (`prom/prometheus:v3.2.1`) + `prometheus-data` volume; grafana now also depends_on prometheus.
- Verification: `docker compose config -q` valid, 4 YAML files + dashboard JSON linted. (Runtime validation of the collector config against the image wasn't possible with the Docker daemon down — verify on first `make up`.)

**Why:** the traces slice (step 8) shipped spans to Tempo but there were no metrics; with the spanmetrics connector every service gets RED metrics on a ready-made Grafana dashboard without installing a separate metrics SDK. This completes the observability step.

### 8. Observability — traces slice (end to end)
**Commit:** `984811b` (PR #7 → merged to main as `873b003`)

The api/ai-engine → OTel collector → Tempo → Grafana trace flow was set up.
- `observability/otel-collector/config.yaml` — OTLP receiver (gRPC 4317 / HTTP 4318) → `otlp/tempo` exporter to Tempo (+ debug).
- `observability/tempo/tempo.yaml` — single-binary Tempo, accepts OTLP gRPC, HTTP API on :3200.
- `observability/grafana/provisioning/datasources/datasources.yaml` — Tempo datasource (traces browsable via Explore); anonymous access enabled.
- `docker-compose.yml` — `otel-collector`, `tempo`, `grafana` services + `tempo-data`/`grafana-data` volumes; the `OTEL_EXPORTER_OTLP_ENDPOINT` default for ai-engine and api set to `http://otel-collector:4317`. Grafana `3000:3000` in the override.
- **Code**: `instrument_app()` in `core/tracing.py` of both services — FastAPI + asyncpg + httpx auto-instrumentation; called from `create_app` in `main.py`; `opentelemetry-instrumentation-{fastapi,asyncpg,httpx}` added to pyproject + Dockerfile.
- Verification: api 7 / ai-engine 2 tests passed, both services import cleanly, `docker compose config` valid, 3 YAML configs linted.

**Why:** every request's HTTP + DB + outbound-call spans and Claude call metrics should be collected in Tempo and visible in Grafana. The "lands in the observability step" note in the `tracing.py` files is now fulfilled. The metrics/dashboard slice followed as the next step.

### 7. api service — public-facing layer
**Commit:** `72c11e6` (PR #4 → merged to main as `6176a13`)

Following the same `core/` pattern as ai-engine, the `api/` stubs were turned into a real implementation.
- `core/`: structlog JSON logging, OTel tracing, request-context middleware, typed exception hierarchy (`ApiError`, `UserNotFoundError`, `AIEngineError`, `AIEngineRateLimitError`, `SupersetError`).
- **finance**: read-only endpoints over the `marts.*` schema (summary, cashflow, spending, net-worth, peer-comparison), layered repo → service → router.
- **chat**: proxied to ai-engine via `AIEngineClient` — the api **never** calls Claude directly (CLAUDE.md rule); 429→rate-limit, 5xx→ai_engine_error mapping.
- **superset**: login → guest_token flow, every token **RLS-scoped** by `user_id` (per-user security rule).
- main/config/dependencies wiring, Dockerfile, pyproject (OTel + pytest), docker-compose `api` service + `8001:8000` port, `.env.example` updated.
- Unit tests: finance shaping, RLS scoping, proxy error mapping — **7 passed**.

**Why:** the single user-facing entry point; reads data from marts, proxies chat inward, and mints secure tokens for Superset embeds.

### 6. ai-engine — AI engine implementation
**Commit:** `354245e` (2026-06-23)

TODO stubs turned into a real implementation: insight/anomaly/recommendation runners, `ClaudeService` (current `output_config.format` structured output + adaptive thinking API, model `claude-sonnet-4-6`), context/insight repositories, chat & insights routers, Jinja2 prompts, observability `core/` layer. Unit test (`test_insight_runner`) — 2 passed.

**Why:** the internal service that reads mart output, generates insights with Claude, and writes them back to `ai_layer`.

### 5. dbt pipeline + walkthrough
**Commit:** `fbbe3cd`, `effede9` (models) · `5fa294e` (2026-06-11, walkthrough doc)

staging → intermediate → marts (finance + ai_layer) models, macros, tests. End-to-end walkthrough (in Turkish) in `docs/dbt/pipeline-walkthrough.md`.

**Why:** the transformation layer that turns raw data into marts that BI and AI can read fast.

### 4. analytics-db + FDW + AI insights foundation
**Commit:** `5a24864`

`postgres_fdw` setup SQL and the foundation schema for AI insights.

### 3. CI workflow
**Commit:** `c82f6af`

GitHub Actions: dbt parse/build/test + pytest, with a Postgres service container.

### 2 & 1. Skeleton + mock-data + source-db
**Commit:** `a1a00c9` (and earlier)

Initial DB schema, static reference data, deterministic (Faker) mock-data generator.

---

> **Note:** This file is updated after every completed step. An uncommitted step is marked "not committed yet"; the hash is added once it is committed.
