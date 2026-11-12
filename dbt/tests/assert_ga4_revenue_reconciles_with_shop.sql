{#
  GA4 and the shop should agree on revenue. GA4 purchase revenue excludes tax and shipping, so it is compared with the shop's
  subtotal less discount (gross_revenue_usd). Observed gap is ~2%; this fails above 5%.
#}
with ga4 as (
    select sum(ga4_revenue_usd) as ga4_usd from {{ ref('int_ga4__sessions') }}
),
shop as (
    select sum(gross_revenue_usd) as shop_usd from {{ ref('int_orders__revenue') }} where counts_as_revenue
)
select ga4_usd, shop_usd, abs(ga4_usd - shop_usd) / shop_usd as gap
from ga4 cross join shop
where abs(ga4_usd - shop_usd) / shop_usd > 0.05
