# 01 · Business Problem

## The Monday-morning question
Every Monday, the growth team at a DTC brand gets the same question from leadership: **"Revenue was down 12% last week. Why?"**

The data to answer it exists. It is spread across six or more systems:

| System | Holds | Owner |
|---|---|---|
| GA4 (lands in BigQuery) | Sessions, traffic sources, funnel events | Marketing |
| Store database (Postgres) | Orders, customers, refunds | Engineering |
| Meta Ads / Google Ads | Spend, impressions, clicks (exported as CSV) | Paid media agency |
| Email platform | Sends, opens, clicks (JSON exports) | CRM team |
| Google Sheets | Monthly budget and revenue targets | Finance |
| External signals | Search trends, weather, holidays, consumer sentiment | Nobody |

## Why it's still painful in 2026
1. **Attribution is broken.** Since iOS privacy changes and the loss of third-party cookies, Meta and Google each claim credit for the same conversion. Adding up platform-reported revenue gives 140%+ of actual revenue. Teams need their own **blended**, source-of-truth metrics such as MER, blended CAC and new-customer ROAS.
2. **Analysis is manual.** An analyst spends 4–8 hours a week exporting CSVs, reconciling them in spreadsheets and writing a commentary. By the time it's done, the week is half over.
3. **Dashboards show *what*, not *why*.** BI tools show that revenue fell. They don't break the change down into traffic vs conversion vs AOV, then into channel and campaign, or check whether a holiday or a heatwave explains it.
4. **External context is ignored.** Weather, search demand and macro sentiment drive DTC demand, but they are almost never joined to first-party data.
5. **Pipelines break silently.** When an ads export changes a column name, the dashboard quietly shows zero spend and nobody notices for days.

## Who feels the pain

| Persona | Pain | What they want |
|---|---|---|
| **Head of Growth** | Walks into the Monday meeting without a clear story | A one-page brief that explains the change, in plain English, before 9am |
| **Performance marketer** | Can't trust platform ROAS, so budget shifts are guesswork | Blended, deduplicated channel efficiency |
| **Finance / FP&A** | Marketing numbers don't reconcile with orders | One version of revenue and CAC, tied to targets |
| **Analytics engineer** | Firefights broken pipelines; spends time on reporting chores instead of modelling | Automated testing and diagnosis, and fewer chores |

## The opportunity
Automate the whole loop: **ingest → model → test → detect → explain → alert.**

- A data warehouse that is reliable, tested and analytics-ready, so the numbers can be trusted.
- Statistical change detection that flags movements that matter.
- An AI agent that drills into the governed marts and writes the explanation, while a human stays in charge of decisions.
- An AI agent that diagnoses pipeline failures, so the team spends less time repairing them.

## Value hypothesis (illustrative, for portfolio framing)

| Metric | Before | After |
|---|---|---|
| Time to produce the weekly performance commentary | 4–8 analyst-hours | ~0 (review only, ~15 minutes) |
| Time from a broken source to a diagnosed root cause | Hours to days | Minutes |
| Number of conflicting "revenue" figures | 3+ (GA4, platforms, store database) | 1 governed definition |
| Share of the analyst's week spent on modelling vs reporting chores | Low | High |

## Why this project is credible as a portfolio piece
It reflects a real 2026 analytics engineering job description: multiple source types, a cloud warehouse feeding an OLAP warehouse, orchestration, tested dbt models, data contracts, observability, and practical, guardrailed use of AI in the delivery loop.
