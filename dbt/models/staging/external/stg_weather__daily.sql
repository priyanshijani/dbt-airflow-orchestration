select
    toDate(date)                    as weather_date,
    city,
    country                         as country_code,
    temp_max_c,
    temp_min_c,
    (temp_max_c + temp_min_c) / 2   as temp_mean_c,
    precipitation_mm
from {{ source('weather', 'daily') }}
