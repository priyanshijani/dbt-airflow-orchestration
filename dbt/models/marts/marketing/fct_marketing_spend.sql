{{ config(engine='MergeTree()', order_by='(report_date, channel, campaign_slug)') }}
{# Paid media from both platforms at campaign-day grain, all in USD. Platform-reported purchases are kept
   apart from our own attribution: they are the platform claim, not our measurement. #}
select assumeNotNull(report_date) as report_date, ifNull(channel, 'unmapped') as channel, 'meta' as platform, ifNull(campaign_slug, 'unmapped') as campaign_slug,
       sum(spend_usd) as spend_usd, sum(impressions) as impressions, sum(clicks) as clicks,
       sum(platform_purchases) as platform_purchases, sum(platform_purchase_value_usd) as platform_purchase_value_usd
from {{ ref('stg_meta_ads__daily') }}
group by report_date, channel, campaign_slug
union all
select assumeNotNull(report_date), ifNull(channel, 'unmapped'), 'google' as platform, ifNull(campaign_slug, 'unmapped'),
       sum(spend_usd), sum(impressions), sum(clicks), sum(platform_purchases), sum(platform_purchase_value_usd)
from {{ ref('stg_google_ads__daily') }}
group by report_date, channel, campaign_slug
