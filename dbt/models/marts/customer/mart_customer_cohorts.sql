{{ config(engine='MergeTree()', order_by='(cohort_month, months_since_first_order)') }}
{# Cohort = month of a customer first paid order. For each later month: customers still buying and revenue. #}
select
    toStartOfMonth(c.first_order_date) as cohort_month,
    dateDiff('month', toStartOfMonth(c.first_order_date), toStartOfMonth(o.order_date)) as months_since_first_order,
    uniqExact(o.customer_id) as active_customers,
    sum(o.net_revenue_usd) as revenue_usd
from {{ ref('fct_orders') }} as o
inner join {{ ref('dim_customers') }} as c on c.customer_id = o.customer_id
group by cohort_month, months_since_first_order
