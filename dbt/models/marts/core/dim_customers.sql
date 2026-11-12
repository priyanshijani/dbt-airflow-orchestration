{{ config(engine='MergeTree()', order_by='customer_id') }}
{# No direct identifiers: staging already hashed the email and dropped names and street data. #}
with orders as (
    select
        customer_id,
        min(order_date) as first_order_date,
        count() as orders_count,
        sum(net_revenue_usd) as lifetime_net_revenue_usd
    from {{ ref('int_orders__attributed') }}
    where counts_as_revenue
    group by customer_id
)
select
    toUInt64(c.customer_id) as customer_id,
    c.customer_email_hash as customer_email_hash,
    c.country_code as country_code,
    c.region as region,
    c.is_marketing_opted_in as is_marketing_opted_in,
    toDate(c.created_at) as signup_date,
    o.first_order_date as first_order_date,
    o.orders_count as orders_count,
    o.lifetime_net_revenue_usd as lifetime_net_revenue_usd
from {{ ref('stg_shop__customers') }} as c
left join orders as o on o.customer_id = c.customer_id
