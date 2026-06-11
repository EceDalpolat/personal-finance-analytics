-- Income vs spend per user / month.
select
    user_id,
    txn_month,
    sum(case when direction = 'credit' and category_kind = 'income'
             then amount else 0 end)                                as total_income,
    sum(case when direction = 'debit'  and category_kind = 'expense'
             then amount else 0 end)                                as total_spend,
    sum(case when direction = 'credit' and category_kind = 'income'
             then amount else 0 end)
      - sum(case when direction = 'debit' and category_kind = 'expense'
                 then amount else 0 end)                            as net_cashflow
from {{ ref('int_finance__transactions_enriched') }}
group by 1, 2
