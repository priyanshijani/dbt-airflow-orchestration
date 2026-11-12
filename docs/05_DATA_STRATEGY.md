# 05 · Data Strategy

## 1. Guiding principles
1. **Small but realistic.** Volumes are small enough that a full build takes minutes and AI testing is cheap. The data still carries realistic patterns and realistic mess.
2. **One coherent universe.** All synthetic sources describe the same fictional company, Kestrel Goods, over the same time window, and they join correctly.
3. **Mess on purpose.** File sources contain the problems real exports have, so staging has real cleaning work to do.
4. **Reproducible.** Every generator is seeded (`SEED=42`), so the same seed gives byte-identical data.
5. **Works offline.** Every external source has a committed fallback snapshot.

## 2. Time window and date alignment
- The GA4 public sample covers **2020-11-01 → 2021-01-31** (92 days).
- The simulation window is **2025-11-02 → 2026-02-01**, the most recent complete holiday season ([ADR-020](DECISION_LOG.md#adr-020)).
- GA4 dates are shifted by exactly **261 weeks (1,827 days)**. Weekdays stay aligned, and Black Friday 2020 (Nov 27) lands on Black Friday 2025 (Nov 28). The `ga4_date_shift` dbt macro applies the same shift ([ADR-020](DECISION_LOG.md#adr-020)).
- Synthetic sources are generated directly in the shifted window, with matching seasonality (Black Friday spike, December peak, January slump).
- External APIs (weather, holidays, FRED) are fetched for the **real** shifted window. Their dates are genuine.

## 3. Source catalogue and target volumes

> Table names below are logical (`raw_<source>.<table>`). Physically they are `raw.<source>___<table>` ([ADR-022](DECISION_LOG.md#adr-022)).

| Source | Raw table(s) | Grain | Target rows (92 days) | Notes |
|---|---|---|---|---|
| GA4 sample | `raw_ga4.events` | event | TBD at extract (funnel events only, user-sampled if needed) | Native GA4 shape with `event_params` and `items` trimmed to the keys we use; committed as Parquet, ≤ 25 MB ([ADR-021](DECISION_LOG.md#adr-021)) |
| Shop: customers | `raw_shop.customers` | customer | ~4,000 | Includes PII-like fields (email, name), masked in staging |
| Shop: orders | `raw_shop.orders` | order | ≈ GA4 purchases ÷ 0.85 | One order per GA4 purchase plus ~15% untracked; status lifecycle (placed → paid → shipped → delivered / cancelled / payment_failed) |
| Shop: order_items | `raw_shop.order_items` | line | ~20,000 | |
| Shop: products | `raw_shop.products` | product | ~150 | Price changes, captured in a snapshot |
| Shop: refunds | `raw_shop.refunds` | refund | ~500 | |
| Meta Ads export | `raw_meta_ads.daily` | campaign × ad set × day | ~2,000 | Daily CSV files |
| Google Ads export | `raw_google_ads.daily` | campaign × day | ~1,500 | Daily CSV files |
| Email events | `raw_email.events` | event | ~25–50k | JSONL: send, open, click, unsubscribe |
| Budget & targets | `raw_budget.monthly` | channel × month | ~30 | XLSX, finance-maintained |
| Holidays | `raw_holidays.public_holidays` | country × date | ~50 | Nager.Date (US, GB) |
| Weather | `raw_weather.daily` | city × day | ~460 | Open-Meteo, 5 key cities |
| FRED | `raw_fred.observations` | series × date | ~10 | UMCSENT (monthly), CPIAUCSL (monthly) |

**Total:** about 220k rows. A full `dbt build` should take under 2 minutes.

## 4. Deliberate data-quality issues (staging must handle these)

| Source | Issue | Handled by |
|---|---|---|
| Meta Ads CSV | Spend in mixed currencies (USD, GBP, EUR) depending on ad account | `currency_to_usd` macro + FX seed |
| Meta Ads CSV | Duplicate rows when a day is re-exported | Dedup on natural key, keeping the latest `_loaded_at` |
| Google Ads CSV | Cost in **micros** (`cost_micros`) | Divide by 1e6 in staging |
| Google Ads CSV | Date as `MM/DD/YYYY` string | Explicit parse |
| Email JSONL | Nested `properties` object, optional fields | JSON extraction with defaults |
| Email JSONL | Timestamps in local time with an offset | Normalise to UTC |
| Shop orders | Multiple versions per order (status updates) | `ReplacingMergeTree` + latest-version logic |
| Shop customers | Email case and whitespace inconsistent | `lower(trim())` before hashing |
| Budget XLSX | Merged header cells, channel names that don't match ads data | Seed mapping `channel_mapping.csv` |
| GA4 | `(not set)` and `(direct)` sources, obfuscated `<Other>` values | Mapped to a "Direct / Unknown" channel |
| Chaos mode | `amount_spent` renamed to `spend` in Meta export | Detected by schema-change capture and contract test failure → triage agent |

## 5. Synthetic generation design
- **Library:** Python with `numpy` and `Faker`, seeded.
- **Causal structure.** This makes the AI explanations *discoverable*: there are real drivers to find.
  - Daily sessions per channel = baseline × weekday factor × seasonality × spend elasticity (paid channels) × weather effect (drinkware sells better in heat).
  - Conversion rate varies by channel and new vs returning customers. It dips during a planted "site incident" week.
  - AOV rises during Black Friday bundles.
  - **Planted stories** for the narrator to find, documented in `data/generators/STORIES.md`:
    1. A Meta CPM spike in week N: spend up, efficiency down.
    2. An email campaign drives returning-customer revenue in week M.
    3. Checkout conversion drops for 4 days (a planted bug) in the final complete week.
- **Bridging GA4 and orders.** Synthetic orders carry a `ga_session_id`, sampled from GA4 purchase sessions in the matching shifted date. This allows session → order joins for attribution. The fit is approximate by design, and documented.

## 6. Warehouse layers

| Layer | Schema | Materialisation | Contents | Who reads it |
|---|---|---|---|---|
| Raw | `raw_<source>` | dlt-managed tables | As delivered, plus load metadata | dbt staging only |
| Staging | `staging` | view (table for heavy JSON parsing) | Cleaned, typed, renamed, deduped, PII-masked; 1:1 with source entities | Intermediate |
| Intermediate | `intermediate` | ephemeral / table | Sessionisation, attribution, currency conversion, joins | Marts |
| Marts | `marts` | table / incremental, **contracted** | Facts, dimensions, KPI marts | Hub, agents, analysts |
| Meta | `meta` | tables | dbt run results, schema changes, ingestion log | Hub, triage agent |
| AI | `ai` | tables | briefs, incidents, agent_runs (token/cost log) | Hub |

## 7. Metric definitions
There is one definition per metric, documented in `dbt/models/marts/finance/_metrics.yml` and computed only in marts.

| Metric | Definition | Grain |
|---|---|---|
| **Net revenue** | Σ order item revenue − discounts − refunds, USD, excluding cancelled orders | day / channel |
| **Sessions** | Distinct `ga_session_id` (GA4) | day / channel |
| **Conversion rate** | Orders ÷ sessions | day / channel |
| **AOV** | Net revenue ÷ orders | day |
| **Total ad spend** | Meta spend (USD) + Google cost (USD) | day / channel / campaign |
| **MER** (marketing efficiency ratio) | Net revenue ÷ total ad spend | day / week |
| **Blended CAC** | Total ad spend ÷ new customers | week / month |
| **nc-ROAS** (new-customer ROAS) | New-customer net revenue ÷ paid spend | week / channel |
| **Platform-reported vs blended gap** | Σ platform conversions value ÷ net revenue | week |
| **Cohort LTV (n days)** | Cumulative net revenue per customer by first-order month | cohort × age |
| **Target attainment** | Actual net revenue ÷ target (budget sheet) | month / channel |

**Revenue bridge** (week over week):
`ΔRevenue ≈ Δtraffic effect + Δconversion effect + ΔAOV effect`, using a log decomposition so the parts add up exactly. It is computed in `mart_revenue_bridge` and covered by a dbt unit test.

## 8. Attribution approach
- **Session channel:** derived from GA4 `source/medium/campaign` through the `channel_mapping` seed (Paid Social, Paid Search, Email, Organic Search, Direct, Referral).
- **Order attribution:** last non-direct click within a 7-day lookback. First-click and linear are offered as alternative columns.
- **Blended metrics are the headline.** Attributed metrics are diagnostic only. Platform-reported conversions are shown next to them to make the over-counting visible.

## 9. Data lifecycle
- Raw is append-only and never mutated. A full replay comes from raw plus dbt `--full-refresh`.
- `simulator_advance_day` extends the window by one day, which demonstrates incremental loads.
- `make reset` drops all schemas and reloads from generators and samples.
