{{ config(engine='MergeTree()', order_by='(week_start, channel)') }}
{# Why did revenue move week over week? Per channel, the change splits exactly into
     volume effect = (orders - prior orders) x prior AOV     (more or fewer orders)
     price effect  = the rest                                (bigger or smaller baskets)
   which add up to the change. Only complete Monday-to-Sunday weeks are included. #}
with weekly as (
    select
        toStartOfWeek(report_date, 1) as week_start,
        channel,
        sum(orders) as orders,
        sum(net_revenue_usd) as revenue_usd,
        uniqExact(report_date) as days
    from {{ ref('mart_channel_performance') }}
    group by week_start, channel
    having days = 7
),
paired as (
    select
        w.week_start as week_start,
        w.channel as channel,
        w.orders as orders,
        w.revenue_usd as revenue_usd,
        p.orders as prior_orders,
        p.revenue_usd as prior_revenue_usd
    from weekly as w
    inner join weekly as p on p.channel = w.channel and p.week_start = w.week_start - 7
)
select
    b.week_start as week_start,
    b.channel as channel,
    toDecimal64(b.revenue_usd, 2) as revenue_usd,
    toDecimal64(b.prior_revenue_usd, 2) as prior_revenue_usd,
    toDecimal64(b.revenue_usd - b.prior_revenue_usd, 2) as change_usd,
    toDecimal64(if(b.prior_orders > 0,
                   (toInt64(b.orders) - toInt64(b.prior_orders)) * (toFloat64(b.prior_revenue_usd) / b.prior_orders),
                   toFloat64(b.revenue_usd)), 2) as volume_effect_usd,
    change_usd - volume_effect_usd as price_effect_usd
from paired as b
