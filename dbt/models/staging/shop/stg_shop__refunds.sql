select
    refund_id,
    order_id,
    amount_usd,
    reason         as refund_reason,
    created_at     as refunded_at,
    toDate(created_at) as refund_date,
    updated_at
from {{ source('shop', 'refunds') }} final
