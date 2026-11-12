# 08 · Risk Assessment & Limitations

## 1. Risk register

Likelihood (L) and Impact (I) are scored 1–3.

| ID | Risk | L | I | Mitigation | Owner |
|---|---|---|---|---|---|
| R1 | **Stack too heavy for a reviewer's laptop** (Airflow 3 needs several containers) | 2 | 3 | LocalExecutor, one Postgres, single-container Airflow (ADR-019), low-memory ClickHouse config, memory limits per container; document 16 GB RAM as comfortable and 8 GB as a tight minimum (Docker/WSL limited to about 4 GB, everything else closed). Observed on a 7.7 GB laptop: a clean first load took 45 minutes and failed under memory pressure, which is why seed data is committed and schedules start paused (ADR-024) | AE |
| R2 | **Dependency conflicts** between Airflow, dbt, dlt and Cosmos | 3 | 2 | dbt in its own venv inside the image; pin all versions; build image in CI | AE |
| R3 | **dbt-clickhouse adapter gaps** (incremental strategies, contracts and unit tests lag behind the Snowflake/BigQuery adapters) | 2 | 2 | Check each feature in a spike before relying on it; record workarounds in the decision log | AE |
| R4 | **Elementary support for ClickHouse is less mature** | 2 | 1 | Optional component; if it breaks, fall back to custom anomaly SQL tests plus persisted run results | AE |
| R5 | **Reviewer has no API keys** | 3 | 2 | Zero-key design: committed GA4 and FRED samples, AI mock mode with a pre-recorded brief ([ADR-006](DECISION_LOG.md#adr-006)) | AE |
| R6 | **LLM hallucinates numbers in the brief** | 2 | 3 | Evidence-required schema, post-hoc numeric verification against re-run queries, "unverified" badge ([06_GOVERNANCE §7](06_GOVERNANCE.md#7-ai-governance)) | AE |
| R7 | **Uncontrolled AI cost** during development or by reviewers | 2 | 2 | Token caps per run, max tool calls, prompt caching, mock mode by default in development and CI; cost shown on AI Ops page | AE |
| R8 | **Secret leakage** (API key or service account committed) | 1 | 3 | `.gitignore` for `.env` and `secrets/`; gitleaks in CI and pre-commit; `.env.example` holds placeholders only | AE |
| R9 | **BigQuery sandbox limits or schema change** in the public GA4 dataset | 1 | 2 | Committed Parquet sample is the default; live extract is an opt-in upgrade; queries limited by date suffix | AE |
| R10 | **External API outage or rate limit** (Open-Meteo, Nager.Date, FRED) | 2 | 1 | Retries with backoff; committed snapshots; freshness `warn` rather than `error` for non-critical external sources | AE |
| R11 | **Prompt-injection through data** (e.g., a campaign name containing instructions) | 1 | 2 | Tool results passed as data, not instructions; system prompt states this; agent has no write or exec capability, so the worst case is a bad brief, which is caught by verification | AE |
| R12 | **Scope creep** (MMM, more sources, cloud deploy) | 3 | 2 | Scope document with an explicit out-of-scope list; extensions go to the backlog | AE |
| R13 | **Synthetic data looks fake** and weakens the analysis | 2 | 2 | Causal generator with seasonality, elasticity and planted stories; realistic mess; documented assumptions | AE |
| R15 | **Gemini free-tier changes or rate limits** (models removed from the free tier, low RPM/RPD) | 2 | 2 | Model IDs in `.env`; ≤ 10 requests per run; exponential backoff on 429; mock mode always available; Anthropic provider as fallback | AE |
| R16 | **Free-tier data terms:** Google may use free-tier prompts to improve its products | 3 | 1 | Agents see only synthetic, aggregated, PII-free marts and logs; stated in the README; paid tier or Anthropic for any real data | AE |
| R14 | **Windows-specific Docker issues** (line endings, volume performance) | 2 | 1 | `.gitattributes` forcing LF for `*.sh` and `*.py`; named volumes instead of bind mounts for data | AE |

## 2. Known limitations (stated openly in the README)
1. **The data is synthetic, apart from GA4 and the external APIs.** Insights demonstrate the method; they say nothing about a real business.
2. **GA4 dates are shifted** from 2020–21 into the simulation window. Weekday alignment is kept, but the calendar is not exact.
3. **The GA4 ↔ orders join is simulated.** Synthetic orders reuse sampled GA4 purchase session IDs, so attribution joins work, but they don't reflect the real customer journey.
4. **GA4 public data is obfuscated** (`<Other>`, `(data deleted)` values) and sampled down to about 3% of users, so channel-level session counts are low.
5. **Attribution is rule-based** (last non-direct, first-click, linear). There is no data-driven or MMM attribution.
6. **Batch only.** The finest grain is hourly, with no streaming.
7. **Single-node, local deployment.** There is no high availability, no backups, and only demo auth. The production mapping is described in [04_ARCHITECTURE §10](04_ARCHITECTURE.md#10-how-this-maps-to-production).
8. **AI briefs are decision support, not decisions.** They are probabilistic, need human review, and quality depends on the model version.
9. **No semantic-layer server.** MetricFlow doesn't support ClickHouse, so metrics are governed in contracted marts and documented YAML ([ADR-014](DECISION_LOG.md#adr-014)).
10. **Ad platform data comes from CSV exports**, not live APIs, which mirrors agency-delivered reporting.

## 3. Assumptions
- Reviewers have Docker Desktop and 8 GB+ RAM.
- The default LLM is the **Gemini API free tier** (key from Google AI Studio). Free-tier models and quotas change often, so model IDs are configurable ([ADR-017](DECISION_LOG.md#adr-017)).
- The public GA4 sample dataset remains available in `bigquery-public-data`.
