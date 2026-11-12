# 04 · Architecture Design Document

## 1. System context

```
                        ┌───────────────────────────── docker compose ─────────────────────────────┐
 EXTERNAL               │                                                                          │
 ─────────              │   ORCHESTRATION            STORAGE / COMPUTE           CONSUMPTION       │
 BigQuery (GA4) ───────►│   ┌──────────────┐        ┌───────────────────┐       ┌──────────────┐   │
 FRED API ─────────────►│   │  Airflow 3   │        │    ClickHouse     │       │ Insights Hub │   │
 Open-Meteo API ───────►│   │  scheduler   │──dlt──►│  raw_*            │──────►│ (Streamlit)  │   │
 Nager.Date API ───────►│   │  api-server  │        │  staging          │       └──────────────┘   │
 Gemini API ◄──────────►│   │  dag-proc.   │──dbt──►│  intermediate     │       ┌──────────────┐   │
                        │   │  (Cosmos)    │        │  marts            │──────►│  dbt docs    │   │
 LOCAL / SIMULATED      │   └──────┬───────┘        │  meta / ai        │       └──────────────┘   │
 ─────────────────      │          │                └───────────────────┘                          │
 Store DB ─────────────►│   ┌──────▼───────┐        ┌───────────────────┐                          │
 (Postgres: shop db)    │   │  Postgres    │        │ SeaweedFS (S3 API)│◄── ads CSV / email JSON  │
                        │   │  airflow db  │        │  landing bucket   │    budget XLSX           │
                        │   │  shop db     │        └───────────────────┘                          │
                        │   └──────────────┘                                                       │
                        └──────────────────────────────────────────────────────────────────────────┘
```

## 2. Containers

