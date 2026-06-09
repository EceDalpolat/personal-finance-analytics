# CLAUDE.md

You are working on **personal-finance-analytics**: a multi-user personal finance
analytics platform with a dbt pipeline, AI-powered insights, and a Superset
dashboard. Users can track spending, budgets, investments, and chat with an AI
that interprets their financial data in natural language.

Read the relevant `docs/` pages before starting any task. You are not a generic
assistant — you know this project's architecture, conventions, and decisions.

---

## What This Project Does

Synthetic data for ~100 users flows through a multi-source Postgres setup into a
dbt pipeline (staging → intermediate → marts). An AI engine reads mart output,
produces insights, and stores them back to the DB. Superset visualises everything.
Users can ask natural language questions via a chat widget backed by Claude.

```
source-db (raw transactions, accounts, budgets, investments)
    ↓  postgres_fdw
analytics-db  ←  dbt pipeline (staging → intermediate → marts/ai_layer)
                      ↓
              ai-engine (insight_runner, anomaly_runner, chat)
                      ↓
              Superset (dashboards + chat widget)
                      ↓
              Grafana (observability — OTel + Prometheus + Tempo)
```

---

## Repository Layout

```
personal-finance-analytics/
├── mock-data/          # synthetic data generator (Faker, deterministic seed)
├── source-db/          # PG init SQL — raw schema
├── analytics-db/       # PG init SQL — FDW setup
├── dbt/                # dbt Core project
│   └── models/
│       ├── sources/
│       ├── staging/
│       ├── intermediate/
│       └── marts/
│           ├── finance/
│           └── ai_layer/   ← AI reads and writes here
├── api/                # FastAPI — public-facing (guest token, chat proxy)
│   └── src/
│       ├── routers/
│       ├── services/
│       ├── repositories/
│       ├── schemas/
│       └── core/       # logging, tracing, middleware, exceptions
├── ai-engine/          # FastAPI — internal AI service (Claude, insight runners)
│   └── src/
│       ├── runners/
│       ├── routers/
│       ├── services/
│       ├── repositories/
│       ├── prompts/    # Jinja2 templates — never hardcode prompts in Python
│       ├── schemas/
│       └── core/
├── superset/
├── observability/      # OTel collector, Prometheus, Tempo, Grafana
├── docker-compose.yml
├── Makefile
└── .env.example
```

**Dependency direction — never violate this:**

```
api / ai-engine routers  →  services  →  repositories  →  core
dbt models: marts  →  intermediate  →  staging  →  sources
```

Routers are thin. Logic lives in `services/`. DB access lives in `repositories/`.
`core/` has no knowledge of business logic.

---

## Stack

| Layer | Technology |
|-------|-----------|
| Data pipeline | dbt Core 1.11, Postgres 16, postgres_fdw |
| APIs | FastAPI, Uvicorn, pydantic-settings |
| AI | Anthropic Claude API (claude-sonnet-4-6) |
| BI | Apache Superset |
| Observability | OpenTelemetry, Prometheus, Tempo, Grafana, structlog |
| Infra | Docker Compose, GitHub Actions |
| Package manager | uv |
| Python | 3.13+ |

---

## Code Philosophy 🎯

These are not preferences. They are the rules this codebase is built on.

### Less is more

Write the minimum code that solves the problem correctly.
Every line added is a line that must be read, tested, and maintained.
If you can delete something without breaking behaviour — delete it.

### Explicit over implicit

Name things by what they do, not how they are implemented.
`get_user_monthly_spending()` not `fetch_data()`.
`ClaudeRateLimitError` not `APIError`.
A reader should understand intent without reading the body.

### One responsibility per unit

A function does one thing. A module owns one concept.
A router handles HTTP. A service handles business logic. A repository handles data.
If a function needs a comment to explain what it does — rename or split it.

### No magic, no surprise

Avoid clever code. Avoid hidden side effects.
If a function raises, document it. If it mutates state, name it clearly.
Predictable code is trustworthy code.

### Fail loudly and early

Use custom exceptions with semantic meaning (see `core/exceptions.py`).
Never swallow errors silently. Never return `None` to signal failure.
Validate at the boundary — pydantic schemas at API entry, SQL constraints at DB level.

### Async by default

All API and service code is `async`. Use `asyncpg` / async SQLAlchemy.
Never block the event loop with synchronous I/O.

---

## Naming Conventions

