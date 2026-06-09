# dbt — conventions, layer philosophy, macro catalogue

## Layers
- `staging/` → `view`, 1:1 with source, rename + cast only (`stg_{source}__{entity}`)
- `intermediate/` → `ephemeral`, business logic / joins (`int_{domain}__{description}`)
- `marts/finance/` → `table`, dashboard-facing (`fct_*`, `dim_*`, `mart_*`)
- `marts/ai_layer/` → `mart_ai_context` (AI reads), `mart_ai_insights` (AI writes, view)

## Macro catalogue
- _TODO_ — `spending_score`, `budget_variance`, RLS macros

## Tests
- Every source table: `not_null`, `unique`, `relationships`
