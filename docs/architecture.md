# Architecture

System design, data flow, and per-service responsibilities.

## Data flow

```
source-db  --postgres_fdw-->  analytics-db  --dbt-->  marts/ai_layer
   (raw)                          (warehouse)            mart_ai_context
                                                              |
                                                              v
                                                         ai-engine --> ai_insights
                                                              |
                                                              v
                                                          Superset --> user
```

## Service responsibilities

| Service | Owns | Talks to |
|---------|------|----------|
| `mock-data` | Deterministic synthetic data generation | source-db |
| `source-db` | Raw operational tables | — |
| `analytics-db` | Warehouse + FDW foreign schemas | source-db (FDW) |
| `dbt` | staging → intermediate → marts transformation | analytics-db |
| `ai-engine` | Claude calls, insight/anomaly/recommendation runners, chat | analytics-db, Claude API |
| `api` | Superset guest token, chat proxy | ai-engine, Superset |
| `superset` | Dashboards, SQL Lab, chat widget | analytics-db, api |
| `observability` | Traces, metrics, dashboards | all services |

> Record decisions here with their "why" so future sessions build on what was worked out.
