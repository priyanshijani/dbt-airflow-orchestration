# Planted stories (ground truth)

The generators plant known causes in the data so the AI agents can be **evaluated**: a correct brief has to rediscover these causes from the marts alone (06_GOVERNANCE §7, Evaluation). Dates are defined in [config.py](config.py).

| # | Window | What happened (cause) | What the data shows | Expected agent finding |
|---|---|---|---|---|
| 1 | Nov 24 – Dec 2, 2025 | BFCM sitewide 20% code (`BFCM20`) plus the BFCM Meta campaign | ~65% of orders discounted, Meta spend ×1.6–2.2, AOV and order volume up, margin down | "Revenue up, driven by order volume during the promotion; discounting cut margin" |
| 2 | Dec 8 – 14, 2025 | Meta auction pressure, with CPM ×1.6 | Meta spend steady, impressions and clicks down, fewer Meta-attributed orders, MER down | "Paid social efficiency fell: CPMs rose, so the same spend bought less reach" |
| 3 | Dec 15 – 17, 2025 | "Last shipping day" email | +140 orders from returning customers with `utm_medium=email`, a higher click rate on that campaign, none of it visible in GA4 | "Email drove returning-customer revenue; GA4 under-reports it (untracked)" |
| 4 | Jan 12 – Feb 1, 2026 | New Google PMax campaign launched | About $450/day of extra Google spend, almost no clicks or sessions, MER and blended CAC worse | "Paid search spend rose without a traffic lift; the PMax campaign is inefficient" |
| 5 | Jan 20 – 23, 2026 | Payment provider outage | ~35% of orders end in `payment_failed`; GA4 purchase events look normal; net revenue drops | "Revenue fell but GA4 purchases didn't: backend payment failures. Check payment provider" |

Background patterns (not stories): weekday seasonality, a December peak and a January slump, about 15% of orders invisible to GA4 (consent and ad blockers), platform-reported conversions over-claiming by 1.1–1.7×, ~6% refunds, ~2.5% cancellations.

## Simulated release
- The bootstrap releases data through **Jan 18, 2026**. The latest complete week (Jan 12–18) contains story 4.
- Each `simulator_advance_day` releases one more day. Advancing to Jan 25 brings story 5 into the latest week.
