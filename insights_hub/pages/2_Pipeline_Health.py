"""Pipeline Health: is the data fresh, did the last loads and dbt runs succeed, and what changed shape?

Reads only the meta schema: ingestion runs (written by dlt pipelines), schema changes (dlt schema diffs) and
dbt run results (written by the on-run-end hook in dbt/macros/log_run_results.sql).
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from insights_hub import ui
from insights_hub.db import FAILED, query, status_label, table_exists

ui.setup("Pipeline Health · Insights Hub")
ui.header("Pipeline Health", "Source freshness, last loads, dbt run results and schema changes")

# ── ingestion ───────────────────────────────────────────────────────────────
with ui.card("sources", "Sources", "Last load per source, from meta.ingestion_log"):
    if not table_exists("meta", "ingestion_log"):
        ui.notice("No ingestion has run yet. Trigger the <b>bootstrap</b> DAG in Airflow", "info")
    else:
        latest = query("""
            select
                source,
                argMax(status, finished_at)       as last_status,
                argMax(rows_loaded, finished_at)  as last_rows,
                argMax(mode, finished_at)         as mode,
                max(finished_at)                  as last_run_at,
                maxIf(finished_at, status = 'success') as last_success_at,
                sum(rows_loaded)                  as total_rows,
                countIf(status = 'failed')        as failures
            from meta.ingestion_log
            group by source
            order by source
        """)
        failing = int(latest["last_status"].str.lower().isin(FAILED).sum())
        latest["last_status"] = latest["last_status"].map(status_label)
        latest["hours_since_success"] = (
            (pd.Timestamp.now(tz="UTC") - pd.to_datetime(latest["last_success_at"], utc=True)).dt.total_seconds()
            / 3600
        ).round(1)

        ui.kpis([
            dict(label="Sources", value=str(len(latest)), icon="database", note="Loaded by dlt"),
            dict(label="Last run failed", value=str(failing), icon="x",
                 note="Sources whose latest load failed"),
            dict(label="Rows loaded", value=f"{latest['total_rows'].sum():,}", icon="layers", note="All time"),
        ])
        if failing:
            ui.notice(f"{failing} source(s) failed on their last run. See the run log below", "error")
        else:
            ui.notice("Every source's last run succeeded, or skipped because nothing was new", "ok")

        st.dataframe(
            ui.status_styler(latest[["source", "last_status", "last_rows", "mode", "last_run_at",
                                     "hours_since_success", "total_rows", "failures"]], "last_status"),
            hide_index=True, width="stretch",
            column_config={
                "source": "Source", "last_status": "Last run",
                "last_rows": st.column_config.NumberColumn("Rows", format="%d"),
                "mode": "Mode", "last_run_at": st.column_config.DatetimeColumn("Last run (UTC)", format="D MMM, HH:mm"),
                "hours_since_success": st.column_config.NumberColumn("Hours since success", format="%.1f h"),
                "total_rows": st.column_config.NumberColumn("Total rows", format="%d"),
                "failures": st.column_config.NumberColumn("Failed runs", format="%d"),
            },
        )
        st.caption("Freshness is wall-clock time since the last successful load. The source data itself follows "
                   "the simulated clock, which the `simulator_advance_day` DAG moves forward.")

        with st.expander("Recent ingestion runs"):
            runs = query("select source, status, mode, rows_loaded, started_at, finished_at, error "
                         "from meta.ingestion_log order by finished_at desc limit 100")
            runs["status"] = runs["status"].map(status_label)
            runs["seconds"] = (pd.to_datetime(runs["finished_at"])
                               - pd.to_datetime(runs["started_at"])).dt.total_seconds()
            st.dataframe(ui.status_styler(runs.drop(columns=["started_at"]), "status"), hide_index=True,
                         width="stretch")

# ── dbt ─────────────────────────────────────────────────────────────────────
with ui.card("dbt", "Transformations (dbt)", "Run results from the on-run-end hook, meta.dbt_run_results"):
    if not table_exists("meta", "dbt_run_results"):
        ui.notice("No dbt run has been logged yet. Trigger the <b>dbt_transform</b> DAG in Airflow", "info")
    else:
        invocations = query("""
            select invocation_id, min(run_started_at) as started_at, count() as nodes,
                   countIf(status in ('error', 'fail')) as failed, countIf(status = 'warn') as warned,
                   round(sum(execution_time_s), 1) as busy_seconds
            from meta.dbt_run_results
            group by invocation_id
            order by started_at desc
            limit 20
        """)
        last = invocations.iloc[0]
        ui.kpis([
            dict(label="Last run", value=pd.Timestamp(last["started_at"]).strftime("%H:%M"), icon="clock",
                 note=pd.Timestamp(last["started_at"]).strftime("%a %d %b, UTC")),
            dict(label="Models and tests", value=str(int(last["nodes"])), icon="layers", note="In the last run"),
            dict(label="Failed", value=str(int(last["failed"])), icon="x", note="Errors and failing tests"),
            dict(label="Warnings", value=str(int(last["warned"])), icon="alert", note="Tests at warn severity"),
        ])
        if last["failed"]:
            ui.notice("The last dbt run had failures. Details below", "error")
        else:
            ui.notice("The last dbt run passed", "ok")

        nodes = query("select node_name, resource_type, status, execution_time_s, failures, message "
                      "from meta.dbt_run_results where invocation_id = {inv:String} order by execution_time_s desc",
                      inv=last["invocation_id"])
        bad = nodes[nodes["status"].isin(["error", "fail", "warn"])]
        if not bad.empty:
            bad = bad.assign(status=bad["status"].map(status_label))
            st.dataframe(ui.status_styler(bad, "status"), hide_index=True, width="stretch")

        left, right = st.columns(2)
        with left:
            st.html('<div class="hub-card-title">Slowest models in the last run</div>')
            slow = nodes[nodes["resource_type"] == "model"].head(10).iloc[::-1]
            fig = go.Figure(go.Bar(
                x=slow["execution_time_s"], y=slow["node_name"], orientation="h", marker_color=ui.NAVY,
                hovertemplate="%{y}: %{x:.1f} s<extra></extra>", text=slow["execution_time_s"].round(1),
                textposition="outside", textfont=dict(color=ui.TEXT_2),
            ))
            fig.update_layout(height=340, margin=dict(t=8, b=8, l=8, r=40), xaxis_ticksuffix=" s", showlegend=False,
                              bargap=0.4, xaxis_showgrid=True, xaxis_gridcolor="rgba(15,30,54,0.06)",
                              yaxis_showgrid=False)
            ui.chart(fig)
        with right:
            st.html('<div class="hub-card-title">Recent runs</div>')
            st.dataframe(
                invocations.drop(columns=["invocation_id"]), hide_index=True, width="stretch",
                column_config={
                    "started_at": st.column_config.DatetimeColumn("Started (UTC)", format="D MMM, HH:mm"),
                    "nodes": "Nodes", "failed": "Failed", "warned": "Warned",
                    "busy_seconds": st.column_config.NumberColumn("Busy time", format="%.1f s"),
                },
            )

# ── schema drift ────────────────────────────────────────────────────────────
with ui.card("schema", "Schema changes detected at load", "dlt schema diffs, newest first"):
    if not table_exists("meta", "schema_changes"):
        ui.notice("No schema changes recorded", "info")
    else:
        changes = query("select * from meta.schema_changes order by 1 desc limit 100")
        if changes.empty:
            ui.notice("No source has changed shape", "ok")
        else:
            st.dataframe(changes, hide_index=True, width="stretch")
            st.caption("New columns are added automatically by dlt. Staging only selects columns it knows, so a new "
                       "column is harmless until someone decides to use it; a dropped one fails the staging tests.")
