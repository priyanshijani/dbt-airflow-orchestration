{{ config(engine='MergeTree()', order_by='(session_date, channel, session_key)', partition_by='toYYYYMM(session_date)') }}
select
    s.session_key as session_key,
    s.session_date as session_date,
    if(m.channel != '', m.channel, 'organic_direct_referral') as channel,
    s.device_category as device_category,
    s.country as country,
    s.viewed_item as viewed_item,
    s.added_to_cart as added_to_cart,
    s.began_checkout as began_checkout,
    s.purchased as purchased
from {{ ref('int_ga4__sessions') }} as s
left join {{ ref('ga4_channel_mapping') }} as m on m.source = s.first_touch_source and m.medium = s.first_touch_medium
