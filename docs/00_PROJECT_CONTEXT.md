# Project Context: dbt-airflow-clickhouse-dtc-growth

> **Start here.** This is the entry point to the project. Read it before changing anything, then follow the links to the document you need.

## One-line pitch
An orchestrated, analytics-ready data warehouse for a direct-to-consumer (DTC) e-commerce brand. It pulls in **9 sources of 6 different types** and models them in **ClickHouse** with **dbt**, orchestrated by **Airflow**. Every week it answers *"why did revenue move?"* automatically with an **AI insight agent**. When the pipeline breaks, an **AI triage agent** diagnoses the failure.

## The fictional company
**Kestrel Goods** sells apparel, drinkware and accessories online, direct to consumers. It runs paid acquisition on Meta and Google Ads, sends email campaigns, and uses GA4 for web analytics. The company is fictional. Its web behaviour comes from Google's public GA4 sample dataset (a merchandise store), and every other first-party system is generated synthetically to match.

## Document map

| # | Document | Answers |
|---|---|---|
| 00 | [Project Context](00_PROJECT_CONTEXT.md) | What is this, where is everything, what's the status |
| 01 | [Business Problem](01_BUSINESS_PROBLEM.md) | Why this project exists, who feels the pain |
| 02 | [Scope of Work](02_SCOPE_OF_WORK.md) | What's in, what's out, deliverables |
| 03 | [PRD](03_PRD.md) | Users, requirements, acceptance criteria, metrics |
| 04 | [Architecture Design](04_ARCHITECTURE.md) | Components, data flow, ClickHouse modelling, AI layer |
| 05 | [Data Strategy](05_DATA_STRATEGY.md) | Sources, synthetic data design, layers, volumes |
| 06 | [Governance](06_GOVERNANCE.md) | Quality, contracts, access, PII, AI guardrails |
| 07 | [Tech Stack](07_TECH_STACK.md) | Every tool, why it was chosen, what it replaced |
| 08 | [Risks & Limitations](08_RISKS_AND_LIMITATIONS.md) | What could go wrong, what this doesn't do |
| 09 | [Project Plan](09_PROJECT_PLAN.md) | Phases, tasks, status |
| — | [Decision Log](DECISION_LOG.md) | Every significant decision, with context and trade-offs |

## Current status
- **Phase:** 1 to 4 done and tested. Full dbt build 104/104; Insights Hub (home, Revenue & Growth Dashboard, Pipeline Health) restyled to the navy theme (ADR-027) and dbt docs running. Next: Phase 5, AI agents (needs `GEMINI_API_KEY`).
- **Last updated:** 2026-11-02
- See [09_PROJECT_PLAN.md](09_PROJECT_PLAN.md) for task-level status.

## Credentials (requested only when a phase needs them)

| Key | Needed in | Required? | Fallback without it |
|---|---|---|---|
| `GEMINI_API_KEY` (free, from Google AI Studio) | Phase 5 (agents) | Optional | Agents run in `mock` mode or are skipped; the pipeline still works |
| `ANTHROPIC_API_KEY` | Only if `LLM_PROVIDER=anthropic` | Optional | — |
| `GCP_PROJECT_ID` + service account JSON (BigQuery sandbox) | Phase 2 (GA4 live extract) | Optional | A committed GA4 sample (Parquet) is loaded instead |
| `FRED_API_KEY` | Phase 2 (macro data) | Optional | A committed FRED snapshot (CSV) is loaded instead |

**Principle:** a recruiter with no keys can run `docker compose up` and see the whole pipeline, dashboards and a sample AI brief. Adding keys upgrades it to live data and live agents. See [ADR-006](DECISION_LOG.md#adr-006).

## Where the AI output appears
**Insights Hub** is a Streamlit app at `http://localhost:8501`, with four pages:
1. **Weekly Brief:** the AI-written revenue bridge, with evidence tables and charts
2. **KPI Overview:** blended ROAS, CAC, MER, cohort LTV, channel mix
3. **Pipeline Health:** run history, test results, and AI triage reports for failures
4. **AI Ops:** tokens, cost and latency per agent run

Briefs are also written as Markdown to `reports/` and can optionally be posted to Slack. See [ADR-009](DECISION_LOG.md#adr-009).

## Local URLs (once running)

| Service | URL |
|---|---|
| Airflow UI | http://localhost:8080 |
| Insights Hub (Streamlit) | http://localhost:8501 |
| dbt docs (from Phase 4) | http://localhost:8081 |
| ClickHouse HTTP / Play UI | http://localhost:8123/play |
| SeaweedFS filer UI (landing bucket browser) | http://localhost:8888 |
