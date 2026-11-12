select
    toDate(date)         as holiday_date,
    country_code,
    name                 as holiday_name,
    local_name,
    fixed                as is_fixed_date,
    `global`             as is_nationwide
from {{ source('holidays', 'public_holidays') }}
