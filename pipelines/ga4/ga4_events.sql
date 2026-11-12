-- GA4 funnel-events extract from Google's public obfuscated ecommerce sample.
-- Used by the one-off sample extract (scripts/extract_ga4_sample.py) and by the
-- live BigQuery ingestion in Phase 2, so both paths land the same shape.
--
-- Shape stays close to the native GA4 export (nested event_params / items) so the
-- dbt staging layer still does the GA4 unnesting work. Only keys and events the
-- marts need are kept to stay small (ADR-007, ADR-018).
SELECT
  event_date,
  event_timestamp,
  event_name,
  user_pseudo_id,
  user_first_touch_timestamp,
  ARRAY(
    SELECT AS STRUCT
      p.key,
      p.value.string_value AS string_value,
      p.value.int_value    AS int_value,
      p.value.double_value AS double_value
    FROM UNNEST(event_params) AS p
    WHERE p.key IN (
      'ga_session_id', 'ga_session_number', 'page_location', 'page_referrer',
      'source', 'medium', 'campaign', 'session_engaged', 'engagement_time_msec'
    )
  ) AS event_params,
  STRUCT(
    device.category         AS category,
    device.operating_system AS operating_system,
    device.web_info.browser AS browser
  ) AS device,
  STRUCT(geo.country AS country, geo.region AS region, geo.city AS city) AS geo,
  STRUCT(
    traffic_source.source AS source,
    traffic_source.medium AS medium,
    traffic_source.name   AS name
  ) AS traffic_source,
  STRUCT(
    ecommerce.transaction_id          AS transaction_id,
    ecommerce.purchase_revenue_in_usd AS purchase_revenue_in_usd,
    ecommerce.total_item_quantity     AS total_item_quantity
  ) AS ecommerce,
  ARRAY(
    SELECT AS STRUCT
      i.item_id, i.item_name, i.item_category, i.price_in_usd, i.quantity, i.item_revenue_in_usd
    FROM UNNEST(items) AS i
    WHERE event_name = 'purchase'
  ) AS items
FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
WHERE _TABLE_SUFFIX BETWEEN @start_suffix AND @end_suffix
  AND event_name IN UNNEST(@event_names)
  AND MOD(ABS(FARM_FINGERPRINT(user_pseudo_id)), 100) < @sample_pct
