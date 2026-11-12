{#
  Finance's plan, one row per channel x month x metric. Finance uses its own channel labels (mapped via a seed)
  and revises the workbook during the year: the newest file wins per cell (v2 replaces v1).
#}
with latest as (

    select channel_label, month_label, metric, value, _source_file
    from {{ source('budget', 'monthly') }}
    order by _source_file desc
    limit 1 by channel_label, month_label, metric

)

select
    m.channel,
    l.channel_label                                                   as finance_channel_label,
    toDate(parseDateTimeBestEffort(concat('1 ', l.month_label)))      as month_start,
    l.metric,
    toFloat64(l.value)                                                as amount_usd,
    l._source_file                                                    as plan_file
from latest as l
left join {{ ref('budget_channel_mapping') }} as m on l.channel_label = m.finance_label
