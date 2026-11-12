{{ config(engine='MergeTree()', order_by='product_id') }}
select product_id, sku, product_name, product_category, price_usd, cost_usd, is_active
from {{ ref('stg_shop__products') }}
