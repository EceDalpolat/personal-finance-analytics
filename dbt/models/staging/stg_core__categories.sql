with source as (select * from {{ source('core', 'categories') }})
select
    category_id,
    name as category_name,
    parent_category_id,
    kind
from source
