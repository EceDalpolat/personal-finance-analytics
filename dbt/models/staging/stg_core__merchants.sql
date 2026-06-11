with source as (select * from {{ source('core', 'merchants') }})
select
    merchant_id,
    name as merchant_name,
    default_category_id
from source
