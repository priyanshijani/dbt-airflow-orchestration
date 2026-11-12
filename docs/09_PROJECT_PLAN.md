# 09 · Project Plan

Status legend: ✅ done · 🔄 in progress · ⬜ not started · ⏸ blocked

## Phase 0: Project definition ✅
| Task | Status |
|---|---|
| Choose use case, warehouse and architecture | ✅ |
| Project context docs (00–09) | ✅ |
| Decision log seeded (ADR-001 → ADR-016) | ✅ |
| `CLAUDE.md` working agreement | ✅ |

## Phase 1: Foundations 🔄
**Goal:** `docker compose up` gives a healthy stack, with synthetic data generated.
| Task | Status |
|---|---|
| Repo skeleton, `.gitignore`, `.gitattributes`, `Makefile`, `.env.example` | ✅ |
| Custom Airflow image (Airflow 3.3.2 + Cosmos 1.15.1 + dlt 1.31.0 + dbt 1.11 venv); dependency set resolved against Airflow constraints | ✅ |
| `docker-compose.yml`: postgres (airflow + shop db), clickhouse, seaweedfs, airflow (standalone), insights-hub stub | ✅ |
| ClickHouse init: databases, users, grants, read-only profiles with row and time limits | ✅ |
| Postgres init: `airflow` and `shop` databases, shop OLTP schema | ✅ |
| Synthetic generators: shop (from GA4), ads CSVs, email JSONL, budget XLSX, 5 planted stories; seeded and verified deterministic | ✅ (tested on the GA4 fixture) |
| Release / simulator CLI (`generators.release`): Postgres upserts + S3 file delivery by simulated date | ✅ (written; needs the running stack to test) |
| `smoke_test` DAG | ✅ (written) |
| GA4 sample extract → committed Parquet | ⏸ needs GCP sandbox credentials |
| FRED snapshot → committed CSV | ⏸ needs FRED API key |
| Smoke test on the running stack: containers healthy, release seeds Postgres and S3, `smoke_test` DAG green | ⏸ needs Docker Desktop installed |

## Phase 2: Ingestion ✅
**Goal:** all 9 sources land in `raw` with Assets published.
| Task | Status |
|---|---|
| Verify dlt's ClickHouse behaviour; record the raw layout (ADR-022) | ✅ |
| dlt pipeline: Postgres incremental, ReplacingMergeTree per table (`pipelines/shop.py`) | ✅ tested: 5 tables, orders match Postgres exactly |
| dlt pipelines: S3 file drops: Meta, Google, email, budget (`pipelines/files.py`) | ✅ tested |
| dlt pipelines: REST APIs: holidays, weather, FRED with snapshot fallback (`pipelines/apis.py`) | ✅ tested (weather 390 = 5 cities × 78 days) |
| GA4 loader: BigQuery (live, 8 min) or committed Parquet (sample, 76 s) via ClickHouse's native Parquet reader, ADR-023 | ✅ tested: 978,234 rows both ways |
| Schema-change capture → `meta.schema_changes`; run log → `meta.ingestion_log` | ✅ tested |
| Ingestion DAGs with Assets, retries, skip-on-no-new-data | ✅ parse cleanly; loads verified via DAG (shop, email, budget) and directly (rest) |
| `bootstrap` and `simulator_advance_day` DAGs | 🔄 generate and release proven; full green run from a clean stack still to do |
| Run everything on the live stack; fix what breaks; confirm table engines in ClickHouse | ✅ all 9 sources in `raw`, ~1.04M rows, ReplacingMergeTree confirmed |
| Clean-stack run: `make reset`, `docker compose up`, `bootstrap` end to end in one go | ✅ green, no retries (28 min on a 7.7 GB laptop; attempt 1 failed after 45 min, fixed by ADR-024) |
| Simulator test: advance a day, see new rows and duplicate order versions collapse under FINAL | ✅ +22 orders, +59 status versions collapsed by FINAL, GA4/ads/weather advanced one day |

