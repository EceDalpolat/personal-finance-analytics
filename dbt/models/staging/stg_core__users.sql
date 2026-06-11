with source as (select * from {{ source('core', 'users') }})
select
    user_id,
    full_name,
    email,
    country,
    age_band,
    income_band,
    employment_status,
    signup_date,
    created_at
from source
