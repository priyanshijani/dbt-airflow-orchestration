"""Home page: AI mode, the latest week at a glance, and where to go next (ADR-009).

Registered in app.py. Weekly Brief and AI Ops arrive with the agents in Phase 5.
"""
import os
from datetime import timedelta
from html import escape

import pandas as pd
import streamlit as st

from insights_hub import ui
from insights_hub.db import money, query, table_exists

ui.setup("Insights Hub · Kestrel Goods")


def ai_mode() -> str:
    mode = os.getenv("AI_MODE", "").strip().lower()
    if mode in {"live", "mock", "off"}:
        return mode
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    key = os.getenv("GEMINI_API_KEY") if provider == "gemini" else os.getenv("ANTHROPIC_API_KEY")
    return "live" if key else "mock"


try:
    has_marts = table_exists("marts", "mart_kpi_daily")
except Exception as exc:  # surfaced in the UI, not swallowed
    ui.header("Insights Hub", "Kestrel Goods growth data")
    ui.notice(f"ClickHouse connection failed: {escape(str(exc))}", "error")
    st.stop()

kpi = query("select * from marts.mart_kpi_daily order by report_date") if has_marts else None
last = pd.to_datetime(kpi["report_date"]).max() if has_marts else None
ui.header(
    "Insights Hub",
    "Kestrel Goods growth data: 9 sources → ClickHouse → dbt → Airflow → AI agents",
    f"Data through {last:%a %d %b %Y}" if has_marts else "",
)

mode = ai_mode()
ui.notice(
    f"AI mode: <b>{mode}</b>" + ("" if mode == "live" else ". Add a GEMINI_API_KEY to .env for live agents"),
    {"live": "ok", "mock": "info", "off": "warn"}[mode],
)

if not has_marts:
    ui.notice("No data yet. In Airflow (http://localhost:8080), run <b>bootstrap</b>; dbt_transform follows "
              "automatically when new data lands. This page fills in once the marts exist", "info")
else:
    kpi["report_date"] = pd.to_datetime(kpi["report_date"])
    week = kpi[kpi["report_date"] > last - timedelta(days=7)]
    prev = kpi[(kpi["report_date"] <= last - timedelta(days=7)) & (kpi["report_date"] > last - timedelta(days=14))]
    rev, rev_p = float(week["net_revenue_usd"].sum()), float(prev["net_revenue_usd"].sum())
    orders, orders_p = int(week["orders"].sum()), int(prev["orders"].sum())
    spend, spend_p = float(week["spend_usd"].sum()), float(prev["spend_usd"].sum())
    roas_p = rev_p / spend_p if spend_p else 0

    st.html('<div class="hub-card-title" style="margin-top:16px">Last 7 days</div>')
    ui.kpis([
        dict(label="Net revenue", value=money(rev), icon="revenue", note=ui.change(rev, rev_p, "prior 7 days")),
        dict(label="Orders", value=f"{orders:,}", icon="cart", note=ui.change(orders, orders_p, "prior 7 days")),
        dict(label="Ad spend", value=money(spend), icon="megaphone",
             note=ui.change(spend, spend_p, "prior 7 days", lower_is_better=None)),
        dict(label="Blended ROAS", value=f"{rev / spend:.2f}x" if spend else "n/a", icon="target",
             note=ui.change(rev / spend, roas_p, "prior 7 days") if spend else ""),
    ])

with ui.card("pages", "Pages"):
    st.markdown(
        """
- **Growth Dashboard**: revenue, orders, ROAS, CAC and conversion by channel; why revenue moved week over week;
  plan vs actual; cohorts
- **Pipeline Health**: source freshness, last loads, dbt run results and schema changes
- **Weekly Brief** and **AI Ops** arrive with the AI agents (Phase 5)

Model documentation and lineage: [dbt docs](http://localhost:8081)
"""
    )
