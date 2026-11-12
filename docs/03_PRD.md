# 03 · Product Requirements Document (PRD)

## 1. Summary
**Product:** Kestrel Goods Growth Data Platform
**Problem:** Growth performance data sits in silos, attribution can't be trusted, and explaining revenue changes is manual and slow ([01_BUSINESS_PROBLEM.md](01_BUSINESS_PROBLEM.md)).
**Solution:** An orchestrated ELT platform that produces governed growth metrics, with AI agents that explain changes in performance and diagnose pipeline failures.

## 2. Users and jobs to be done

| User | Job to be done | Primary surface |
|---|---|---|
| Head of Growth | "Tell me what changed last week and why, in 2 minutes." | Insights Hub → Weekly Brief |
| Performance marketer | "Show me which channels and campaigns are efficient on a blended basis." | Insights Hub → KPI Overview |
| Finance | "Are we on track against target, using a revenue number I trust?" | KPI Overview (target vs actual) |
| Analytics engineer | "Tell me what broke, why, and how to fix it." | Insights Hub → Pipeline Health, Airflow UI |
| Recruiter / reviewer | "Can I run this and understand it in 10 minutes?" | README → `docker compose up` |

## 3. Functional requirements

### FR-1 Ingestion
- **FR-1.1** Each of the 9 sources has its own ingestion task that writes to `raw.<source>___<table>` in ClickHouse ([ADR-022](DECISION_LOG.md#adr-022)).
- **FR-1.2** Every raw row carries dlt's `_dlt_load_id` (load timestamp) and `_dlt_id`; file sources add `_source_file`. Every run is logged to `meta.ingestion_log` ([ADR-022](DECISION_LOG.md#adr-022)).
- **FR-1.3** Incremental sources (Postgres, weather, file drops) load only new or changed data and can be re-run safely (idempotent).
- **FR-1.4** Each ingestion task publishes an Airflow **Asset** when it succeeds.
- **FR-1.5** Optional sources (BigQuery, FRED) fall back to committed snapshots when credentials are absent, and log which mode was used.
- **FR-1.6** Schema changes, such as new or renamed columns, are detected and recorded in `meta.schema_changes`.

### FR-2 Transformation
- **FR-2.1** dbt models follow the `staging → intermediate → marts` layering, with naming conventions in [06_GOVERNANCE.md](06_GOVERNANCE.md).
- **FR-2.2** Staging deduplicates, casts types, standardises currency to USD and timestamps to UTC, and renames columns to snake_case.
- **FR-2.3** Marts expose governed metrics with one definition each ([05_DATA_STRATEGY.md §Metrics](05_DATA_STRATEGY.md#metric-definitions)).
- **FR-2.4** All marts have enforced model contracts.
- **FR-2.5** The dbt DAG runs when its upstream Assets update, not on a fixed cron.

### FR-3 Quality and observability
- **FR-3.1** Source freshness checks run before transformation; a stale critical source blocks the marts that depend on it.
- **FR-3.2** Generic tests: `unique`, `not_null`, `relationships` and `accepted_values` on keys and enums.
- **FR-3.3** dbt unit tests cover attribution logic and the revenue bridge.
- **FR-3.4** dbt run results are persisted to ClickHouse (`meta.dbt_run_results`) for the Pipeline Health page.

### FR-4 Insight Narrator agent
- **FR-4.1** Runs after `mart_kpi_daily` refreshes, with weekly granularity (and on demand).
- **FR-4.2** Deterministic SQL flags week-over-week changes in revenue, sessions, conversion rate, AOV, spend, MER and CAC beyond thresholds (z-score / % change).
- **FR-4.3** The agent decomposes the revenue change into **traffic × conversion × AOV**, then drills into channel → campaign → product category → new vs returning customers, and checks external context (holidays, weather, sentiment).
- **FR-4.4** The agent may only run **read-only SELECT queries against `marts`**, through a whitelisted tool, with row and time limits.
- **FR-4.5** The output is a structured brief (JSON plus rendered Markdown): headline, top 3 drivers with numbers, supporting evidence queries, recommended actions and a confidence level.
- **FR-4.6** Every number in the brief must come from a tool result. The agent stores the queries it used as evidence.
- **FR-4.7** Briefs are persisted to `ai.briefs` and `reports/brief_<week>.md`, and shown in the Insights Hub.

### FR-5 Failure Triage agent
- **FR-5.1** Triggered by Airflow `on_failure_callback` on ingestion and dbt tasks.
- **FR-5.2** Gathers the task log tail, dbt `run_results.json` errors, compiled SQL, recent schema changes and recent git changes to the affected model.
- **FR-5.3** Outputs a category (source schema change / data quality / SQL error / infrastructure / upstream freshness), root-cause hypothesis, suggested fix (code diff where applicable) and severity.
- **FR-5.4** Persisted to `ai.incidents`; shown on Pipeline Health; optional Slack post.
- **FR-5.5** A **chaos script** (`make break-ads-schema`) deliberately breaks a source so the agent can be demonstrated.

### FR-6 Schema Drift Assistant
- **FR-6.1** When `meta.schema_changes` records a change, the assistant proposes an updated staging model and YAML as a patch file in `proposals/`.
- **FR-6.2** It never applies changes automatically.

### FR-7 Insights Hub (Streamlit)
- **FR-7.1** Pages: Weekly Brief, KPI Overview, Pipeline Health, AI Ops.
- **FR-7.2** Reads only from `marts`, `meta` and `ai` schemas, using a read-only user.
- **FR-7.3** Includes a **"Generate brief now"** button. It is disabled with an explanation when no API key is set.
- **FR-7.4** Shows a banner stating whether the app is in live, mock or offline mode.

### FR-8 Run modes

| `AI_MODE` | Behaviour |
|---|---|
| `live` | Calls the configured LLM provider: `LLM_PROVIDER=gemini` (default, needs `GEMINI_API_KEY`) or `anthropic` (needs `ANTHROPIC_API_KEY`) |
| `mock` | Replays recorded responses from `agents/fixtures/`, at no cost; used in CI and development |
| `off` | Agents are skipped; the pipeline runs normally |

The default is `mock` if no key is set, and `live` if a key is present.

## 4. Non-functional requirements

| ID | Requirement | Target |
|---|---|---|
| NFR-1 | Cold start: clone → `docker compose up` → first dashboard | ≤ 10 minutes on an 8 GB laptop |
| NFR-2 | Full pipeline run (ingest + dbt build) | ≤ 5 minutes |
| NFR-3 | Memory footprint of the stack | ≤ 6 GB |
| NFR-4 | Repo size including committed samples | ≤ 50 MB |
| NFR-5 | AI usage per Narrator run | ≤ 50k input tokens, ≤ 4k output tokens, ≤ 10 LLM requests (fits within Gemini free-tier per-minute limits) |
| NFR-6 | AI usage per Triage run | ≤ 15k input tokens, ≤ 3 LLM requests (lightweight model by default) |
| NFR-7 | No secrets in git | Enforced by `.gitignore` and a CI secret scan |
| NFR-8 | Reproducibility | Generators are seeded; same seed gives the same data |

## 5. Acceptance criteria (demo script)
1. Fresh clone, `cp .env.example .env`, `docker compose up -d` → all containers healthy.
2. Airflow UI shows the DAGs. Triggering `bootstrap` loads all 9 sources, runs dbt, and every test passes.
3. Insights Hub shows KPIs and a sample brief (mock mode).
4. Adding a free `GEMINI_API_KEY` (from Google AI Studio) and clicking "Generate brief now" produces a new brief in under 90 seconds, with evidence queries.
5. `make break-ads-schema` followed by triggering ingestion → the dbt test fails → an incident appears on Pipeline Health with the correct root cause ("column `amount_spent` renamed to `spend`").
6. `make simulate-day` → new orders are loaded incrementally → KPIs update.

## 6. Success metrics (for the portfolio)
- A reviewer reaches a running dashboard without asking a question.
- The README explains *why* for each major decision (links to the decision log).
- CI is green; there are tests at every layer.
- The AI features are visibly governed, with evidence, caps, modes and human review.
