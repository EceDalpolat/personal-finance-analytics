-- Net worth per user / month = sum of month-end account balances
-- (credit-card balances are negative, so they reduce net worth).
with balances as (
    select * from {{ ref('stg_core__account_balances') }}
),
accounts as (
    select account_id, user_id from {{ ref('stg_core__accounts') }}
)
select
    a.user_id,
    b.balance_month,
    sum(b.balance) as net_worth
from balances b
join accounts a on a.account_id = b.account_id
group by 1, 2
