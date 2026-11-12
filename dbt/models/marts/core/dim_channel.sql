{{ config(engine='MergeTree()', order_by='channel') }}
select 'paid_social' as channel, 'Paid social (Meta)' as channel_label, true as is_paid
union all select 'paid_search', 'Paid search (Google)', true
union all select 'email', 'Email / CRM', false
union all select 'organic_direct_referral', 'Organic, direct & referral', false
