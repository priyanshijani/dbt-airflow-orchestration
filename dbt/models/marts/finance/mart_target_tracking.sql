{{ config(engine='MergeTree()', order_by='(month_start, channel)') }}
{# The finance plan against what happened, per month and channel. Months still in progress are flagged. #}
with plan as (
    select ifNull(channel, 'unmapped') as channel, assumeNotNull(month_start) as month_start,
           sumIf(amount_usd, metric = 'revenue_target_usd') as revenue_target_usd,
           sumIf(amount_usd, metric = 'budget_usd') as budget_usd
    from {{ ref('stg_budget__monthly') }}
    group by channel, month_start
),
actual as (
    select toStartOfMonth(report_date) as month_start, channel,
           sum(net_revenue_usd) as revenue_usd, sum(spend_usd) as spend_usd, max(report_date) as last_day
    from {{ ref('mart_channel_performance') }}
    group by month_start, channel
)
select
    p.month_start as month_start,
    p.channel as channel,
    p.revenue_target_usd as revenue_target_usd,
    ifNull(a.revenue_usd, 0) as revenue_usd,
    p.budget_usd as budget_usd,
    ifNull(a.spend_usd, 0) as spend_usd,
    if(p.revenue_target_usd > 0, ifNull(a.revenue_usd, 0) / p.revenue_target_usd, 0) as revenue_attainment,
    ifNull(a.last_day, toDate('1970-01-01')) < toLastDayOfMonth(p.month_start) as is_month_in_progress
from plan as p
left join actual as a on a.month_start = p.month_start and a.channel = p.channel