## Phase 3: dbt staging and intermediate ✅
| Task | Status |
|---|---|
| dbt project scaffold, profile via env vars, sources with freshness and owners | ✅ |
| Macros: `ga4_date`, `ga4_timestamp`, `ga4_param`; `generate_schema_name` (layer = ClickHouse database) | ✅ |
| Seeds: `fx_rates`, `campaign_mapping`, `budget_channel_mapping` | ✅ |
| Staging models for all 9 sources (14 models: dedup, typing, USD, UTC, PII hash) | ✅ 55/55 build and tests pass |
| Spike: dbt-clickhouse support for contracts, unit tests, incremental strategies | ✅ all three work (ADR-025) |
| Intermediate: sessions, channel mapping, attribution, order revenue rules | ✅ `int_orders__revenue`, `int_ga4__sessions`, `int_orders__attributed`; 11/11 pass |
| Singular tests (GA4 vs shop reconciliation within tolerance) | ✅ gap 1.8% vs 5% limit (GA4 excludes tax and shipping) |
| Cosmos DAG `dbt_transform`, Asset-triggered | ✅ 38 tasks pass; 43 min on the dev laptop (about 1 min of dbt startup per task). Watcher mode tried and dropped (ADR-025) |

## Phase 4: Marts and Insights Hub ✅
| Task | Status |
|---|---|
| Full project build | ✅ 104/104 (4 seeds, 30 models, 66 tests, 3 unit tests) in 1 min 47 s |
| Core dimensions and facts with ClickHouse engines (ADR-004) | ✅ dim_channel, dim_date, dim_products, dim_customers, fct_orders, fct_sessions, fct_marketing_spend |
| KPI marts: kpi_daily (+ AggregatingMergeTree rollup), channel performance, cohorts, revenue bridge, target tracking | ✅ 34/34 build, tests and bridge unit test pass; revenue reconciles across fct_orders, kpi_daily and the rollup ($326,224) |
| Contracts on marts, unit tests (bridge, attribution) | ✅ 4 contracted marts; 3 unit tests (revenue rules, attribution, bridge) |
| Run results → `meta.dbt_run_results`; Elementary | ✅ on-run-end hook; Elementary dropped (ADR-026) |
| Insights Hub: KPI Overview and Pipeline Health pages | ✅ both pages + home; headless smoke test passes on live data |
| Insights Hub visual pass: navy theme, summary blocks, KPI Overview → Revenue & Growth Dashboard (ADR-027) | ✅ all pages restyled; smoke test passes; checked in a browser at 1440 px |
| dbt docs service | ✅ :8081, regenerated hourly |

## Phase 5: AI agents ⬜
**Keys needed: `GEMINI_API_KEY`** (free, Google AI Studio; requested at the start of this phase).
| Task | Status |
|---|---|
| `agents/core`: LLM wrapper (modes, caps, cost log), safe SQL tool | ⬜ |
| Insight Narrator: detection SQL → drill-down loop → structured brief → verification → render | ⬜ |
| Failure Triage: `on_failure_callback`, context collector, classify, diagnose | ⬜ |
| Schema Drift Assistant → `proposals/` | ⬜ |
| Mock fixtures recorded from one live run each | ⬜ |
| Evals for planted stories and chaos scenarios | ⬜ |
| Insights Hub: Weekly Brief and AI Ops pages, "Generate now" button | ⬜ |
| `make break-ads-schema` chaos demo | ⬜ |
| `.mcp.json` + Dev Accelerator documentation | ⬜ |

## Phase 6: Polish and ship ⬜
| Task | Status |
|---|---|
| GitHub Actions CI (lint, DAG tests, dbt build, agent evals in mock mode, gitleaks) | ⬜ |
| README: story, architecture diagram, quickstart, screenshots/GIF, decision highlights | ⬜ |
| Fresh-clone test on a clean machine (NFR-1) | ⬜ |
| Create GitHub repo `dbt-airflow-clickhouse-dtc-growth` and push | ⬜ (confirm with owner first) |
| Portfolio write-up (why, decisions, AI layer) | ⬜ |

## Backlog / extensions (out of current scope)
- Marketing mix modelling (Robyn or PyMC-Marketing) on the marts
- AI-search referral tracking (use case #2) as a module
- Reverse ETL of audience segments
- ClickHouse Cloud deployment for a live hosted demo
