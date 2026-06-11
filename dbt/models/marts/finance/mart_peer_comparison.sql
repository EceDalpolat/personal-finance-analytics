-- Each user's monthly spend vs the average of their income-band peers.
with cashflow as (
    select user_id, txn_month, total_spend from {{ ref('int_finance__monthly_cashflow') }}
),
users as (
    select user_id, income_band from {{ ref('stg_core__users') }}
),
joined as (
    select cf.user_id, cf.txn_month, cf.total_spend, u.income_band
    from cashflow cf
    join users u using (user_id)
),
peer as (
    select income_band, txn_month, avg(total_spend) as peer_avg_spend
    from joined
    group by 1, 2
)
select
    j.user_id,
    j.income_band,
    j.txn_month,
    j.total_spend,
    round(p.peer_avg_spend, 2)                              as peer_avg_spend,
    round(j.total_spend - p.peer_avg_spend, 2)             as spend_vs_peer,
    round(j.total_spend / nullif(p.peer_avg_spend, 0) * 100, 1) as pct_of_peer
from joined j
join peer p on p.income_band = j.income_band and p.txn_month = j.txn_month
