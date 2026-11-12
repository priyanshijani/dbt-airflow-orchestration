{#
  Revenue rules in one place. An order counts as revenue once payment has cleared:
  paid, shipped and delivered. placed (unpaid), payment_failed and cancelled never count.
  Net revenue is order value excluding tax and shipping (subtotal - discount), less refunds.
#}
with refunds as (

    select order_id, sum(amount_usd) as refunded_usd
    from {{ ref('stg_shop__refunds') }}
    group by order_id

)

select
    o.order_id as order_id,
    o.customer_id as customer_id,
    o.order_date as order_date,
    o.ordered_at as ordered_at,
    o.order_status as order_status,
    o.order_status in ('paid', 'shipped', 'delivered')                    as counts_as_revenue,
    o.ga_user_pseudo_id as ga_user_pseudo_id,
    o.ga_session_id as ga_session_id,
    o.utm_source as utm_source,
    o.utm_medium as utm_medium,
    o.utm_campaign as utm_campaign,
    o.discount_code as discount_code,
    o.subtotal_usd as subtotal_usd,
    o.discount_usd as discount_usd,
    o.shipping_usd as shipping_usd,
    o.tax_usd as tax_usd,
    o.total_usd as total_usd,
    o.subtotal_usd - o.discount_usd                                       as gross_revenue_usd,
    ifNull(r.refunded_usd, 0)                                             as refunded_usd,
    if(counts_as_revenue, gross_revenue_usd - refunded_usd, 0)            as net_revenue_usd
from {{ ref('stg_shop__orders') }} as o
left join refunds as r on r.order_id = o.order_id
