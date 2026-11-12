{#
  Email platform events. Timestamps arrive in New York local time with an offset; they become UTC here.
  Apple Mail pre-fetches messages, so some "opens" are machines: they are flagged, not dropped.
  Email addresses are hashed with the same salt as customers, so the two can be joined without exposing either.
#}
select
    id                                                                                   as event_id,
    type                                                                                 as event_type,
    parseDateTime64BestEffort(timestamp, 3, 'UTC')                                       as event_at,
    toDate(parseDateTime64BestEffort(timestamp, 3, 'UTC'))                               as event_date,
    lower(hex(SHA256(concat(lower(trim(profile__email)), '{{ env_var("PII_HASH_SALT", "local-demo-salt") }}')))) as customer_email_hash,
    toInt64OrNull(profile__external_id)                                                  as customer_id,
    properties__campaign_id                                                              as campaign_id,
    properties__campaign_name                                                            as campaign_name,
    properties__subject                                                                  as subject,
    properties__utm_campaign                                                             as utm_campaign,
    ifNull(properties__machine_open, false)                                              as is_machine_open,
    properties__url                                                                      as clicked_url,
    _source_file
from {{ source('email', 'events') }}
order by _source_file desc
limit 1 by id
