# Personal Finance Analytics

Kişisel finans verisini uçtan uca işleyen analitik + AI platformu.

## Mimari

```
Source DB
    ↓ FDW
Analytics DB ← dbt pipeline
    ↓
mart_ai_context
    ↓
ai-engine ──────────────── LLM API
    ↓                           ↑
ai_insights tablosu         chat endpoint (api/)
    ↓                           ↑
Superset dashboard ←────── kullanıcı sorusu
    ↓
Grafana (observability)
```

## Bileşenler

| Dizin | Görev |
|-------|-------|
| `mock-data/` | Sentetik finans verisi üreteci |
| `source-db/` | Kaynak Postgres şeması + statik seed |
| `analytics-db/` | Analitik Postgres + postgres_fdw |
| `dbt/` | dbt pipeline (staging → intermediate → marts → ai_layer) |
| `api/` | FastAPI — Superset guest token + chat proxy |
| `ai-engine/` | Bağımsız AI servisi (Claude) — insight/anomaly/recommendation + chat |
| `superset/` | Dashboard / BI |
| `observability/` | OTel Collector + Prometheus + Grafana |

## Çalıştırma

```bash
cp .env.example .env   # değerleri doldur
make up                # stack'i ayağa kaldır
make mock              # sentetik veri üret
make dbt-build         # dbt pipeline
```
