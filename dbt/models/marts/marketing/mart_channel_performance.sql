{{ config(engine='MergeTree()', order_by='(report_date, channel)') }}
{# Channel by day: traffic, orders, revenue and spend side by side. ROAS and CAC are left to the reader
   (sum the parts, then divide) so they stay correct at any grain. #}
with sessions as (
    select session_date as report_date, channel, count() as sessions, countIf(purchased) as purchasing_sessions
    from {{ ref('fct_sessions') }} group by report_date, channel
),
orders as (
    select order_date as report_date, channel, count() as orders,
           sum(net_revenue_usd) as net_revenue_usd, countIf(is_first_order) as new_customers
    from {{ ref('fct_orders') }} group by report_date, channel
),
spend as (
    select report_date, channel, sum(spend_usd) as spend_usd, sum(clicks) as clicks
    from {{ ref('fct_marketing_spend') }} group by report_date, channel
)
select
    d.date_day as report_date,
    ch.channel as channel,
    ifNull(s.sessions, 0) as sessions,
    ifNull(o.orders, 0) as orders,
    ifNull(o.new_customers, 0) as new_customers,
    toDecimal64(ifNull(o.net_revenue_usd, 0), 2) as net_revenue_usd,
    toDecimal64(ifNull(sp.spend_usd, 0), 2) as spend_usd,
    ifNull(sp.clicks, 0) as clicks
from {{ ref('dim_date') }} as d
cross join {{ ref('dim_channel') }} as ch
left join sessions as s on s.report_date = d.date_day and s.channel = ch.channel
left join orders as o on o.report_date = d.date_day and o.channel = ch.channel
left join spend as sp on sp.report_date = d.date_day and sp.channel = ch.channel
where d.date_day between toDate('2025-11-02') and (select max(order_date) from {{ ref('fct_orders') }})
