-- One enriched row per transaction: attaches the owning user, the leaf category
-- (with its kind), and the rolled-up category group. The workhorse the spend /
-- cashflow models build on.
with txns as (
    select * from {{ ref('stg_core__transactions') }}
),
accounts as (
    select account_id, user_id from {{ ref('stg_core__accounts') }}
),
categories as (
    select category_id, category_name, parent_category_id, kind
    from {{ ref('stg_core__categories') }}
)
select
    t.transaction_id,
    a.user_id,
    t.account_id,
    t.merchant_id,
    t.txn_ts,
    t.txn_date,
    t.txn_month,
    t.direction,
    t.amount,
    t.category_id,
    c.category_name,
    c.kind                                            as category_kind,
    coalesce(c.parent_category_id, c.category_id)     as group_id,
    g.category_name                                   as group_name
from txns t
join accounts a   on a.account_id = t.account_id
join categories c on c.category_id = t.category_id
left join categories g
    on g.category_id = coalesce(c.parent_category_id, c.category_id)
