with source as (select * from {{ source('core', 'account_balances') }})
select
    account_id,
    as_of_date,
    date_trunc('month', as_of_date)::date as balance_month,
    balance
from source
