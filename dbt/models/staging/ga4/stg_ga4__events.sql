{{
    config(
        materialized='table',
        engine='MergeTree()',
        partition_by='toYYYYMM(event_date)',
        order_by='(event_date, event_name, session_key)'
    )
}}
{#
  One row per GA4 event, flattened: the nested event_params array is unpacked into typed columns and the date is
  moved into the simulation window. A table, not a view: unpacking ~1M nested rows on every read would be wasteful.
  ORDER BY follows how marts read it: by day, then event type, then session.
#}
select
    {{ ga4_date('event_date') }}                                                   as event_date,
    {{ ga4_timestamp('event_timestamp') }}                                         as event_at,
    event_name,
    user_pseudo_id,
    {{ ga4_param('ga_session_id', 'int_value') }}                                  as ga_session_id,
    concat(user_pseudo_id, '-', toString(ifNull({{ ga4_param('ga_session_id', 'int_value') }}, 0))) as session_key,

    -- session-scoped attribution, present on session_start only
    {{ ga4_param('source', 'string_value') }}                                      as session_source,
    {{ ga4_param('medium', 'string_value') }}                                      as session_medium,
    {{ ga4_param('campaign', 'string_value') }}                                    as session_campaign,

    {{ ga4_param('page_location', 'string_value') }}                               as page_location,
    {{ ga4_param('engagement_time_msec', 'int_value') }}                           as engagement_time_msec,

    -- user's first-touch acquisition source (survives across sessions)
    tupleElement(traffic_source, 'source')                                         as first_touch_source,
    tupleElement(traffic_source, 'medium')                                         as first_touch_medium,
    tupleElement(device, 'category')                                               as device_category,
    tupleElement(geo, 'country')                                                   as country,
    tupleElement(geo, 'region')                                                    as region,
    tupleElement(geo, 'city')                                                      as city,

    tupleElement(ecommerce, 'transaction_id')                                      as transaction_id,
    tupleElement(ecommerce, 'purchase_revenue_in_usd')                             as purchase_revenue_usd
from {{ source('ga4', 'events') }}
