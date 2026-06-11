# dbt — conventions, layer philosophy, macro catalogue

> 📖 **Tam anlatım:** Her dosya ve SQL bloğunun ne/neden/nasıl açıklaması için
> [pipeline-walkthrough.md](pipeline-walkthrough.md) — sıfırdan yazabilecek
> seviyede rehber.

## Layers
- `staging/` → `view`, 1:1 with source, rename + cast only (`stg_{source}__{entity}`)
- `intermediate/` → `ephemeral`, business logic / joins (`int_{domain}__{description}`)
- `marts/finance/` → `table`, dashboard-facing (`fct_*`, `dim_*`, `mart_*`)
- `marts/ai_layer/` → `mart_ai_context` (AI reads), `mart_ai_insights` (AI writes, view)

## Macro catalogue
- `budget_status(actual, limit)` — 'over' / 'near' (>=90%) / 'under' etiketi
- `generate_schema_name` — override: özel şema adını birebir kullan (staging/marts/ai_layer)

## Tests
- Every source table: `not_null`, `unique`, `relationships`
