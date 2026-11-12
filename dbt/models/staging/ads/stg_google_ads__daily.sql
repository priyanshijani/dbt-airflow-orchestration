{#
  Google Ads agency export: dates are MM/DD/YYYY text and cost is in micros (1,000,000 = 1 currency unit).
  The account bills in USD.
#}
with typed as (

    select
        toDate(parseDateTime(date, '%m/%d/%Y'))        as report_date,
        toUInt64OrNull(campaign_id)                    as campaign_id,
        campaign_name,
        advertising_channel_type                       as campaign_type,
        toUInt64OrNull(impressions)                    as impressions,
        toUInt64OrNull(clicks)                         as clicks,
        toFloat64OrNull(cost_micros) / 1000000         as spend_usd,
        toFloat64OrNull(conversions)                   as platform_purchases,
        toFloat64OrNull(conversions_value)             as platform_purchase_value_usd,
        _source_file
    from {{ source('google_ads', 'daily') }}
    order by _source_file desc
    limit 1 by report_date, campaign_id

)

{# Every column is aliased explicitly: ClickHouse names a joined column `t.x` when both sides have an `x`. #}
select
    concat(toString(t.report_date), '|', toString(t.campaign_id))   as ad_key,
    t.report_date as report_date,
    t.campaign_id as campaign_id,
    t.campaign_name as campaign_name,
    m.campaign_slug as campaign_slug,
    m.channel as channel,
    t.campaign_type as campaign_type,
    'USD'                                                            as currency,
    round(t.spend_usd, 2)                                            as spend_usd,
    t.impressions as impressions,
    t.clicks as clicks,
    t.platform_purchases as platform_purchases,
    t.platform_purchase_value_usd as platform_purchase_value_usd,
    t._source_file as _source_file
from typed as t
left join {{ ref('campaign_mapping') }} as m on m.platform = 'google' and m.campaign_name = t.campaign_name
