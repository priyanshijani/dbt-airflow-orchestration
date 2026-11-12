# CLAUDE.md: working agreement for this repo

## What this is
`dbt-airflow-clickhouse-dtc-growth` is a portfolio project. It ingests 9 sources of 6 types (BigQuery GA4, Postgres, CSV/JSON/XLSX file drops on S3 (SeaweedFS), and REST APIs) into ClickHouse with dlt. It models them with dbt, orchestrates with Airflow 3 (Assets + Cosmos), and uses LLM agents (Gemini free tier by default, Anthropic optional; see ADR-017) to explain revenue changes and diagnose pipeline failures. The UI is a Streamlit "Insights Hub".

## Read first
- [docs/00_PROJECT_CONTEXT.md](docs/00_PROJECT_CONTEXT.md): index, status, credentials, URLs
- [docs/09_PROJECT_PLAN.md](docs/09_PROJECT_PLAN.md): current phase and tasks
- [docs/DECISION_LOG.md](docs/DECISION_LOG.md): why things are the way they are

## Rules
1. **Decisions:** any change to architecture, tooling, modelling pattern or scope goes in a new ADR in `docs/DECISION_LOG.md`. Don't edit old ADRs; supersede them.
2. **Status:** update task status in `docs/09_PROJECT_PLAN.md` and the "Current status" block in `00_PROJECT_CONTEXT.md` at the end of each work session.
3. **Keep data small** ([ADR-007](docs/DECISION_LOG.md#adr-007)). Don't grow volumes without reason.
4. **AI cost** ([ADR-015](docs/DECISION_LOG.md#adr-015)): develop and test agents in `AI_MODE=mock`. Make live API calls only to record fixtures or for final demos, and say so before doing it.
5. **Credentials:** ask the owner for keys only when a phase actually needs them. Never commit `.env`, `secrets/` or service-account JSON.
6. **Zero-key path must always work** ([ADR-006](docs/DECISION_LOG.md#adr-006)): a fresh clone with an untouched `.env.example` → `docker compose up` → working pipeline and UI.
7. **Conventions:** naming, tests and PII rules are in [docs/06_GOVERNANCE.md](docs/06_GOVERNANCE.md).
8. **Git:** don't create the GitHub repo or push without the owner's explicit go-ahead.

## Environment notes
- The dev machine is Windows 11 with Docker Desktop. Keep shell scripts LF (`.gitattributes`) and use named volumes for data.
