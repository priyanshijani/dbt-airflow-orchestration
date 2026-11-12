"""Shared helpers for the Insights Hub pages: one read-only ClickHouse client, cached queries, chart colours.

The visual layer (CSS, summary blocks, cards, Plotly template) lives in ui.py.
"""
import os

import clickhouse_connect
import pandas as pd
import streamlit as st

# Colour follows the entity, never its rank: each channel keeps its step of the navy ramp on every page and filter.
CHANNEL_COLORS = {
    "paid_social": "#0B3A75",
    "paid_search": "#2F6DB5",
    "email": "#7FA8DA",
    "organic_direct_referral": "#BBD3EE",
}
CHANNEL_LABELS = {
    "paid_social": "Paid social (Meta)",
    "paid_search": "Paid search (Google)",
    "email": "Email / CRM",
    "organic_direct_referral": "Organic, direct & referral",
}
CHANNEL_ORDER = list(CHANNEL_COLORS)

# Status labels are plain text; ui.status_styler colours them by state in tables.
STATUS = {
    "success": "OK",
    "pass": "Pass",
    "skipped": "Skipped, no new data",
    "no_new_data": "Skipped, no new data",
    "skip": "Skipped",
    "warn": "Warning",
    "failed": "Failed",
    "fail": "Failed",
    "error": "Error",
}
FAILED = {"failed", "fail", "error"}
UP, DOWN, NEUTRAL = "#2F6DB5", "#dc2626", "#9AA8BC"


@st.cache_resource
def client():
    # hub_reader: SELECT on marts, meta and ai only, with a read-only profile enforced by the database
    return clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "localhost"),
        username="hub_reader",
        password=os.getenv("CLICKHOUSE_HUB_PASSWORD", ""),
        # the client is shared across sessions and reruns; a server session would reject concurrent queries
        autogenerate_session_id=False,
    )


@st.cache_data(ttl=300, show_spinner=False)
def query(sql: str, **params) -> pd.DataFrame:
    return client().query_df(sql, parameters=params)


def table_exists(database: str, table: str) -> bool:
    df = query(
        "select count() as n from system.tables where database = {db:String} and name = {t:String}",
        db=database, t=table,
    )
    return bool(df["n"].iloc[0])


def status_label(status: str) -> str:
    return STATUS.get(str(status).lower(), str(status))


def money(x: float) -> str:
    return f"${x:,.0f}"
