# 06 · Data Governance

## 1. Ownership (RACI, simulated)

| Domain | Data owner (accountable) | Steward (responsible) | Consumers |
|---|---|---|---|
| Web analytics (GA4) | Head of Growth | Analytics engineer | Marketing, agents |
| Orders and customers | Head of Engineering | Analytics engineer | Finance, marketing, agents |
| Paid media | Performance marketing lead | Analytics engineer | Marketing, finance |
| Email | CRM manager | Analytics engineer | Marketing |
| Budget and targets | FP&A lead | FP&A analyst | Leadership, marketing |

Each source and mart declares an owner in dbt `meta: { owner: ..., domain: ... }`, and it appears in dbt docs.

## 2. Naming conventions

| Object | Convention | Example |
|---|---|---|
| Raw table | `raw.<source>___<table>` | `raw.meta_ads___meta_ads_daily` |
| Staging model | `stg_<source>__<entity>` | `stg_shop__orders` |
| Intermediate model | `int_<domain>__<description>` | `int_marketing__sessions_attributed` |
| Fact / dimension | `fct_<process>` / `dim_<entity>` | `fct_orders`, `dim_customers` |
| KPI mart | `mart_<subject>` | `mart_kpi_daily` |
| Columns | snake_case; `_id` keys; `_at` timestamps (UTC); `_date` dates; `is_` / `has_` booleans; `_usd` for money | `net_revenue_usd`, `is_new_customer` |
| DAGs | `<verb>_<subject>` | `ingest_shop_postgres` |

## 3. Data quality framework

| Layer | Check | Tool | On failure |
|---|---|---|---|
| Ingestion | Row count > 0 for expected file drops; schema-change capture | dlt + Airflow | Warn; record in `meta.schema_changes` |
| Sources | Freshness (`warn_after`, `error_after`) | dbt source freshness | Error on critical sources → block downstream marts |
| Staging | `unique` + `not_null` on primary keys; `accepted_values` on enums | dbt generic tests | Fail the model task → triage |
| Intermediate | Referential integrity (`relationships`) | dbt | Fail → triage |
| Marts | **Model contracts** (column names, types, constraints) | dbt contracts | Build fails → triage |
| Marts | Unit tests: attribution, revenue bridge additivity | dbt unit tests | CI fails |
| Marts | Reconciliation: GA4 purchase revenue vs orders within ±X% tolerance | singular test, `severity: warn` | Warn, shown on Pipeline Health |
| Marts | Volume and freshness anomalies | Elementary | Warn, shown on Pipeline Health |

**Test severity policy:** keys and contracts are `error`. Reconciliations and anomalies are `warn`. Every `warn` is visible on Pipeline Health, never silently ignored.

## 4. PII handling
- PII-like fields (customer email, name, phone, address) exist **only** in `raw_shop.customers`.
- Staging produces `customer_email_hash = sha256(lower(trim(email)) || salt)`. Names and addresses are dropped. Country and region are kept.
- Marts contain **no direct identifiers**.
- `agent_reader` and `hub_reader` have no access to `raw_*` or `staging`, so PII can never reach an LLM prompt or the UI.
- The salt is supplied through `.env` (`PII_HASH_SALT`).
- All "PII" is synthetic (Faker). This control is shown for practice, not because real data is at risk.

## 5. Access control
See [04_ARCHITECTURE.md §9](04_ARCHITECTURE.md#9-security-model-local-demo). Principle of least privilege: each service has its own ClickHouse user, and roles are created in `clickhouse/init/*.sql`.

## 6. Change management
- All changes go through a PR. CI runs lint, DAG import tests, `dbt build` on modified models and their downstream models (`state:modified+`), and agent tests in mock mode.
- Changing a contracted mart requires a contract version bump and an entry in the decision log if it is a breaking change.
- **Decision log:** every architecture or modelling decision with trade-offs goes into [DECISION_LOG.md](DECISION_LOG.md).

## 7. AI governance

| Control | Implementation |
|---|---|
| **Data minimisation** | Agents see only marts (aggregated, PII-free) and logs. No raw rows or PII reach the LLM. |
| **Read-only** | `agent_reader` has SELECT on `marts.*` only. The SQL tool parses queries and rejects anything that isn't a single SELECT. |
| **Bounded execution** | Maximum 8 tool calls per run, result rows capped at 500, query timeout 10 seconds, per-run token budget (`AI_MAX_INPUT_TOKENS`, `AI_MAX_OUTPUT_TOKENS`). |
| **Evidence and traceability** | Each brief stores the prompt version, model, the tool calls made, query text, and the result hash. Every number in a brief must trace back to a stored query. |
| **Hallucination check** | After generation, a validator re-runs each cited query and checks that the quoted numbers match within rounding. Failed checks mark the brief "unverified". |
| **Human in the loop** | Agents create briefs, incidents and patch proposals only. No autonomous merges, deploys or data changes. |
| **Cost transparency** | Every call is logged to `ai.agent_runs` (tokens in/out, cached tokens, latency, estimated cost) and shown on the AI Ops page. |
| **Graceful degradation** | `AI_MODE=off` / `mock` / `live`. With no key, the platform is fully functional and simply has no live AI. |
| **Prompt versioning** | Prompts live in `agents/prompts/*.md` with a version header, and changes are reviewed like code. |
| **Evaluation** | `agents/evals/`: a handful of fixed scenarios (planted stories, chaos incidents). Each checks that the agent names the right driver or root cause. Runs in CI in mock mode, and on demand in live mode. |

## 8. Documentation standards
- Every staging and mart model has a description, and every mart column is documented.
- Sources document their update cadence, owner and known issues.
- dbt docs are served at `localhost:8081` (from Phase 4), with lineage from source to mart.
