-- Category dimension flattened to leaf + its rolled-up group.
with categories as (
    select * from {{ ref('stg_core__categories') }}
)
select
    c.category_id,
    c.category_name,
    c.kind,
    coalesce(c.parent_category_id, c.category_id) as group_id,
    g.category_name                               as group_name,
    (c.parent_category_id is null)                as is_group
from categories c
left join categories g
    on g.category_id = coalesce(c.parent_category_id, c.category_id)
