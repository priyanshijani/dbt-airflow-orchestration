{#
  One row per GA4 session with its funnel steps and acquisition channel. GA4's session-level source and medium are
  empty in this export, so the channel comes from the user's first-touch source/medium (mapped by seed).
#}
select
    e.session_key as session_key,
    any(e.user_pseudo_id) as user_pseudo_id,
    any(e.ga_session_id) as ga_session_id,
    min(e.event_date) as session_date,
    min(e.event_at) as session_start_at,
    any(e.first_touch_source) as first_touch_source,
    any(e.first_touch_medium) as first_touch_medium,
    any(e.device_category) as device_category,
    any(e.country) as country,
    countIf(e.event_name = 'view_item') > 0                  as viewed_item,
    countIf(e.event_name = 'add_to_cart') > 0                as added_to_cart,
    countIf(e.event_name = 'begin_checkout') > 0             as began_checkout,
    countIf(e.event_name = 'purchase') > 0                   as purchased,
    sum(ifNull(e.purchase_revenue_usd, 0))                   as ga4_revenue_usd
from {{ ref('stg_ga4__events') }} as e
group by e.session_key
