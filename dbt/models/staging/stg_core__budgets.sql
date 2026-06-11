with source as (select * from {{ source('core', 'budgets') }})
select
    budget_id,
    user_id,
    category_id,
    period_month,
    limit_amount,
    currency
from source
