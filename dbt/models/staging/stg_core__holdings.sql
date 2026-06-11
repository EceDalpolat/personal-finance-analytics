with source as (select * from {{ source('core', 'holdings') }})
select
    holding_id,
    account_id,
    symbol,
    asset_class,
    quantity,
    cost_basis,
    market_value,
    as_of_date
from source
