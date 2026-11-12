select
    order_item_id,
    order_id,
    product_id,
    quantity,
    unit_price_usd,
    line_discount_usd,
    quantity * unit_price_usd                      as line_gross_usd,
    quantity * unit_price_usd - line_discount_usd  as line_net_usd,
    created_at,
    updated_at
from {{ source('shop', 'order_items') }} final
