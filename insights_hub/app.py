"""Insights Hub entry point: registers the pages so the sidebar shows proper names (ADR-009, ADR-027).

Weekly Brief arrived with the Insight Narrator (ADR-028); AI Ops follows with the other agents.
"""
from pathlib import Path

import streamlit as st

HERE = Path(__file__).parent

st.navigation([
    st.Page(HERE / "home.py", title="Home", default=True),
    st.Page(HERE / "pages" / "3_Weekly_Brief.py", title="Weekly Brief", url_path="Weekly_Brief"),
    st.Page(HERE / "pages" / "1_Growth_Dashboard.py", title="Growth Dashboard", url_path="Growth_Dashboard"),
    st.Page(HERE / "pages" / "2_Pipeline_Health.py", title="Pipeline Health", url_path="Pipeline_Health"),
]).run()
