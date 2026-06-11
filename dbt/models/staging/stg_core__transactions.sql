with source as (select * from {{ source('core', 'transactions') }})
select
    transaction_id,
    account_id,
    category_id,
    merchant_id,
    txn_ts,
    cast(txn_ts as date)                 as txn_date,
    date_trunc('month', txn_ts)::date    as txn_month,
    direction,
    amount,
    currency,
    description
from source
