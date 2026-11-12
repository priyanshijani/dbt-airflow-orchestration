{{ config(engine='MergeTree()', order_by='report_date') }}
{# The headline numbers by day. Ratios are blended across channels: total revenue over total spend. #}
with totals as (
    select
        report_date,
        sum(orders) as total_orders,
        sum(new_customers) as total_new_customers,
        sum(net_revenue_usd) as total_revenue_usd,
        sum(sessions) as total_sessions,
        sum(spend_usd) as total_spend_usd
    from {{ ref('mart_channel_performance') }}
    group by report_date
)
select
    report_date,
    total_orders as orders,
    total_new_customers as new_customers,
    toDecimal64(total_revenue_usd, 2) as net_revenue_usd,
    total_sessions as sessions,
    toDecimal64(total_spend_usd, 2) as spend_usd,
    toDecimal64(if(total_orders > 0, toFloat64(total_revenue_usd) / total_orders, 0), 2) as aov_usd,
    if(total_spend_usd > 0, toFloat64(total_revenue_usd) / toFloat64(total_spend_usd), 0) as blended_roas,
    toDecimal64(if(total_new_customers > 0, toFloat64(total_spend_usd) / total_new_customers, 0), 2) as blended_cac_usd,
    toFloat64(if(total_sessions > 0, total_orders / total_sessions, 0)) as conversion_rate
from totals
