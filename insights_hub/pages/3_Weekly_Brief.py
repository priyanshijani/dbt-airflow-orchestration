"""Weekly Brief: the AI-written answer to "why did revenue move?", with the evidence behind every claim.

Reads ai.briefs (written by the ai_insight_narrator DAG). The page holds no LLM logic (ADR-009): "Generate now"
only asks Airflow to run the DAG.
"""
import json
import os
from html import escape

import requests
import streamlit as st

from insights_hub import ui
from insights_hub.db import DOWN, UP, money, query, table_exists

ui.setup("Weekly Brief · Insights Hub")
ui.header("Weekly Brief", "Why revenue moved last week, in plain English, with the numbers behind each claim")


def trigger(force: bool) -> str:
    """Ask Airflow to run the narrator DAG. Returns a message for the user."""
    base = os.getenv("AIRFLOW_API_URL", "http://airflow:8080")
    try:
        # local demo runs the simple auth manager with everyone as admin (ADR-019): the token endpoint needs no login
        token = requests.get(f"{base}/auth/token", timeout=10)
        headers = {"Authorization": f"Bearer {token.json()['access_token']}"} if token.ok else {}
        r = requests.post(f"{base}/api/v2/dags/ai_insight_narrator/dagRuns", headers=headers, timeout=15,
                          json={"logical_date": None, "conf": {"force": force}})
        return "Started. Refresh in a minute." if r.ok else f"Airflow said {r.status_code}. Trigger ai_insight_narrator in Airflow instead."
    except requests.RequestException:
        return "Could not reach Airflow. Trigger the ai_insight_narrator DAG there instead."


left, right = st.columns([4, 1])
with right:
    if st.button("Generate now", width="stretch", help="Regenerates the latest complete week"):
        st.session_state["gen_msg"] = trigger(force=True)
    if st.session_state.get("gen_msg"):
        st.caption(st.session_state["gen_msg"])

if not table_exists("ai", "briefs"):
    ui.notice("No brief yet. Trigger the <b>ai_insight_narrator</b> DAG in Airflow, or press Generate now", "info")
    st.stop()

weeks = query("select week_start, argMax(brief_id, created_at) as brief_id from ai.briefs group by week_start "
              "order by week_start desc limit 12")
if weeks.empty:
    ui.notice("No brief yet. Trigger the <b>ai_insight_narrator</b> DAG in Airflow, or press Generate now", "info")
    st.stop()

with left:
    week = st.selectbox("Week starting", weeks["week_start"].astype(str).tolist(), label_visibility="collapsed")
row = query("select brief_json, mode, model, created_at from ai.briefs where week_start = {w:Date} "
            "order by created_at desc limit 1", w=week).iloc[0]
b = json.loads(row["brief_json"])
evidence = {e["id"]: e for e in b.get("evidence", [])}
totals = {r["period"]: r for r in evidence.get("E1", {}).get("rows", [])}
now, before = totals.get("this_week"), totals.get("prior_week")

st.html(f'<div class="hub-card" style="padding:18px 22px"><div style="font-size:1.25rem;font-weight:700">'
        f'{escape(b["headline"])}</div><div style="margin-top:6px">{escape(b.get("summary", ""))}</div></div>')

if now and before:
    ui.kpis([
        dict(label="Revenue", value=money(now["revenue_usd"]), icon="layers",
             note=ui.change(now["revenue_usd"], before["revenue_usd"], "prior week")),
        dict(label="Orders", value=f"{now['orders']:,.0f}", icon="database",
             note=ui.change(now["orders"], before["orders"], "prior week")),
        dict(label="Avg order value", value=money(now["aov_usd"]), icon="clock",
             note=ui.change(now["aov_usd"], before["aov_usd"], "prior week")),
        dict(label="Ad spend", value=money(now["spend_usd"]), icon="alert",
             note=ui.change(now["spend_usd"], before["spend_usd"], "prior week", lower_is_better=None)),
    ])

with ui.card("drivers", "What moved revenue", "Each claim cites the evidence it comes from"):
    if not b["drivers"]:
        ui.notice("No driver passed verification", "warn")
    for d in b["drivers"]:
        colour = {"up": UP, "down": DOWN}.get(d.get("direction"), "#9AA8BC")
        sign = {"up": "▲", "down": "▼"}.get(d.get("direction"), "■")
        impact = f' · {"+" if d["impact_usd"] >= 0 else "-"}{money(abs(d["impact_usd"]))}' if d.get("impact_usd") not in (None, "") else ""
        st.html(f'<div style="border-left:4px solid {colour};padding:4px 12px;margin:10px 0">'
                f'<b style="color:{colour}">{sign}</b> <b>{escape(d["title"])}</b>{escape(impact)}<br>'
                f'{escape(d["explanation"])}<br><small>Evidence: {escape(", ".join(d["evidence"]))}</small></div>')

c1, c2 = st.columns(2)
with c1, ui.card("next", "Check next"):
    for w in b.get("watch_items", []):
        st.markdown(f"- {w}")
with c2, ui.card("caveats", "Caveats"):
    for c in b.get("caveats", []):
        st.markdown(f"- {c}")

v = b["verification"]
if v["passed"]:
    ui.notice("Every figure in this brief was traced back to the data.", "ok")
else:
    ui.notice("Some claims failed verification and were removed: " + escape("; ".join(v["notes"])), "warn")
st.caption(f"Generated {row['created_at']:%d %b %Y %H:%M} UTC · "
           + ("mock mode: a rule-based explainer, no AI model called" if row["mode"] == "mock" else f"model {row['model']}"))

with st.expander("Evidence behind the brief"):
    for e in evidence.values():
        st.markdown(f"**{e['id']}** · {e['title']}")
        st.dataframe(e["rows"], hide_index=True, width="stretch")
