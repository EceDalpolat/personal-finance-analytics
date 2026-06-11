-- Expense spend per user / month / category group. Grain matches budgets,
-- which are set at the group level.
select
    user_id,
    txn_month,
    group_id,
    group_name,
    sum(amount)  as total_spend,
    count(*)     as txn_count
from {{ ref('int_finance__transactions_enriched') }}
where direction = 'debit' and category_kind = 'expense'
group by 1, 2, 3, 4
