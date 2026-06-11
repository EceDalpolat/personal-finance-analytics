-- One row per budget: planned limit vs actual spend for that user/group/month.
with budgets as (
    select * from {{ ref('stg_core__budgets') }}
),
spend as (
    select * from {{ ref('int_finance__monthly_category_spend') }}
)
select
    b.budget_id,
    b.user_id,
    b.category_id                                          as group_id,
    b.period_month,
    b.limit_amount,
    coalesce(s.total_spend, 0)                             as actual_spend,
    round(coalesce(s.total_spend, 0) - b.limit_amount, 2)  as variance,
    round(coalesce(s.total_spend, 0)
          / nullif(b.limit_amount, 0) * 100, 1)            as pct_of_limit,
    {{ budget_status('coalesce(s.total_spend, 0)', 'b.limit_amount') }} as status,
    (coalesce(s.total_spend, 0) > b.limit_amount)          as over_budget
from budgets b
left join spend s
    on  s.user_id   = b.user_id
    and s.group_id  = b.category_id
    and s.txn_month = b.period_month
