-- One row per user: a compact, model-ready summary of their latest financial
-- state. The ai-engine's context_builder renders this into a prompt — so this
-- model is the single contract between the dbt pipeline and the AI layer.
with months as (
    select max(txn_month) as latest_month from {{ ref('fct_monthly_cashflow') }}
),

cashflow_last as (
    select cf.user_id, cf.total_income, cf.total_spend, cf.net_cashflow
    from {{ ref('fct_monthly_cashflow') }} cf
    join months m on cf.txn_month = m.latest_month
),

top_cat as (
    select distinct on (s.user_id) s.user_id, s.group_name, s.total_spend
    from {{ ref('fct_monthly_spending') }} s
    join months m on s.txn_month = m.latest_month
    order by s.user_id, s.total_spend desc
),

budget_last as (
    select
        bv.user_id,
        count(*) filter (where bv.over_budget)                            as over_budget_count,
        json_agg(dc.group_name) filter (where bv.over_budget)            as over_budget_categories
    from {{ ref('fct_budget_variance') }} bv
    join months m on bv.period_month = m.latest_month
    left join {{ ref('dim_category') }} dc on dc.category_id = bv.group_id
    group by bv.user_id
),

nw_ranked as (
    select
        user_id, net_worth,
        row_number() over (partition by user_id order by balance_month desc) as rn
    from {{ ref('fct_net_worth_monthly') }}
),
nw_latest as (select user_id, net_worth from nw_ranked where rn = 1),
nw_6m     as (select user_id, net_worth from nw_ranked where rn = 6),

peer_last as (
    select pc.user_id, pc.peer_avg_spend, pc.pct_of_peer
    from {{ ref('mart_peer_comparison') }} pc
    join months m on pc.txn_month = m.latest_month
),

spend_series as (
    select user_id,
           json_agg(json_build_object('month', txn_month, 'spend', total_spend)
                    order by txn_month) as monthly_spend_6m
    from (
        select user_id, txn_month, total_spend,
               row_number() over (partition by user_id order by txn_month desc) as rn
        from {{ ref('fct_monthly_cashflow') }}
    ) x
    where rn <= 6
    group by user_id
),

cat_breakdown as (
    select s.user_id,
           json_agg(json_build_object('category', s.group_name, 'spend', s.total_spend)
                    order by s.total_spend desc) as category_breakdown
    from {{ ref('fct_monthly_spending') }} s
    join months m on s.txn_month = m.latest_month
    group by s.user_id
)

select
    u.user_id,
    u.income_band,
    m.latest_month,
    cl.total_income                              as last_month_income,
    cl.total_spend                               as last_month_spend,
    cl.net_cashflow                              as last_month_net,
    tc.group_name                                as top_category,
    tc.total_spend                               as top_category_spend,
    coalesce(bl.over_budget_count, 0)            as over_budget_count,
    bl.over_budget_categories,
    nl.net_worth                                 as net_worth_latest,
    n6.net_worth                                 as net_worth_6m_ago,
    round(nl.net_worth - n6.net_worth, 2)        as net_worth_6m_change,
    pl.peer_avg_spend,
    pl.pct_of_peer,
    ss.monthly_spend_6m,
    cb.category_breakdown
from {{ ref('dim_user') }} u
cross join months m
left join cashflow_last cl on cl.user_id = u.user_id
left join top_cat       tc on tc.user_id = u.user_id
left join budget_last   bl on bl.user_id = u.user_id
left join nw_latest     nl on nl.user_id = u.user_id
left join nw_6m         n6 on n6.user_id = u.user_id
left join peer_last     pl on pl.user_id = u.user_id
left join spend_series  ss on ss.user_id = u.user_id
left join cat_breakdown cb on cb.user_id = u.user_id
