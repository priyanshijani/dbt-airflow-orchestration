{#
  Last-click attribution of each order to one channel. Order of evidence:
    1. the order's own UTM (what the shop captured at checkout)
    2. the GA4 session's first-touch source/medium
    3. otherwise organic_direct_referral
  utm medium 'paid_social' and 'email' map straight to those channels; google/cpc to paid_search.
#}
select
    r.order_id as order_id,
    r.order_date as order_date,
    r.customer_id as customer_id,
    r.counts_as_revenue as counts_as_revenue,
    r.net_revenue_usd as net_revenue_usd,
    r.utm_campaign as utm_campaign,
    multiIf(
        r.utm_medium = 'paid_social', 'paid_social',
        r.utm_medium = 'email', 'email',
        r.utm_medium = 'cpc', 'paid_search',
        m.channel != '', m.channel,
        'organic_direct_referral'
    )                                                         as channel,
    multiIf(
        r.utm_medium != '', 'order_utm',
        m.channel != '', 'ga4_first_touch',
        'default'
    )                                                         as attribution_basis
from {{ ref('int_orders__revenue') }} as r
left join {{ ref('int_ga4__sessions') }} as s on s.ga_session_id = r.ga_session_id and s.user_pseudo_id = r.ga_user_pseudo_id
left join {{ ref('ga4_channel_mapping') }} as m on m.source = s.first_touch_source and m.medium = s.first_touch_medium
