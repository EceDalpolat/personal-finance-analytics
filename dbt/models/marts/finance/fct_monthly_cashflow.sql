-- Income, spend, and net cashflow per user / month.
select
    user_id,
    txn_month,
    total_income,
    total_spend,
    net_cashflow
from {{ ref('int_finance__monthly_cashflow') }}
