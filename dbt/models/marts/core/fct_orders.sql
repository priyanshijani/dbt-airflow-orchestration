{{ config(engine='MergeTree()', order_by='(order_date, channel, order_id)', partition_by='toYYYYMM(order_date)') }}
{# One row per order that counts as revenue, with its channel, refund-adjusted revenue and item margin. #}
with items as (
    select
        i.order_id as order_id,
        sum(i.quantity) as units,
        sum(i.line_net_usd - i.quantity * p.cost_usd) as gross_margin_usd
    from {{ ref('stg_shop__order_items') }} as i
    left join {{ ref('stg_shop__products') }} as p on p.product_id = i.product_id
    group by i.order_id
)
select
    toUInt64(a.order_id) as order_id,
    a.order_date as order_date,
    toUInt64(a.customer_id) as customer_id,
    a.channel as channel,
    a.attribution_basis as attribution_basis,
    a.utm_campaign as utm_campaign,
    r.discount_code as discount_code,
    toDecimal64(r.gross_revenue_usd, 2) as gross_revenue_usd,
    toDecimal64(r.refunded_usd, 2) as refunded_usd,
    toDecimal64(a.net_revenue_usd, 2) as net_revenue_usd,
    toUInt64(ifNull(it.units, 0)) as units,
    toDecimal64(ifNull(it.gross_margin_usd, 0), 2) as gross_margin_usd,
    toBool(c.first_order_date = a.order_date) as is_first_order
from {{ ref('int_orders__attributed') }} as a
inner join {{ ref('int_orders__revenue') }} as r on r.order_id = a.order_id
left join items as it on it.order_id = a.order_id
left join {{ ref('dim_customers') }} as c on c.customer_id = toUInt64(a.customer_id)
where a.counts_as_revenue
