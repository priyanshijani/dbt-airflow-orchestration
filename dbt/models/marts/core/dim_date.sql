{{ config(engine='MergeTree()', order_by='date_day') }}
{# One row per day of the simulation window plus a year of runway for targets. #}
with days as (
    select toDate('2025-11-01') + number as date_day from numbers(0, 426)
)
select
    d.date_day as date_day,
    toStartOfWeek(d.date_day, 1) as week_start,
    toStartOfMonth(d.date_day) as month_start,
    toDayOfWeek(d.date_day) as day_of_week,
    toDayOfWeek(d.date_day) >= 6 as is_weekend,
    h.holiday_name != '' as is_us_holiday,
    h.holiday_name as holiday_name
from days as d
left join (
    select holiday_date, any(holiday_name) as holiday_name
    from {{ ref('stg_holidays__public_holidays') }}
    where country_code = 'US' and is_nationwide
    group by holiday_date
) as h on h.holiday_date = d.date_day
