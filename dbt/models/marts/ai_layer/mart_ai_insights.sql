-- View over the app-owned ai.insights table (written by the ai-engine). A view,
-- not a table, so it always reflects the latest insights without a dbt run.
{{ config(materialized='view') }}
select
    insight_id,
    user_id,
    insight_type,
    period_month,
    title,
    body,
    model,
    created_at
from {{ source('ai', 'insights') }}
