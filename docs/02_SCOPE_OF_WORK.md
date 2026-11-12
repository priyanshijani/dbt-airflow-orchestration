# 02 · Scope of Work

## Objective
Deliver a **public, self-contained GitHub repository** (`dbt-airflow-clickhouse-dtc-growth`) that anyone can clone and run with `docker compose up`. It demonstrates production-style analytics engineering across multiple data sources, with an AI agent layer for insight generation and pipeline debugging.

## In scope

### Ingestion (9 sources, 6 source types)

| # | Source | Type | Mode |
|---|---|---|---|
| 1 | GA4 public ecommerce sample | Cloud warehouse (BigQuery) | Live with keys, else committed Parquet sample |
| 2 | Store database: customers, orders, order_items, products, refunds | OLTP database (Postgres) | Incremental by `updated_at` |
| 3 | Meta Ads daily export | Local file (CSV) → S3 object store (SeaweedFS) | File-arrival driven |
| 4 | Google Ads daily export | Local file (CSV) → S3 landing | File-arrival driven |
| 5 | Email campaign events | Semi-structured file (JSON lines) → S3 landing | File-arrival driven |
| 6 | Budget and revenue targets | Spreadsheet (Google Sheets export / local XLSX) | Full refresh |
| 7 | Public holidays (Nager.Date) | REST API, no key | Full refresh, yearly |
| 8 | Weather (Open-Meteo) | REST API, no key | Incremental by date |
| 9 | Macro: consumer sentiment and CPI (FRED) | REST API, key | Live with key, else committed snapshot |

*Google Trends was considered but dropped from the core scope (no stable free API). See [ADR-010](DECISION_LOG.md#adr-010).*

### Transformation (dbt on ClickHouse)
- Layers: `raw` → `staging` → `intermediate` → `marts`
- Marts:
  - `fct_orders`, `fct_sessions`, `fct_marketing_spend`
  - `dim_customers`, `dim_products`, `dim_date`, `dim_channel`
  - `mart_kpi_daily`, `mart_channel_performance`, `mart_customer_cohorts`, `mart_revenue_bridge`
- ClickHouse-specific engines and settings ([ADR-004](DECISION_LOG.md#adr-004))
- Tests:
  - Generic tests and unit tests (attribution, revenue bridge)
  - Model contracts on marts
  - Source freshness
  - Elementary anomaly tests

### Orchestration (Airflow 3)
- Ingestion DAGs per source, which publish **Assets**
- A dbt DAG rendered with **Cosmos** (one task per model), triggered by those Assets
- A **simulator** DAG that "advances one day": it inserts new orders and drops new ad and email files, so incremental behaviour is visible
- Insight and triage agent DAGs
- Idempotent, backfillable runs keyed to the logical date

### AI agent layer
1. **Insight Narrator:** a weekly revenue bridge, drilled down through governed marts
2. **Failure Triage:** diagnoses failed tasks and dbt errors
3. **Schema Drift Assistant:** proposes staging model updates when a source changes shape
4. **Dev Accelerator (documentation only):** how Claude Code, the dbt MCP server and the ClickHouse MCP server are used during development

### Consumption
- **Insights Hub** (Streamlit): the brief, KPIs, pipeline health, AI ops
- dbt docs site
- Markdown briefs in `reports/`; optional Slack webhook

### Engineering quality
- GitHub Actions CI:
  - Lint (SQLFluff, ruff)
  - DAG import tests
  - `dbt build` against an ephemeral ClickHouse
  - Agent unit tests in mock mode
- `.env.example` with documented variables; secrets are never committed
- README with architecture diagram, quickstart, demo GIF or video and decision highlights

## Out of scope (stated deliberately)
- Real ad platform API connectors (Meta Marketing API, Google Ads API). These need business verification. They are simulated through CSV exports, which is also how many agencies actually deliver the data.
- Real-time streaming (Kafka). Batch with daily or hourly granularity matches the business need.
- Multi-touch attribution with ML models such as Shapley or Markov. Rule-based last-click, first-click and linear attribution plus blended metrics only. MMM is a possible extension.
- Cloud deployment such as Kubernetes or Terraform. The project runs locally in Docker; the README explains how it maps to a managed setup.
- Production-grade auth and SSO on the UIs. Local demo credentials only.
- Autonomous AI actions. Agents propose; humans approve. No agent merges code or changes data.

## Deliverables

| # | Deliverable | Phase |
|---|---|---|
| D1 | Project docs (this folder) and decision log | 0 |
| D2 | Docker Compose stack with `.env.example` | 1 |
| D3 | Synthetic data generators, committed samples, simulator | 1 |
| D4 | Ingestion DAGs for all 9 sources | 2 |
| D5 | dbt project: staging, intermediate, marts, tests | 3–4 |
| D6 | Insights Hub (Streamlit) | 4 |
| D7 | AI agents (narrator, triage, drift) with mock mode | 5 |
| D8 | CI pipeline, README, architecture diagram, demo, GitHub push | 6 |

## Constraints
- **Runs on a laptop:** the full stack must fit in about 6 GB of RAM ([ADR-008](DECISION_LOG.md#adr-008)).
- **Small data:** keep AI testing cheap, a full build fast and the repo small ([ADR-007](DECISION_LOG.md#adr-007)).
- **Zero required keys** for the base demo ([ADR-006](DECISION_LOG.md#adr-006)).