| Service | Image (pinned at build time) | Purpose | Port |
|---|---|---|---|
| `postgres` | postgres:16 | Two databases: `airflow` (metadata) and `shop` (simulated OLTP source) | 5432 |
| `clickhouse` | clickhouse/clickhouse-server (LTS) | Analytical warehouse | 8123, 9000 |
| `seaweedfs` | chrislusf/seaweedfs:4.48 | S3-compatible landing zone for file sources ([ADR-018](DECISION_LOG.md#adr-018)) | 8333 (S3), 8888 (filer UI) |
| `airflow` | custom (Airflow 3.3 + Cosmos + dlt + dbt venv) | `airflow standalone`: api-server, scheduler, dag-processor and triggerer in one container, LocalExecutor ([ADR-019](DECISION_LOG.md#adr-019)) | 8080 |
| `insights-hub` | custom (Streamlit) | UI for briefs, KPIs, health and AI ops | 8501 |
| `dbt-docs` | added in Phase 4 | Model documentation and lineage | 8081 |

**Footprint decisions** ([ADR-008](DECISION_LOG.md#adr-008)):
- LocalExecutor, with no Celery, Redis or workers.
- One Postgres instance serving two databases.
- All Airflow components in one container through `airflow standalone` ([ADR-019](DECISION_LOG.md#adr-019)).
- ClickHouse tuned for low memory (`infra/clickhouse/config.d/low_memory.xml`).

## 3. Data flow

```
 [source] ──extract (dlt)──► raw_<source>.<table>   (append-only, + _loaded_at, _batch_id)
                                    │  publishes Asset("clickhouse://raw/<source>")
                                    ▼
          Airflow Asset schedule: dbt DAG starts when ALL required raw Assets update
                                    │
              dbt source freshness ─┤ fail on critical sources → stop
                                    ▼
          staging (views or light tables)  →  intermediate  →  marts (contracted)
                                    │  publishes Asset("clickhouse://marts/kpi_daily")
                                    ▼
          insight_narrator DAG (Asset-triggered, weekly gate) → ai.briefs → Insights Hub
          on_failure_callback (any task) → triage agent → ai.incidents → Insights Hub
```

### DAG inventory

| DAG | Schedule | Produces |
|---|---|---|
| `ingest_shop_postgres` | hourly | `raw/shop` Asset |
| `ingest_ga4` | daily | `raw/ga4` Asset |
| `ingest_file_drops` (ads, email, budget) | hourly (every 15 min overloaded the demo container), incremental by file | `raw/meta_ads`, `raw/google_ads`, `raw/email`, `raw/budget` |
| `ingest_external_apis` (weather, holidays, FRED) | daily | `raw/weather`, `raw/holidays`, `raw/fred` |
| `dbt_transform` | Asset-triggered | `marts/*` Assets |
| `ai_insight_narrator` | Asset-triggered on `marts/kpi_daily`, runs only if a new week has completed (or on manual trigger) | `ai/briefs` |
| `ai_schema_drift` | Asset-triggered on `meta/schema_changes` | `proposals/*.patch` |
| `simulator_advance_day` | manual / optional daily | New rows in `shop` db and new files in the S3 landing bucket (releases one held-back day, [ADR-020](DECISION_LOG.md#adr-020)) |
| `bootstrap` | manual | Runs the full first load end to end |

## 4. Ingestion design (dlt)
- **Why dlt:** it is a Python library, not a service, so it adds no extra containers. It has a native ClickHouse destination and handles schema inference, schema evolution and incremental cursors ([ADR-005](DECISION_LOG.md#adr-005)).
- **Postgres:** `sql_database` source, incremental on `updated_at`, `write_disposition="append"`. Deduplication happens downstream through `ReplacingMergeTree`.
- **Files:** `filesystem` source over the S3 landing bucket (s3fs). Processed files are tracked through dlt state, so each file loads exactly once.
- **BigQuery:** a custom resource that runs a parameterised query against `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`. It only reads date-filtered table suffixes, which stays within the sandbox's free 1 TB/month query allowance.
- **Schema contracts in dlt:** raw tables use `evolve` (new columns are accepted). Changes are captured to `meta.schema_changes` for the drift agent. Breaking changes surface in dbt staging through contracts and tests.

## 5. ClickHouse modelling (the OLAP engineering)

See [ADR-004](DECISION_LOG.md#adr-004) for the full reasoning.

| Pattern | Where | Why |
|---|---|---|
| `MergeTree` with `ORDER BY` matched to the main query filter | All fact tables, e.g. `fct_sessions ORDER BY (event_date, channel, session_id)` | ClickHouse's sparse primary index; the ordering decides how much data is skipped |
| `PARTITION BY toYYYYMM(date)` | Facts | Easy partition-level backfills and drops; monthly to avoid too many parts (small data) |
| `ReplacingMergeTree(_version)` | Mutable entities: orders, customers, products | No in-place UPDATE in ClickHouse; latest version wins. Queries use `FINAL` or `argMax` in dbt where exactness is needed |
| `AggregatingMergeTree` + `-State` / `-Merge` functions | `mart_kpi_daily_agg` | Pre-aggregated rollups, so dashboard queries stay fast as data grows |
| `LowCardinality(String)` | channel, campaign, device, country, category | Dictionary encoding: smaller storage and faster GROUP BY |
| ClickHouse **dictionaries** | `dim_channel`, `dim_date` lookups | In-memory key/value joins for small dimensions |
| `Nullable` avoided in keys | All ORDER BY keys | Nullable columns hurt index efficiency; default values used instead |
| dbt incremental strategies | `append` (events), `delete+insert` (orders by date window), `table` (small dims) | The strategy is chosen per model based on how the data mutates |
| Codecs (`Delta`, `ZSTD`) | Timestamp and monotonically increasing columns | Shows awareness of compression; small gain at this scale but documented |

## 6. dbt project layout

```
dbt/
  models/
    staging/<source>/stg_<source>__<entity>.sql       # 1:1 with raw, cleaned
    intermediate/int_<domain>__<verb>.sql             # joins, sessionisation, attribution
    marts/
      core/        dim_customers, dim_products, dim_date, dim_channel, fct_orders
      marketing/   fct_sessions, fct_marketing_spend, mart_channel_performance
      finance/     mart_kpi_daily, mart_revenue_bridge, mart_target_tracking
      customer/    mart_customer_cohorts
  macros/          ga4_date_shift, currency_to_usd, clickhouse engine helpers
  tests/           singular tests (e.g., revenue reconciliation GA4 vs orders within tolerance)
  seeds/           channel_mapping.csv, fx_rates_fallback.csv
  snapshots/       product price history (SCD2)
```

dbt runs inside Airflow through **Astronomer Cosmos**. Each model becomes an Airflow task with its tests attached, so failures are isolated per model and each one triggers triage with precise context ([ADR-003](DECISION_LOG.md#adr-003)).

## 7. AI agent layer

```
                ┌──────────────────────── agents/ (Python package) ───────────────────────┐
                │  core/llm.py        Provider-agnostic client (gemini | anthropic):      │
                │                     mode (live/mock/off), token cap, 429 backoff,       │
                │                     usage logging → ai.agent_runs                       │
                │  core/tools.py      run_marts_query (read-only, marts schema only,      │
                │                     SELECT-only parser check, LIMIT 500, 10s timeout)   │
                │                     get_metric_definitions, get_task_log, get_dbt_errors│
                │  narrator/          detect (SQL, deterministic) → agent drill-down loop │
                │                     → structured brief (JSON schema) → render Markdown  │
                │  triage/            context collector → classify (lite) → diagnose      │
                │  drift/             schema diff → proposed staging SQL + YAML patch     │
                │  fixtures/          recorded responses for mock mode                    │
                └──────────────────────────────────────────────────────────────────────────┘
```

**Design principles** ([ADR-011](DECISION_LOG.md#adr-011)):
1. **Detection is deterministic; explanation is generative.** SQL decides *whether* something changed. The LLM explains *why*, using tool results.
2. **Governed access only.** The agent's ClickHouse user has `SELECT` on `marts.*` and nothing else.
3. **Evidence-backed output.** The structured output requires each driver to cite a query ID. The renderer rejects drivers with no evidence.
4. **Bounded usage.** A per-run token budget, a maximum of 8 tool calls (which keeps a run within free-tier per-minute limits), backoff on HTTP 429, and a compact, stable system prompt.
5. **Human in the loop.** Agents write briefs, incidents and proposals. They never change code or data.

**Model selection** (configurable in `.env`, see [ADR-017](DECISION_LOG.md#adr-017)):
- `LLM_PROVIDER=gemini` (default). `LLM_MODEL_REASONING` (narrator, drift, triage diagnosis) and `LLM_MODEL_LIGHT` (triage classification) are set to free-tier Gemini Flash / Flash-Lite models. Exact model IDs are pinned in `.env.example` when Phase 5 is built, after checking the models AI Studio currently lists as free.
- `LLM_PROVIDER=anthropic` is an optional alternative that uses the same tools and prompts.

**Integration:** the agents use a thin provider adapter in `agents/core/llm.py`. It uses the Google GenAI SDK by default, or the Anthropic SDK, with function calling and JSON-schema structured output, and is called from Airflow tasks. The agent loop, tools, caps and mock replay don't depend on which provider is used. The **ClickHouse MCP server** and **dbt MCP server** are configured in `.mcp.json` for interactive development in Claude Code, which is documented as the "Dev Accelerator" workflow ([ADR-012](DECISION_LOG.md#adr-012)).

## 8. Insights Hub (Streamlit)
- Connects to ClickHouse as `hub_reader`, with read access to the `marts`, `meta` and `ai` schemas.
- Pages: Weekly Brief · KPI Overview · Pipeline Health · AI Ops.
- "Generate brief now" calls the Airflow REST API to trigger `ai_insight_narrator`. The UI never holds the LLM logic, which keeps a single code path.

## 9. Security model (local demo)

| Principal | Access |
|---|---|
| `etl_writer` | Read/write on `raw`, `staging`, `intermediate`, `marts`, `meta` |
| `agent_reader` | SELECT on `marts.*` only |
| `hub_reader` | SELECT on `marts.*`, `meta.*`, `ai.*` |
| `ai_writer` | INSERT on `ai.*` |

All secrets come from `.env`; nothing is committed. `.env.example` documents every variable.

## 10. How this maps to production
- Docker Compose → managed Airflow (MWAA, Astro or Cloud Composer)
- ClickHouse container → ClickHouse Cloud
- SeaweedFS → S3 or GCS
- Postgres shop db → a read replica, or CDC through Debezium
- Streamlit → an internal app behind SSO
- Secrets → a secrets backend such as AWS Secrets Manager or GCP Secret Manager
