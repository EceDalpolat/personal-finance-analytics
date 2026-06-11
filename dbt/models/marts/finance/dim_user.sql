select
    user_id,
    full_name,
    email,
    country,
    age_band,
    income_band,
    employment_status,
    signup_date
from {{ ref('stg_core__users') }}
