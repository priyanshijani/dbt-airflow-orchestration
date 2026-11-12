{#
  One row per item on a GA4 purchase event (ARRAY JOIN unnests the items array).
  GA4 revenue is the web view of sales; the shop database is the system of record, and the two are reconciled in marts.
#}
select
    {{ ga4_date('event_date') }}                                                  as event_date,
    concat(user_pseudo_id, '-', toString(ifNull({{ ga4_param('ga_session_id', 'int_value') }}, 0))) as session_key,
    tupleElement(ecommerce, 'transaction_id')                                      as transaction_id,
    tupleElement(item, 'item_id')                                                  as product_id,
    tupleElement(item, 'item_name')                                                as item_name,
    tupleElement(item, 'item_category')                                            as item_category,
    tupleElement(item, 'price_in_usd')                                             as price_usd,
    tupleElement(item, 'quantity')                                                 as quantity,
    tupleElement(item, 'item_revenue_in_usd')                                      as item_revenue_usd
from {{ source('ga4', 'events') }}
array join items as item
where event_name = 'purchase'
