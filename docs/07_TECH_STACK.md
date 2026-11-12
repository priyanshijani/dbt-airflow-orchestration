# 07 · Tech Stack

Exact versions are pinned in `requirements*.txt`, `Dockerfile`s and `docker-compose.yml` when each component is built. The table records the choice and the reasoning.

| Layer | Tool | Why this | Alternatives considered | ADR |
|---|---|---|---|---|
| Warehouse | **ClickHouse** (OSS, LTS release, Docker) | Columnar OLAP; makes the portfolio stand out; free and runs locally; shows engine-level modelling skill | Snowflake (trial expires), BigQuery (vendor lock-in, needs keys), DuckDB (no server/concurrency story), Postgres (not OLAP) | [001](DECISION_LOG.md#adr-001) |
| Cloud source | **BigQuery** (free sandbox) | GA4 exports to BigQuery natively, so it's the realistic way to source GA4 | GA4 Data API (aggregated only, quota-limited) | [001](DECISION_LOG.md#adr-001) |
| Orchestration | **Apache Airflow 3.3** | Industry standard; Assets for data-aware scheduling; new UI | Dagster (great, but less common in job descriptions), Prefect | [003](DECISION_LOG.md#adr-003) |
| dbt-in-Airflow | **Astronomer Cosmos** | Renders each dbt model as a task: retries per model, precise failure context | BashOperator `dbt build` (one opaque task) | [003](DECISION_LOG.md#adr-003) |
| Transformation | **dbt-core** + **dbt-clickhouse** adapter | Standard analytics engineering tool; contracts, unit tests, docs, lineage | SQLMesh | [002](DECISION_LOG.md#adr-002) |
| Ingestion | **dlt** (data load tool) | A Python library, not a service; native ClickHouse destination; incremental cursors and schema evolution built in | Airbyte (heavy, 10+ containers), custom scripts (reinventing the wheel), Fivetran (paid) | [005](DECISION_LOG.md#adr-005) |
| Source OLTP | **Postgres 16** | Simulates a production store database; also hosts Airflow metadata | MySQL | [008](DECISION_LOG.md#adr-008) |
| Object storage | **SeaweedFS** | S3-compatible landing zone, so the code is identical to the AWS S3 version; Apache-2.0 and actively maintained | MinIO (community images discontinued), RustFS (very new), local bind mount (less realistic) | [018](DECISION_LOG.md#adr-018) |
| Data quality | dbt tests, contracts, unit tests + **Elementary** | Native tests plus anomaly detection and a run-results history | Great Expectations, Soda | — |
| AI runtime | Thin provider adapter: **Google GenAI SDK** (default) or Anthropic SDK; function calling + JSON-schema output | Direct, transparent control over tools, caps and logging; no lock-in to one provider | LangChain / LangGraph (extra abstraction not needed) | [012](DECISION_LOG.md#adr-012), [017](DECISION_LOG.md#adr-017) |
| AI models | **Gemini free tier**: a Flash model for reasoning, Flash-Lite for classification (IDs pinned in Phase 5) | Free to test and free for reviewers to run; configurable in `.env` | Claude (optional alternative provider) | [017](DECISION_LOG.md#adr-017) |
| AI dev tooling | Claude Code + **dbt MCP server** + **ClickHouse MCP server** | Shows AI-assisted delivery: scaffolding, exploration, review | — | [012](DECISION_LOG.md#adr-012) |
| UI | **Streamlit** (Insights Hub) | Python-native; renders the narrative brief, charts and incident reports in one app | Metabase / Superset (good for charts, poor for narrative and agent output, plus another heavy container) | [009](DECISION_LOG.md#adr-009) |
| Synthetic data | Python, `numpy`, `Faker` | Seeded, causal generators | Mockaroo (not reproducible in code) | — |
| Containers | Docker Compose | One-command start for reviewers | Kubernetes (overkill) | [008](DECISION_LOG.md#adr-008) |
| CI | GitHub Actions | Lint (SQLFluff, ruff), DAG tests, dbt build on ephemeral ClickHouse, agent evals in mock mode, secret scan (gitleaks) | — | — |
| Dev UX | `Makefile` | `make up`, `make bootstrap`, `make simulate-day`, `make break-ads-schema`, `make reset` | — | — |

## Python packages (indicative)
- **Airflow image:** `apache-airflow`, `astronomer-cosmos`, `dbt-core`, `dbt-clickhouse`, `dlt[clickhouse,filesystem,sql_database]`, `google-cloud-bigquery`, `s3fs`, `openpyxl`, `google-genai`, `anthropic` (optional), `clickhouse-connect`, `sqlglot` (SQL safety parsing), `requests`
- **Insights Hub image:** `streamlit`, `clickhouse-connect`, `plotly`, `pandas`, `requests`
- **Generators:** `numpy`, `pandas`, `Faker`, `pyarrow`

dbt runs in a **separate virtualenv** inside the Airflow image (Cosmos `ExecutionMode.VIRTUALENV` or a pre-built venv path), so its dependencies don't conflict with Airflow's.
