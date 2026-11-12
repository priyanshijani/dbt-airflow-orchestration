{# FRED marks missing observations with "." in the value field; that becomes NULL. #}
select
    series_id,
    series_name,
    toDate(date)               as observation_date,
    toFloat64OrNull(value)     as value
from {{ source('fred', 'observations') }}
