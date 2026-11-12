{{ config(engine='AggregatingMergeTree()', order_by='(report_date, channel)') }}
{# Rollup that stays small as history grows: partial aggregate states, merged at read time with sumMerge().
   Query: select toStartOfWeek(report_date) w, sumMerge(net_revenue_state) from this table group by w #}
select
    report_date,
    channel,
    sumState(net_revenue_usd) as net_revenue_state,
    sumState(spend_usd) as spend_state,
    sumState(orders) as orders_state,
    sumState(sessions) as sessions_state
from {{ ref('mart_channel_performance') }}
group by report_date, channel
