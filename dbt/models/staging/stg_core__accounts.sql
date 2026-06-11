with source as (select * from {{ source('core', 'accounts') }})
select
    account_id,
    user_id,
    account_type,
    institution,
    currency,
    opened_at,
    is_active
from source
