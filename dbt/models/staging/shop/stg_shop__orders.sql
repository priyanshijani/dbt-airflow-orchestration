{#
  Latest version of each order (ReplacingMergeTree keeps every status change; FINAL collapses them).
  Business meaning (which statuses count as revenue) is decided downstream, not here.
#}
select
    order_id,
    order_number,
    customer_id,
    ga_session_id,
    ga_client_id                                   as ga_user_pseudo_id,
    status                                         as order_status,
    upper(currency)                                as currency,
    subtotal_usd,
    discount_usd,
    shipping_usd,
    tax_usd,
    total_usd,
    discount_code,
    nullIf(utm_source, '')                         as utm_source,
    nullIf(utm_medium, '')                         as utm_medium,
    nullIf(utm_campaign, '')                       as utm_campaign,
    device_type,
    created_at                                     as ordered_at,
    toDate(created_at)                             as order_date,
    updated_at
from {{ source('shop', 'orders') }} final
