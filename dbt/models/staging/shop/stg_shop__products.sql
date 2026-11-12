select
    product_id,
    sku,
    name                as product_name,
    category            as product_category,
    price_usd,
    cost_usd,
    is_active,
    created_at,
    updated_at
from {{ source('shop', 'products') }} final