| Context | Convention | Example |
|---------|-----------|---------|
| dbt staging models | `stg_{source}__{entity}` | `stg_core__transactions` |
| dbt intermediate models | `int_{domain}__{description}` | `int_finance__monthly_summary` |
| dbt mart models | `fct_*`, `dim_*`, `mart_*` | `fct_monthly_spending` |
| Python files | `snake_case` | `insight_runner.py` |
| Python classes | `PascalCase` | `ClaudeService` |
| Python functions | `snake_case`, verb-first | `build_context()`, `run_insight()` |
| Pydantic schemas | `PascalCase` + suffix | `ChatRequest`, `InsightResponse` |
| Environment variables | `SCREAMING_SNAKE_CASE` | `CLAUDE_API_KEY` |
| Docker services | `kebab-case` | `ai-engine`, `source-db` |

---

## Observability Rules

Every service has the same `core/` layer:

- **`logging.py`** — structlog, JSON output, `request_id` + `trace_id` auto-injected
- **`tracing.py`** — OpenTelemetry SDK, FastAPI + SQLAlchemy + httpx auto-instrumented
- **`middleware.py`** — request ID generation, response timing, global error handler
- **`exceptions.py`** — typed exception hierarchy, never a bare `Exception`

All Claude API calls are traced. Duration, token count, and model are recorded as
OTel span attributes. Grafana dashboards monitor this.

Never add `print()`. Use `structlog.get_logger()`.

---

## dbt Conventions

- `staging` → `view` materialization (cheap, 1:1 with source)
- `intermediate` → `ephemeral` (CTE, no physical table)
- `marts` → `table` (BI reads fast)
- Every source table has `not_null`, `unique`, and `relationships` tests
- Seeds live in `seeds/` — versioned reference data (category hierarchy, peer segments)
- Macros handle reusable SQL logic (`spending_score`, `budget_variance`)
- Snapshots track SCD2 changes (e.g. user net worth over time)
- Exposures document which Superset dashboards consume which marts
- `dbt docs generate` must always pass cleanly

---

## AI Engine Rules

- `api/` **never** calls Claude directly — always proxies to `ai-engine/`
- All prompts live in `ai-engine/src/prompts/*.j2` — never hardcoded in Python
- `context_builder.py` is responsible for converting mart data into prompt context
- Insight runners are triggered after `dbt build` completes (via Makefile or dbt `on-run-end` hook)
- Scheduled runners (anomaly, recommendation) run on a timer inside the container
- Claude model: always `claude-sonnet-4-6` — do not change without discussion
- Token limits and retry logic are handled inside `claude_service.py` only

---

## Security & Data Rules

- All user-facing queries go through RLS (`marts/security/access_map_*`)
- No real financial data anywhere — all data is synthetic and deterministic
- Secrets come from environment variables only — never hardcoded, never in `docker-compose.yml`
- `.env.example` must be updated when a new env var is added
- Guest tokens (Superset) are scoped per user — `superset_service.py` enforces this

---

## Commands

```bash
make up           # docker compose up — full stack
make generate     # run mock-data/generate.py
make dbt-build    # dbt seed + run + test
make dbt-docs     # dbt docs generate + serve
make logs         # open Grafana at localhost:3000
make test         # pytest (api + ai-engine)
```

---

## CI (GitHub Actions)

Every push runs:
1. `dbt deps && dbt parse` — syntax check
2. `dbt build && dbt test` — full pipeline with Postgres service container
3. `pytest` — unit + integration tests for api and ai-engine

CI must stay green. Never remove or weaken tests to fix a failing pipeline.

---

## Boundaries

Ask before:
- Adding a new dependency
- Changing a public API contract (request/response schema)
- Adding a new top-level service or database
- Changing dbt materialization strategy on existing models

Never:
- Commit secrets or real financial data
- Call Claude from a router directly
- Hardcode prompts in Python files
- Use `print()` instead of structured logging
- Edit `uv.lock` manually
- Write synchronous DB or HTTP calls in async functions

---

## Conventional Commits

```
feat(dbt): add mart_peer_comparison model
feat(ai-engine): add anomaly_runner with Claude prompt
feat(api): expose /chat endpoint with streaming
fix(dbt): correct budget_variance macro edge case
test(ai-engine): mock Claude in insight_runner unit tests
docs(architecture): update AI layer data flow diagram
chore(deps): add dbt-expectations to packages.yml
```

---

## Docs

Keep knowledge cumulative under `docs/` — write decisions with their "why" so
future sessions build on what was already worked out.

- `docs/architecture.md` — system design, data flow, service responsibilities
- `docs/dbt/` — model conventions, layer philosophy, macro catalogue
- `docs/ai-engine/` — prompt design, runner logic, context building strategy
- `docs/observability/` — OTel setup, Grafana dashboard guide
- `docs/api/` — endpoint contracts, auth, guest token flow
```
