# Decision Log

Each entry is a lightweight Architecture Decision Record (ADR). New decisions are appended and never edited in place. To change a decision, add a new ADR that **supersedes** the old one, and mark the old one's status.

**Template**
```
## ADR-NNN · Title
- Date / Status (Proposed · Accepted · Superseded by ADR-XXX)
- Context: the problem and the constraints
- Decision: what we chose
- Alternatives: what else we considered and why we rejected it
- Consequences: the trade-offs we accept
```

## Index

| ADR | Title | Status |
|---|---|---|
| [001](#adr-001) | ClickHouse (OSS, Docker) as warehouse; BigQuery as a source only | Accepted |
| [002](#adr-002) | ELT with immutable raw layer and dbt layering | Accepted |
| [003](#adr-003) | Airflow 3 with Asset-driven scheduling and Cosmos for dbt | Accepted |
| [004](#adr-004) | ClickHouse-native modelling patterns | Accepted |
| [005](#adr-005) | dlt for ingestion | Accepted |
| [006](#adr-006) | Zero-key runnable repo with live upgrades | Accepted |
| [007](#adr-007) | Deliberately small data volumes | Accepted |
| [008](#adr-008) | Laptop-sized footprint | Accepted |
| [009](#adr-009) | Streamlit "Insights Hub" as the surface for AI output | Accepted |
| [010](#adr-010) | Drop Google Trends from core scope | Accepted |
| [011](#adr-011) | Deterministic detection, generative explanation | Accepted |
| [012](#adr-012) | Anthropic SDK tool use at runtime; MCP servers for development | Runtime part amended by 017 |
| [013](#adr-013) | Shift GA4 dates by whole weeks | Superseded by 020 |
| [014](#adr-014) | Govern metrics in contracted marts, not a semantic-layer server | Accepted |
| [015](#adr-015) | AI run modes and cost controls | Model choice amended by 017 |
| [016](#adr-016) | Repo name and local folder | Accepted |
| [017](#adr-017) | Gemini free tier as default LLM, behind a provider-agnostic adapter | Accepted (amends 012, 015) |
| [018](#adr-018) | SeaweedFS replaces MinIO as the S3 landing zone | Accepted |
| [019](#adr-019) | Single-container Airflow (`airflow standalone`) | Accepted (amends 008) |
| [020](#adr-020) | Holiday-season window and progressive daily release | Accepted (supersedes 013) |
| [021](#adr-021) | Shop data derived from GA4 purchases; funnel-events extract | Accepted |
| [022](#adr-022) | Raw layer layout and ingestion conventions (dlt on ClickHouse) | Accepted (amends 002, FR-1.2) |
| [023](#adr-023) | GA4 bulk-loads through ClickHouse's native Parquet reader, not dlt | Accepted (amends 005) |
| [024](#adr-024) | Explicit ingestion tasks in bootstrap, committed seed data, paused schedules | Accepted (amends 019, 020) |

---

<a id="adr-001"></a>
## ADR-001 · ClickHouse (OSS, Docker) as warehouse; BigQuery as a source only
- **Date:** 2026-11-01 · **Status:** Accepted
- **Context:** The portfolio needs a warehouse that reviewers can run without accounts, that stands out from typical Snowflake or BigQuery projects, and that shows OLAP engineering depth. GA4 data realistically lives in BigQuery.
- **Decision:** Use self-hosted **ClickHouse** in Docker as the analytical warehouse. Use **BigQuery** (free sandbox) only as an upstream *source* for the public GA4 dataset.
- **Alternatives:**
  - **Snowflake:** the trial expires and the demo breaks.
  - **BigQuery as the warehouse:** every reviewer would need GCP credentials, and it's very common in portfolios.
  - **DuckDB:** excellent, but embedded, with no server or multi-user story.
  - **ClickHouse Cloud:** a trial again; kept as an optional hosted demo.
- **Consequences:** We must handle ClickHouse specifics ourselves (no UPDATE, merge semantics, dbt adapter maturity). This is a cost, but it is also the skill we're showing. The pattern of extracting from a cloud warehouse into an OLAP warehouse makes a strong interview topic. dbt keeps the SQL portable enough that "it ports to Snowflake" is a credible claim.

<a id="adr-002"></a>
## ADR-002 · ELT with immutable raw layer and dbt layering
- **Date:** 2026-11-01 · **Status:** Accepted
- **Context:** Multiple messy sources; transformations must be testable, versioned and replayable.
- **Decision:** Land data as-is into `raw_*` (append-only, with load metadata). All transformation happens in dbt, through `staging → intermediate → marts`.
- **Alternatives:** Transform during ingestion (ETL in Python). Rejected: the logic would be untested and hidden, and replay would be hard.
- **Consequences:** Raw storage grows (trivial at this scale). Any bug can be fixed and replayed with `--full-refresh`.

<a id="adr-003"></a>
## ADR-003 · Airflow 3 with Asset-driven scheduling and Cosmos for dbt
- **Date:** 2026-11-01 · **Status:** Accepted
- **Context:** Sources arrive on different cadences (hourly database, daily APIs, irregular file drops). A fixed cron for dbt either runs on stale data or wastes runs.
- **Decision:** Airflow 3. Ingestion tasks publish **Assets**, and `dbt_transform` is scheduled on those Assets. dbt runs through **Astronomer Cosmos**, so each model and its tests is an Airflow task.
- **Alternatives:**
  - Cron-scheduled `dbt build` in a BashOperator: one opaque task and poor failure context.
  - Dagster: asset-native and arguably cleaner, but Airflow dominates job descriptions.
- **Consequences:** A more complex DAG graph and Cosmos parsing overhead, mitigated with a pre-compiled manifest (`LoadMode.DBT_MANIFEST`). In return, failures are isolated per model, which gives the triage agent precise context.

<a id="adr-004"></a>
## ADR-004 · ClickHouse-native modelling patterns
- **Date:** 2026-11-01 · **Status:** Accepted
- **Context:** Modelling ClickHouse like a row-store warehouse wastes its strengths and hits its limits (no cheap UPDATE or DELETE, sparse index, merge-time deduplication).
- **Decision:**
  1. `ORDER BY` keys designed around the dominant filters (date first, then low-cardinality dimensions).
  2. `PARTITION BY toYYYYMM()`, monthly not daily, to avoid too many parts.
  3. `ReplacingMergeTree(version)` for mutable entities, with exact reads via `FINAL` or `argMax` in models that need correctness.
  4. `AggregatingMergeTree` for KPI rollups.
  5. `LowCardinality(String)` for dimension-like strings.
  6. Dictionaries for small lookups.
  7. No `Nullable` in sort keys.
  8. dbt incremental strategy chosen per model (`append`, `delete+insert`, `table`).
- **Alternatives:** Generic `MergeTree` everywhere with full-refresh tables. Rejected: it hides the OLAP skill and doesn't scale.
- **Consequences:** Correctness depends on understanding merge semantics. `FINAL` has a query cost, which is fine at this scale and documented as a trade-off. Each pattern is commented in the model config for reviewers.

<a id="adr-005"></a>
## ADR-005 · dlt for ingestion
- **Date:** 2026-11-01 · **Status:** Accepted
- **Context:** Nine sources of six types; we need incremental loading, schema evolution and exactly-once file processing, without running a heavy ingestion platform.
- **Decision:** **dlt**, a Python library running inside Airflow tasks, writing to its ClickHouse destination.
- **Alternatives:**
  - Airbyte: many containers and GBs of RAM, which conflicts with ADR-008.
  - Hand-written loaders: reinventing state, schema inference and retries.
  - Fivetran: paid.
- **Consequences:** We depend on dlt's ClickHouse destination behaviour (table engines it creates, type mapping), which must be verified in Phase 2. Ingestion stays in code, reviewable and testable.

<a id="adr-006"></a>
## ADR-006 · Zero-key runnable repo with live upgrades
- **Date:** 2026-11-01 · **Status:** Accepted
- **Context:** Recruiters won't create GCP projects or buy API credits to look at a portfolio. The owner wants a ready-to-deploy repo: clone, `docker compose up`, optionally add an AI key.
- **Decision:**
  - Every keyed source has a committed fallback: GA4 as a Parquet sample, FRED as a CSV snapshot.
  - Agents default to `mock` mode, with a pre-recorded brief and incident.
  - `.env.example` lists every variable with comments. Only `ANTHROPIC_API_KEY` is needed to unlock live agents. GCP and FRED keys unlock live extraction.
  - The UI shows the current mode.
- **Alternatives:** Require keys. Rejected, because it blocks most reviewers.
- **Consequences:** We maintain fallback assets and two code paths per keyed source. The repo carries about 20–25 MB of samples.

<a id="adr-007"></a>
## ADR-007 · Deliberately small data volumes
- **Date:** 2026-11-01 · **Status:** Accepted
- **Context:** Fast reviewer experience, a small repo, cheap AI testing (the owner wants to conserve usage), and CI must build in minutes.
- **Decision:** About 220k rows in total over 92 days ([05_DATA_STRATEGY §3](05_DATA_STRATEGY.md#3-source-catalogue-and-target-volumes)). Agents only ever see aggregated marts, capped at 500 rows per query.
- **Alternatives:** Millions of rows to "show scale". Rejected: it slows everything and proves little. Scale readiness is shown through engine design (ADR-004), not volume. A generator `SCALE` factor allows larger runs on demand.
- **Consequences:** Performance claims are architectural, not benchmarked. A `SCALE=10` option exists for anyone who wants to stress-test.

<a id="adr-008"></a>
## ADR-008 · Laptop-sized footprint
- **Date:** 2026-11-01 · **Status:** Accepted
- **Context:** The official Airflow Compose file (Celery, Redis, workers, triggerer) plus ClickHouse, MinIO, Postgres and a UI can exceed 8 GB.
- **Decision:**
  - LocalExecutor.
  - One Postgres instance with two databases (`airflow`, `shop`).
  - No triggerer unless needed.
  - Memory limits per container.
  - Streamlit instead of a separate BI server (ADR-009).
- **Alternatives:** CeleryExecutor for "production realism". Rejected, and documented in the production mapping instead.
- **Consequences:** No horizontal task scaling, which isn't needed at this volume. Sharing one Postgres instance between Airflow metadata and the "source system" is a demo shortcut and is explicitly called out.

<a id="adr-009"></a>
## ADR-009 · Streamlit "Insights Hub" as the surface for AI output
- **Date:** 2026-11-01 · **Status:** Accepted
- **Context:** The AI briefs and incident diagnoses need a place where a reviewer can *see* them. Narrative text, evidence tables, charts and incident timelines don't fit well into BI tiles.
- **Decision:** A Streamlit app at `localhost:8501` with four pages: Weekly Brief, KPI Overview, Pipeline Health, AI Ops. Briefs are also written to `reports/*.md`, with an optional Slack webhook.
- **Alternatives:**
  - Metabase or Superset: strong charts, weak for narrative and agent output, and another heavy container.
  - Slack only: needs a workspace, invisible to reviewers.
  - Airflow logs: not a product surface.
- **Consequences:** Charts are coded (Plotly) rather than drag-and-drop. It's one Python app the owner fully controls, and it's easy to screenshot for the README.

<a id="adr-010"></a>
## ADR-010 · Drop Google Trends from core scope
- **Date:** 2026-11-01 · **Status:** Accepted
- **Context:** Google Trends has been an appealing demand signal, but the unofficial `pytrends` breaks often and official API access is limited.
- **Decision:** Exclude it from core sources. Weather, holidays and FRED sentiment cover external context.
- **Alternatives:** Use pytrends. Rejected because it would make the demo flaky.
- **Consequences:** Less "search demand" context. Can be added later as an optional source with a snapshot fallback.

<a id="adr-011"></a>
## ADR-011 · Deterministic detection, generative explanation
- **Date:** 2026-11-01 · **Status:** Accepted
- **Context:** LLMs are good at investigating and explaining, but unreliable at deciding whether a change is significant, and they can invent numbers.
- **Decision:** SQL (z-scores and % change thresholds) decides what is anomalous. The agent investigates and explains, using only tool results from governed marts. The output schema requires evidence for each claim, and a verifier re-runs the cited queries to check the numbers.
- **Alternatives:** "Ask the LLM to analyse the dashboard". Rejected: it isn't auditable.
- **Consequences:** More engineering (detector, verifier, schema). The result is trustworthy, auditable AI output, which is the exact point to make to recruiters.

<a id="adr-012"></a>
## ADR-012 · Anthropic SDK tool use at runtime; MCP servers for development
- **Date:** 2026-11-01 · **Status:** Accepted
- **Context:** Runtime agents need tight control over tools, caps, logging and mock replay. Development benefits from interactive warehouse and dbt access.
- **Decision:**
  - Runtime agents use the **Anthropic Python SDK** directly (tool use, structured outputs, prompt caching) with a small in-house tool set.
  - For development, `.mcp.json` configures the **ClickHouse MCP server** and **dbt MCP server** for Claude Code (the "Dev Accelerator" workflow).
- **Alternatives:**
  - LangChain / LangGraph: abstraction not needed for 3 focused agents.
  - MCP at runtime: an extra process per run, with harder caps and mock replay.
- **Consequences:** We own the agent loop code (about 200 lines). Both skills are shown: building production agents, and using AI tooling to deliver faster.

<a id="adr-013"></a>
## ADR-013 · Shift GA4 dates by whole weeks
- **Date:** 2026-11-01 · **Status:** Superseded by [ADR-020](#adr-020)
- **Context:** The GA4 sample covers 2020-11-01 → 2021-01-31, but the other data should look current.
- **Decision:** The `ga4_date_shift` macro shifts by `N × 7` days so that the window ends near `SIM_ANCHOR_DATE`. Weekdays are preserved, and the season is roughly preserved (Nov → Jan).
- **Alternatives:** Leave dates in 2020 (synthetic data would also have to be 2020, which looks stale). Shift by an exact year count (weekday misalignment).
- **Consequences:** Holidays may fall a few days off from GA4 behaviour. This is documented in the limitations.

<a id="adr-014"></a>
## ADR-014 · Govern metrics in contracted marts, not a semantic-layer server
- **Date:** 2026-11-01 · **Status:** Accepted
- **Context:** The initial plan mentioned the dbt Semantic Layer. MetricFlow doesn't support ClickHouse as a query engine.
- **Decision:** Compute each metric once in contracted marts (`mart_kpi_daily`, etc.). Document definitions in `_metrics.yml` and in [05_DATA_STRATEGY §7](05_DATA_STRATEGY.md#metric-definitions). The Hub and the agents read only these marts.
- **Alternatives:** Run MetricFlow on another engine (adds complexity); Cube.dev (another service).
- **Consequences:** No dynamic metric querying across arbitrary dimensions; marts must cover the needed grains. There is still one definition per metric, which was the actual goal.

<a id="adr-015"></a>
## ADR-015 · AI run modes and cost controls
- **Date:** 2026-11-01 · **Status:** Accepted
- **Context:** The owner wants to avoid burning usage while testing. Reviewers may or may not add a key. A **Claude Pro subscription does not include Anthropic API credits**: the agents need a separate pay-as-you-go API key from the Anthropic Console.
- **Decision:**
  - `AI_MODE` = `live` | `mock` | `off`.
  - The default is `mock` with no key, and `live` with a key.
  - Caps are set through `AI_MAX_INPUT_TOKENS`, `AI_MAX_OUTPUT_TOKENS` and `AI_MAX_TOOL_CALLS`.
  - Prompt caching for system prompts and metric definitions.
  - Haiku for classification, Sonnet for reasoning; model IDs set through `.env`.
  - Development and CI use mock fixtures. Live calls are made only to record fixtures and for final demos.
- **Consequences:** Fixtures must be refreshed when prompts change. Live testing during development is a deliberate, minimal act.

<a id="adr-016"></a>
## ADR-016 · Repo name and local folder
- **Date:** 2026-11-01 · **Status:** Accepted
- **Context:** The naming convention is `dbt-airflow-<warehouse>-<usecase>`. The local working folder is `dbt-airflow-orchestration`.
- **Decision:** The GitHub repo will be **`dbt-airflow-clickhouse-dtc-growth`**. The local folder name doesn't matter to git. The push happens in Phase 6, after the owner confirms.
- **Consequences:** None functional. The README and Compose project name use `dtc-growth`.

<a id="adr-017"></a>
## ADR-017 · Gemini free tier as default LLM, behind a provider-agnostic adapter
- **Date:** 2026-11-01 · **Status:** Accepted. Amends the runtime SDK choice in ADR-012 and the model choice in ADR-015.
- **Context:** The owner wants testing and the published repo to cost nothing. The Anthropic API needs paid credits, which a Claude Pro plan doesn't include. Gemini's API has a free tier, with a key available from Google AI Studio in minutes. That also lowers the barrier for reviewers.
- **Decision:**
  - `LLM_PROVIDER=gemini` is the default, using the Google GenAI SDK. `anthropic` remains a supported option.
  - `agents/core/llm.py` exposes one interface: `chat(messages, tools, response_schema)`. The agent loop, tools, caps, mock replay, usage logging and evals are provider-independent.
  - Model IDs come from `.env` (`LLM_MODEL_REASONING`, `LLM_MODEL_LIGHT`). Defaults are pinned to free-tier Flash / Flash-Lite models when Phase 5 is built, after checking the current free list in AI Studio, because free-tier models changed during 2026.
  - Runs are designed for free-tier quotas: ≤ 10 requests per narrator run, exponential backoff on HTTP 429, no parallel calls.
  - Dev tooling (Claude Code with the dbt and ClickHouse MCP servers, from ADR-012) is unchanged. It is how the project is *built*, not a runtime dependency.
- **Alternatives:**
  - Anthropic-only: paid credits for the owner and reviewers.
  - Local LLM (Ollama): no key needed, but several GB more RAM, which conflicts with ADR-008, and weaker tool use.
  - LangChain for abstraction: a heavy dependency for a ~60-line adapter.
- **Consequences:**
  - Free-tier quotas and model availability can change. Mitigated by configurable IDs, mock mode and the Anthropic fallback.
  - Google may use free-tier prompts to improve its products. Acceptable because agents see only synthetic, aggregated, PII-free data; stated in the README.
  - Prompt caching is not relied on for cost control.
  - Showing provider-agnostic agent design is a portfolio strength in its own right.


<a id="adr-018"></a>
## ADR-018 · SeaweedFS replaces MinIO as the S3 landing zone
- **Date:** 2026-11-01 · **Status:** Accepted
- **Context:** During Phase 1 the `minio/minio` repository no longer existed on Docker Hub. MinIO stopped distributing community images, so a fresh clone would fail to pull.
- **Decision:** Use **SeaweedFS 4.48** (`weed server -s3`) as the S3-compatible landing zone. Credentials come from `.env` through a generated identity config. The filer UI at `:8888` replaces the MinIO console.
- **Alternatives:**
  - An old pinned MinIO image from another registry: unmaintained, and a reviewer may spot it.
  - RustFS: promising, but 1.0 only recently.
  - A local bind-mounted folder: loses the "same code as AWS S3" property.
- **Consequences:** Application code is unchanged, because s3fs and dlt only see an S3 endpoint. One container, about 100 MB of RAM.

<a id="adr-019"></a>
## ADR-019 · Single-container Airflow (`airflow standalone`)
- **Date:** 2026-11-01 · **Status:** Accepted. Amends the container list in ADR-008.
- **Context:** The development machine has 7.7 GB of RAM, and Docker Desktop on WSL2 gets about half of it by default. Airflow 3 split into api-server, scheduler, dag-processor and triggerer containers loads the Airflow codebase four times (about 0.5 GB each).
- **Decision:** One `airflow` container running `airflow standalone`, which starts all components as processes. It uses the LocalExecutor with Postgres metadata (not SQLite) and runs under a 2.5 GB memory limit. Login is disabled for the local demo (`SIMPLE_AUTH_MANAGER_ALL_ADMINS`).
- **Alternatives:** The split-service layout from the official Compose file. It is closer to production, but about 1 GB heavier.
- **Consequences:** No independent restarts or scaling of components. The production mapping (04_ARCHITECTURE §10) explains the split layout. The total stack is about 4 GB at peak.

<a id="adr-020"></a>
## ADR-020 · Holiday-season window and progressive daily release
- **Date:** 2026-11-01 · **Status:** Accepted. Supersedes ADR-013.
- **Context:** ADR-013 proposed shifting GA4 so the window ended near "today". That would place Nov–Jan web behaviour in Aug–Oct and destroy the seasonality. Separately, a static dataset can't show incremental loading.
- **Decision:**
  - Shift GA4 by exactly **261 weeks**. The window becomes **2025-11-02 → 2026-02-01**, the latest complete holiday season, with weekdays and Black Friday aligned.
  - Generate the whole window, then **release** it into the source systems by date.
  - The bootstrap releases through 2026-01-18. Each `simulator_advance_day` releases one more day: new orders, status updates on older orders (an `updated_at` bump), and new files in S3.
  - The simulated clock lives in `s3://landing/_control/sim_clock.json`.
- **Alternatives:**
  - A live random generator per day: no GA4 to match, so web and orders would disagree.
  - A fixed static load: no incremental story.
- **Consequences:** Data looks about 10 months old relative to today. That's framed as a "last-peak retrospective, preparing for the 2026 peak". The simulation can run 14 days forward.

<a id="adr-021"></a>
## ADR-021 · Shop data derived from GA4 purchases; funnel-events extract
- **Date:** 2026-11-01 · **Status:** Accepted
- **Context:** If orders were generated independently of GA4, conversion rate (orders ÷ sessions) would be meaningless. ~9k synthetic orders against a 3% GA4 user sample would give a conversion rate of about 75%.
- **Decision:**
  - The GA4 extract keeps **all users but only funnel events** (session_start, first_visit, view_item, add_to_cart, begin_checkout, add_shipping_info, add_payment_info, purchase), with `event_params` and `items` trimmed to the needed keys. User sampling applies only if the file would exceed about 25 MB.
  - Every GA4 purchase becomes one shop order, with the same session ID, items, timestamp (shifted), and geo.
  - About 15% extra "untracked" orders model consent and ad-blocker loss.
  - The product catalog is the GA4 item catalog, with brand words stripped. The store is fictional, not a copy of Google's.
  - Backend UTMs map GA4 `cpc` traffic to Google campaigns, and part of the obfuscated `<Other>` / `(data deleted)` traffic to Meta.
- **Alternatives:**
  - An independent synthetic shop: incoherent funnel.
  - Synthetic GA4 as well: loses the real cloud-warehouse source.
- **Consequences:** Order volume is set by real GA4 purchases (~5–6k plus 15%). Meta attribution relies partly on a documented re-labelling of obfuscated sources. A synthetic GA4 fixture (`generators/ga4_fixture.py`) exists for tests and CI only.


<a id="adr-022"></a>
## ADR-022 · Raw layer layout and ingestion conventions (dlt on ClickHouse)
- **Date:** 2026-11-01 · **Status:** Accepted. Amends ADR-002 and PRD FR-1.2.
- **Context:** ADR-005 left dlt's ClickHouse behaviour to be verified in Phase 2. Reading the destination source showed that dlt writes every table of a pipeline into **one database** and puts the dataset name in the table name (`<dataset>___<table>`), and that it can emit `ReplacingMergeTree` with a version column plus custom `ORDER BY`.
- **Decision:**
  1. **Layout:** database `raw`, tables `raw.<source>___<table>` (for example `raw.shop___orders`, `raw.meta_ads___meta_ads_daily`). dbt sources point at these. The `raw_<source>` names in the earlier docs are logical names for the same data.
  2. **Mutable shop tables** land as `ReplacingMergeTree(updated_at)` ordered by primary key, through dlt's ClickHouse adapter. Dedup happens in ClickHouse; exact reads use `FINAL` or `argMax` downstream (ADR-004).
  3. **CSVs stay text** (dlt's timestamp auto-detection is turned off). Typing is dbt staging's job, so raw is genuinely "as delivered" and a changed format cannot silently change a column type.
  4. **GA4 is the exception to dlt**: see [ADR-023](#adr-023). Its nested fields keep their native ClickHouse types.
  5. **Budget workbook** is flattened to one row per channel × month × metric during ingestion, because a spreadsheet with merged headers is a layout, not a table. Cell values are untouched.
  6. **Batch metadata:** dlt's `_dlt_load_id` (a load timestamp) and `_dlt_id` replace the planned `_batch_id` / `_loaded_at` columns. File sources add `_source_file`. Each run also writes `meta.ingestion_log`, including the load id.
  7. **Asset events fire only when rows were loaded.** Runs that load nothing skip their task, so dbt does not rebuild for no reason.
  8. **One dlt pipeline per source family** (meta_ads, google_ads, email, budget, ...), so one broken export cannot block the rest, and incremental state is independent.
  9. **Schema changes** come from dlt's per-load `schema_update` and go to `meta.schema_changes`. dlt never drops columns, so a rename shows up as a new column (the `amount_spent` → `spend` chaos case) while the old column goes null.
- **Alternatives:** One ClickHouse database per source (needs a custom destination or post-load moves); letting dlt infer CSV types (silent type drift); default unnesting of GA4 (millions of child rows).
- **Consequences:** dbt staging does more typing and JSON work; raw tables are not queried directly by anyone else. The engine settings rely on dlt hints and must be verified against a running ClickHouse (planned for the Phase 2 smoke test).


<a id="adr-023"></a>
## ADR-023 · GA4 bulk-loads through ClickHouse's native Parquet reader, not dlt
- **Date:** 2026-11-01 · **Status:** Accepted. Amends ADR-005 and ADR-022 item 4.
- **Context:** GA4 is 1.1M events of nested structs. Measured on the demo container:
  - dlt with Python dict rows: over 30 minutes and no finish (schema inference per row).
  - dlt with Arrow tables: still slow, because nested columns had to be JSON-encoded in Python (~15 min estimated) and the Parquet file alone takes ~2 min to decode in pyarrow on this machine.
  - BigQuery REST paging for the live path: hours (rows arrive nested over JSON).
- **Decision:**
  1. The Parquet bytes are POSTed to ClickHouse's HTTP interface and read server-side with `INSERT ... SELECT ... FROM input(...) FORMAT Parquet`, filtered to the days released so far. Result: **978,234 rows in 76 s**.
  2. The table is created by the loader from the file's schema. Nested fields keep native types (`Array(Tuple(...))`), so dbt staging uses array functions, not JSON parsing. Layout: `PARTITION BY` month, `ORDER BY (event_date, event_name, user_pseudo_id, event_timestamp)`, plus `_loaded_at` and `_source_file`.
  3. The table is its own cursor (newest `event_date` loaded). A failed run deletes its own rows, so partially loaded days can never be skipped by the next run.
  4. Live BigQuery mode uses the Storage Read API (needs the *BigQuery Read Session User* role) and feeds the same insert path. `GA4_SOURCE=auto|sample|live` selects the source; `auto` goes live only when credentials exist.
  5. The committed sample was rewritten with 50k-row row groups and sorted by date. ClickHouse decodes it in pieces within its 1 GB default query memory cap, and the file shrank from 40.7 to 33.3 MB.
- **Alternatives:** keep dlt and accept 30+ minutes (fails NFR-2 and the reviewer experience); sample 10% of users (thinner analysis); give the container more RAM (not available on an 8 GB laptop).
- **Consequences:** One source bypasses dlt's state and schema-evolution tracking, so GA4 schema changes are not logged to `meta.schema_changes` (GA4's export schema is stable by contract). The loader owns its DDL. It remains an honest talking point: choose the tool for the data shape, and measure before deciding.


<a id="adr-024"></a>
## ADR-024 · Explicit ingestion tasks in bootstrap, committed seed data, paused schedules
- **Date:** 2026-11-02 · **Status:** Accepted. Amends ADR-019 and ADR-020.
- **Context:** The first clean-stack `bootstrap` run on the 7.7 GB development laptop took 45 minutes and failed:
  - generating the data inside the container took 15 minutes;
  - `bootstrap` triggered four other DAGs, and the hourly and 15-minute schedules fired on top of it at startup;
  - Windows had 0.2 GB of free RAM (3.9 GB in memory compression) and 100% CPU. A shop load ran 614 s with no error and then went to retry, which fits a missed task heartbeat.
- **Decision:**
  1. **Seed data is committed.** `data/generated/` (16 MB, deterministic from `SEED`) ships in the repo, so a fresh clone skips generation. `make regenerate` rebuilds it byte for byte.
  2. **`bootstrap` and `simulator_advance_day` ingest through plain tasks**, one per source (`dags/_ingest.py`), at most two at a time. They no longer trigger other DAGs. The scheduled `ingest_*` DAGs call the same functions.
  3. **The scheduled `ingest_*` DAGs start paused.** Unpause them to run on a schedule. `bootstrap` and the simulator are unpaused.
  4. **Tighter limits:** Airflow 2 GB (was 2.5), ClickHouse 1.25 GB (was 1.5), a 20-minute task heartbeat timeout.
- **Alternatives:** keep generating at first run (15 minutes of dead time for every reviewer); leave schedules unpaused (they compete with the first load on small machines).
- **Consequences:** The repo grows by about 16 MB before compression (CSV and JSONL compress well in git). Reviewers must unpause the schedules if they want hourly loads, which the README will say. The full-stack footprint on a laptop is still the main risk (R1); the docs recommend 16 GB, with 8 GB as a tight minimum.


<a id="adr-025"></a>
## ADR-025 · dbt feature choices on ClickHouse, Cosmos wiring, and an Airflow CPU cap
- **Date:** 2026-11-02 · **Status:** Accepted.
- **Context:** Before building marts we tested what dbt-clickhouse 1.10.3 supports, and wired dbt into Airflow. Separately, an idle Airflow container was using about 280% CPU (scheduler, dag-processor and triggerer re-parsing DAG files over the Windows bind mount), which starved ClickHouse: a 15-second query ran past 120 seconds.
- **Findings (tested):**
  - **Model contracts** work on tables and are enforced: a `Float64` contract against a `Decimal(38, 2)` column failed at compile time with a clear diff. Contracts will go on the marts.
  - **Unit tests** work (dbt 1.11 core feature). The revenue rule has one.
  - **Incremental `delete_insert`** works with `unique_key`; a second run is a no-op in under a second. Used where a mart is large and append-mostly.
- **Decision:**
  1. Marts use **contracts**; business rules (revenue status, bridge maths, attribution) get **unit tests**.
  2. **Cosmos renders the dbt project as Airflow tasks** (`dags/dbt_transform.py`): one task per seed, model and its tests (`TestBehavior.AFTER_EACH`), so a failing test stops its dependants. It uses Cosmos' own parser (`LoadMode.CUSTOM`, 1.4 s) instead of `dbt ls` at parse time.
  3. `dbt_transform` is **scheduled by Assets with OR logic** over the seven daily raw sources, so it runs only when ingestion loaded new rows. `max_active_runs=1` coalesces bursts.
  4. **Airflow is capped at 1.5 CPUs** and re-parses DAG files every 10 to 15 minutes. Idle CPU fell from about 280% to about 13%, and a staging build dropped from 2 to 7 minutes to 2.
  5. `make dbt ARGS="build ..."` runs dbt in a throwaway container with no Airflow, for fast iteration.
- **Tried and dropped:** Cosmos `ExecutionMode.WATCHER` (one `dbt build`, per-model tasks). Under `airflow dags test` it deadlocks (serial execution), and under the real scheduler its producer task was skipped and the model tasks kept retrying. Not pursued further.
- **Known cost:** per-model tasks start `dbt` 38 times. On the 7.7 GB dev laptop that is about a minute each (43 minutes serially); on normal hardware it is seconds. Mitigation applied: tests now run once, in a single final task (`TestBehavior.AFTER_ALL`), so the DAG has about 20 tasks instead of 38. Trade-off: a failing test no longer stops its downstream models; it fails the run at the end.
- **Alternatives:** `dbt ls` at parse time (slow on small hosts); one task per dbt invocation (loses per-model retries and lineage in the UI); a clock schedule for dbt (rebuilds when nothing changed).
- **Consequences:** Cosmos' custom parser understands a subset of dbt (no package-heavy projects), which is fine here. A DAG that rebuilds on every asset event may run during a long bootstrap; `max_active_tasks=2` keeps it light.


<a id="adr-026"></a>
## ADR-026 · Marts conventions, run results via a dbt hook instead of Elementary, hub and docs services
- **Date:** 2026-11-02 · **Status:** Accepted. Replaces the Elementary item in the Phase 4 plan.
- **Context:** Phase 4 needed typed, stable marts for the dashboards and the AI agents, a record of dbt runs for the Pipeline Health page and the triage agent, and a browsable model catalogue. The dev laptop has 7.7 GB of RAM.
- **Decision:**
  1. **Contracts on the four marts that other systems read** (`fct_orders`, `mart_channel_performance`, `mart_kpi_daily`, `mart_revenue_bridge`). Money is `Decimal(18, 2)`, counts `UInt64`, ratios `Float64`, flags `Bool`. Before this, money came out as `Decimal(38, 2)`, `Decimal(18, 2)` or `Float64` depending on the arithmetic, so the casts are explicit in SQL.
  2. **Sort keys are never nullable.** dlt raw columns and left-join outputs are often `Nullable`; marts wrap key columns in `ifNull` / `assumeNotNull`, backed by `not_null` tests upstream.
  3. **Unit tests on the business rules:** revenue status rules, attribution order (order UTM → GA4 first touch → default) and the revenue bridge (effects add up to the change).
  4. **dbt run results are written by an `on-run-end` hook** (`macros/log_run_results.sql`) to `meta.dbt_run_results`: one row per model, seed and test, with status, timing, failures and message.
  5. **Insights Hub** gets KPI Overview and Pipeline Health pages, reading `marts.*` and `meta.*` as `hub_reader` only. A headless smoke test (`insights_hub/tests/test_pages.py`, Streamlit AppTest) runs every page against live data.
  6. **dbt docs** is its own small service on :8081 (0.5 CPU, 512 MB), regenerated hourly so the catalogue fills in after the first dbt run.
- **Alternatives:** Elementary. It adds a package (network at build time), about 30 extra models and their run time, and its own report UI. On this hardware that cost is not justified for what the hub needs, which is the run results table above. It stays a backlog option.
- **Consequences:** No anomaly-detection tests out of the box (Elementary's main extra). Volume and freshness anomalies are the AI drift agent's job in Phase 5. The hook adds one INSERT per dbt invocation.


<a id="adr-027"></a>
## ADR-027 · Insights Hub visual theme and the Revenue & Growth Dashboard
- **Date:** 2026-11-02 · **Status:** Accepted. Renames the "KPI Overview" page from ADR-009 and ADR-026; the content stays.
- **Context:** The hub used Streamlit's default theme (red accent), four unrelated hues for channels, emoji status icons and plain `st.metric` rows. The owner supplied a reference dashboard: navy and light-blue palette, white cards, summary blocks with an icon disc.
- **Decision:**
  1. **One navy ramp** (`#0B3A75`, `#2F6DB5`, `#7FA8DA`, `#BBD3EE`) on a pale blue-grey page with white cards. Channels keep a fixed step of the ramp on every page. The theme lives in `insights_hub/.streamlit/config.toml`, mounted at `/app/.streamlit`; the shared CSS, summary blocks, cards and Plotly template live in `insights_hub/ui.py`.
  2. **KPI Overview becomes the Revenue & Growth Dashboard** (`pages/1_Growth_Dashboard.py`): four summary blocks (net revenue, orders, AOV, blended ROAS, each vs the prior period), weekly revenue by channel, channel mix, weekly orders, paid ROAS, top 5 countries, and a strip of secondary figures (customers, repeat orders, CAC, conversion, refund rate, gross margin). The channel table, revenue bridge, targets and cohorts follow unchanged. Order-level figures read `fct_orders` joined to `dim_customers` (about 6k rows).
  3. **Weekly charts show complete Monday-to-Sunday weeks only**, so a part week does not read as a drop.
  4. **`app.py` is a router** (`st.navigation`) so the sidebar says Home instead of "app"; the home page moved to `home.py`.
  5. **Status is text, coloured by state** in tables; icons are lucide images (Streamlit's HTML sanitiser strips inline SVG).
  6. **The shared ClickHouse client runs without a server session** (`autogenerate_session_id=False`). With a session, two browser tabs loading at once failed with "concurrent queries within the same session".
- **Alternatives:** a custom component or a JS front end (more to maintain for a portfolio UI); the reference's monthly bars (the data spans under three months, so weekly bars say more).
- **Consequences:** The Figtree font loads from Google Fonts; offline it falls back to the system sans. Recreate the hub container once (`docker compose up -d insights-hub`) to pick up the theme mount.

<a id="adr-028"></a>
## ADR-028 · Insight Narrator v1: one evidence pack, one model call, verified output
- **Date:** 2026-11-12 · **Status:** Accepted. Amends the narrator design in 04_ARCHITECTURE §7 (drill-down loop) and ADR-015 (fixtures).
- **Context:** The architecture described an agent that loops over tool calls to drill down. On the Gemini free tier (ADR-017) that costs up to 10 requests per run, is slow, and is harder to verify. The marts already hold what "why did revenue move?" needs (revenue bridge, channel performance, daily KPIs, GA4 vs shop orders).
- **Decision:**
  1. **Detection is deterministic.** `agents/narrator/detect.py` runs five fixed, reviewed queries for the latest complete week and the week before (E1 to E5) and derives findings in Python (channel moves, conversion shift, spend without traffic, ROAS drop, shop orders vs GA4 purchases, weak day). No number is computed by the model.
  2. **One structured model call** explains the evidence in plain English. Each driver must cite evidence ids.
  3. **Verification before display** (`brief.py`): a driver is dropped if it cites no real evidence or quotes a dollar amount or percentage that is not in the evidence. Drops are shown on the page, not hidden.
  4. **Mock mode is a rule-based explainer** (`mock.py`) that returns the same JSON schema, so the zero-key path (ADR-006) shows a real, data-grounded brief. Live mode replaces only the explanation step. Recorded fixtures are deferred.
  5. **Governed access:** reads marts as `agent_reader`, writes `ai.briefs` and `ai.agent_runs` as `ai_writer`. The SQL guard (`core/tools.py`) allows SELECT on `marts.*` only, on top of the database profile limits.
  6. The DAG `ai_insight_narrator` runs Mondays 06:00 UTC (paused on creation, like the other schedules, ADR-024) or on demand from the Hub. It skips when a brief for that week already exists.
- **Alternatives:** the full tool-calling drill-down loop (more flexible, more quota, harder to verify); passing raw tables to the model (cost, hallucination risk).
- **Consequences:** The brief can only discuss what the five evidence queries cover. Adding a new kind of finding means adding a detector, which is deliberate. The drill-down loop can be added later on top of the same guard and verifier. Live output quality is untested until a model is chosen in `LLM_MODEL_REASONING`.
