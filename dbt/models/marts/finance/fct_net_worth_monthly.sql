-- Net worth per user / month.
select
    user_id,
    balance_month,
    net_worth
from {{ ref('int_finance__net_worth_monthly') }}
