{#
  Latest version of each customer. This is the last place a direct identifier exists:
  the email becomes a salted hash, and name, phone and street-level fields are dropped (06_GOVERNANCE §4).
#}
select
    customer_id,
    lower(hex(SHA256(concat(lower(trim(email)), '{{ env_var("PII_HASH_SALT", "local-demo-salt") }}')))) as customer_email_hash,
    upper(country_code)                                                                              as country_code,
    region,
    city,
    accepts_marketing                                                                                as is_marketing_opted_in,
    created_at,
    updated_at
from {{ source('shop', 'customers') }} final
