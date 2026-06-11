-- Expense spend per user / month / category group.
select
    user_id,
    txn_month,
    group_id,
    group_name,
    total_spend,
    txn_count
from {{ ref('int_finance__monthly_category_spend') }}
