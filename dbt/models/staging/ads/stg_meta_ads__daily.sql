{#
  Meta Ads daily export. Raw columns are text, in the ad account's own currency, and a day can be exported twice
  (the Monday re-export after attribution matures). Staging types the columns, converts money to USD, maps the
  campaign to our slug and channel, and keeps the newest delivery of each day/campaign/ad set.
#}
with typed as (

    select
        toDate(reporting_starts)                       as report_date,
        account_name,
        campaign_name,
        ad_set_name,
        upper(currency)                                as currency,
        toFloat64OrNull(amount_spent)                  as spend_local,
        toUInt64OrNull(impressions)                    as impressions,
        toUInt64OrNull(reach)                          as reach,
        toUInt64OrNull(link_clicks)                    as clicks,
        toFloat64OrNull(purchases)                     as platform_purchases,
        toFloat64OrNull(purchases_conversion_value)    as platform_purchase_value_local,
        _source_file
    from {{ source('meta_ads', 'daily') }}
    -- file names sort re-exports after originals, so "newest file" = most mature numbers
    order by _source_file desc
    limit 1 by report_date, campaign_name, ad_set_name

)

{# Every column is aliased explicitly: ClickHouse names a joined column `t.x` when both sides have an `x`. #}
select
    concat(toString(t.report_date), '|', t.campaign_name, '|', t.ad_set_name)  as ad_key,
    t.report_date as report_date,
    t.account_name as account_name,
    t.campaign_name as campaign_name,
    m.campaign_slug as campaign_slug,
    m.channel as channel,
    t.ad_set_name as ad_set_name,
    t.currency as currency,
    round(t.spend_local / fx.units_per_usd, 2)                                  as spend_usd,
    t.impressions as impressions,
    t.reach as reach,
    t.clicks as clicks,
    t.platform_purchases as platform_purchases,
    round(t.platform_purchase_value_local / fx.units_per_usd, 2)                as platform_purchase_value_usd,
    t._source_file as _source_file
from typed as t
left join {{ ref('fx_rates') }} as fx on t.currency = fx.currency
left join {{ ref('campaign_mapping') }} as m on m.platform = 'meta' and m.campaign_name = t.campaign_name
