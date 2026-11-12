"""Revenue & Growth Dashboard: summary blocks, weekly revenue and orders, channel mix, top countries, the weekly
revenue bridge, targets and cohorts.

Everything here reads contracted marts (marts.*), never staging, so the numbers match what the AI narrator sees.
"""
from datetime import timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from insights_hub import ui
from insights_hub.db import (CHANNEL_COLORS, CHANNEL_LABELS, CHANNEL_ORDER, DOWN, NEUTRAL, UP, money, query,
                             table_exists)

ui.setup("Growth Dashboard · Insights Hub")

if not table_exists("marts", "mart_channel_performance"):
    ui.header("Revenue & Growth Dashboard")
    ui.notice("The marts have not been built yet. Run the <b>bootstrap</b> DAG, then <b>dbt_transform</b>, "
              "in Airflow", "info")
    st.stop()

perf = query("select * from marts.mart_channel_performance order by report_date, channel")
perf["report_date"] = pd.to_datetime(perf["report_date"])
for col in ("net_revenue_usd", "spend_usd"):
    perf[col] = perf[col].astype(float)
first_day, last_day = perf["report_date"].min().date(), perf["report_date"].max().date()

# order grain, for units, refunds, margin, repeat buyers and country (about 6k rows, ADR-007)
orders = query("""
    select o.order_date, o.channel, o.customer_id, o.is_first_order,
           toFloat64(o.gross_revenue_usd) as gross_usd, toFloat64(o.refunded_usd) as refunded_usd,
           toFloat64(o.net_revenue_usd) as net_usd, toFloat64(o.gross_margin_usd) as margin_usd,
           ifNull(c.country_code, '') as country_code
    from marts.fct_orders o
    left join marts.dim_customers c on o.customer_id = c.customer_id
""")
orders["order_date"] = pd.to_datetime(orders["order_date"]).dt.date

ui.header(
    "Revenue & Growth Dashboard",
    "Kestrel Goods net revenue, orders and marketing efficiency by channel",
    f"Data through {last_day:%a %d %b %Y}, simulated clock",
)

# ── filters: one row, above every chart ─────────────────────────────────────
f1, f2 = st.columns([2, 3])
with f1:
    preset = st.radio("Period", ["Last 7 days", "Last 28 days", "All data"], index=1, horizontal=True)
days = {"Last 7 days": 7, "Last 28 days": 28}.get(preset)
start = max(first_day, last_day - timedelta(days=days - 1)) if days else first_day
with f2:
    channels = st.multiselect(
        "Channels", CHANNEL_ORDER, default=CHANNEL_ORDER, format_func=CHANNEL_LABELS.get
    )
if not channels:
    ui.notice("Pick at least one channel", "warn")
    st.stop()

sel = perf[perf["channel"].isin(channels)]
period = sel[sel["report_date"].dt.date.between(start, last_day)]
length = (last_day - start).days + 1
prior_start, prior_end = start - timedelta(days=length), start - timedelta(days=1)
prior = sel[sel["report_date"].dt.date.between(prior_start, prior_end)]
has_prior = prior_start >= first_day
vs = f"prior {length} days" if has_prior else ""

sel_orders = orders[orders["channel"].isin(channels)]
period_orders = sel_orders[sel_orders["order_date"].between(start, last_day)]


def totals(df: pd.DataFrame) -> dict:
    rev, n, spend = df["net_revenue_usd"].sum(), df["orders"].sum(), df["spend_usd"].sum()
    sessions, new = df["sessions"].sum(), df["new_customers"].sum()
    return {
        "Net revenue": rev,
        "Orders": n,
        "AOV": rev / n if n else 0,
        "Blended ROAS": rev / spend if spend else 0,
        "CAC": spend / new if new else 0,
        "Conversion rate": n / sessions if sessions else 0,
    }


now, before = totals(period), totals(prior) if has_prior else {}


def note(name: str) -> str:
    return ui.change(now[name], before.get(name), vs) if has_prior else "No earlier period of equal length"


# ── summary blocks ──────────────────────────────────────────────────────────
ui.kpis([
    dict(label="Net revenue", value=money(now["Net revenue"]), icon="revenue", note=note("Net revenue"),
         help="Gross sales minus refunds, last-click attributed"),
    dict(label="Orders", value=f"{now['Orders']:,.0f}", icon="cart", note=note("Orders")),
    dict(label="Average order value", value=f"${now['AOV']:,.2f}", icon="receipt", note=note("AOV")),
    dict(label="Blended ROAS", value=f"{now['Blended ROAS']:.2f}x", icon="target", note=note("Blended ROAS"),
         help="Net revenue from all channels divided by all ad spend"),
])

# ── weekly revenue by channel, and the channel mix ──────────────────────────
weekly = (
    sel.assign(week=sel["report_date"].dt.to_period("W-SUN").dt.start_time)
    .groupby(["week", "channel"], as_index=False)[["net_revenue_usd", "spend_usd", "orders", "new_customers"]]
    .sum()
)
# only complete Monday-to-Sunday weeks, so a part week does not read as a drop
weekly = weekly[(weekly["week"].dt.date >= first_day) & ((weekly["week"] + pd.Timedelta(days=6)).dt.date <= last_day)]
shown = [c for c in CHANNEL_ORDER if c in channels]

left, right = st.columns([2, 1])
with left, ui.card("revenue", "Net revenue by channel, weekly", "Complete Monday-to-Sunday weeks, all dates"):
    fig = go.Figure()
    for ch in shown:
        d = weekly[weekly["channel"] == ch]
        fig.add_bar(x=d["week"], y=d["net_revenue_usd"], name=CHANNEL_LABELS[ch], marker_color=CHANNEL_COLORS[ch],
                    hovertemplate="%{x|%d %b}: $%{y:,.0f}<extra>" + CHANNEL_LABELS[ch] + "</extra>")
    fig.update_layout(barmode="stack", bargap=0.35, height=340, yaxis_tickprefix="$", hovermode="x unified",
                      xaxis_tickformat="%d %b")
    ui.chart(fig)

with right, ui.card("mix", "Revenue by channel", f"{start:%d %b} to {last_day:%d %b}"):
    mix = period.groupby("channel")["net_revenue_usd"].sum().reindex(shown).fillna(0)
    share = mix / mix.sum() if mix.sum() else mix
    fig = go.Figure(go.Pie(
        labels=[CHANNEL_LABELS[c] for c in shown], values=mix.values, hole=0.62, sort=False, direction="clockwise",
        marker=dict(colors=[CHANNEL_COLORS[c] for c in shown], line=dict(color="#ffffff", width=2)),
        textinfo="none", hovertemplate="%{label}: $%{value:,.0f} (%{percent})<extra></extra>",
    ))
    fig.update_layout(height=200, showlegend=False, margin=dict(t=8, b=8, l=8, r=8),
                      annotations=[dict(text=f"<b>{money(mix.sum())}</b>", showarrow=False,
                                        font=dict(size=16, color=ui.NAVY))])
    ui.chart(fig)
    ui.legend([(CHANNEL_COLORS[c], CHANNEL_LABELS[c], f"{share[c]:.1%}") for c in shown])

# ── orders, paid efficiency, top countries ──────────────────────────────────
c1, c2, c3 = st.columns(3)
with c1, ui.card("orders", "Orders, weekly", "Complete weeks, selected channels"):
    w = weekly.groupby("week", as_index=False)["orders"].sum()
    fig = go.Figure(go.Scatter(
        x=w["week"], y=w["orders"], mode="lines+markers", line=dict(color=ui.NAVY, width=2.5),
        marker=dict(size=6, color=ui.NAVY), hovertemplate="Week of %{x|%d %b}: %{y:,} orders<extra></extra>",
    ))
    fig.update_layout(height=260, xaxis_tickformat="%d %b", yaxis_rangemode="tozero")
    ui.chart(fig)

with c2, ui.card("roas", "ROAS by paid channel, weekly", "Our last-click attribution, not the platforms' claims"):
    paid = [c for c in ("paid_social", "paid_search") if c in channels]
    if not paid:
        ui.notice("Select a paid channel to see ROAS", "info")
    else:
        fig = go.Figure()
        for ch in paid:
            d = weekly[weekly["channel"] == ch]
            roas = d["net_revenue_usd"] / d["spend_usd"].where(d["spend_usd"] > 0)
            fig.add_scatter(x=d["week"], y=roas, name=CHANNEL_LABELS[ch], mode="lines+markers",
                            line=dict(color=CHANNEL_COLORS[ch], width=2), marker=dict(size=6),
                            hovertemplate="%{x|%d %b}: %{y:.2f}x<extra>" + CHANNEL_LABELS[ch] + "</extra>")
        fig.add_hline(y=1, line=dict(color=NEUTRAL, width=1, dash="dot"),
                      annotation_text="break-even", annotation_position="bottom right",
                      annotation_font=dict(color=ui.MUTED, size=11))
        fig.update_layout(height=260, yaxis_ticksuffix="x", hovermode="x unified", xaxis_tickformat="%d %b",
                          legend=dict(y=-0.25))
        ui.chart(fig)

COUNTRIES = {
    "US": "United States", "IN": "India", "CA": "Canada", "GB": "United Kingdom", "ES": "Spain", "DE": "Germany",
    "FR": "France", "AU": "Australia", "BR": "Brazil", "NL": "Netherlands", "IT": "Italy", "MX": "Mexico",
    "JP": "Japan", "PL": "Poland", "SE": "Sweden", "IE": "Ireland",
}
with c3, ui.card("countries", "Top 5 countries by revenue", f"{start:%d %b} to {last_day:%d %b}"):
    by_country = period_orders.groupby("country_code")["net_usd"].sum().sort_values(ascending=False)
    unknown = by_country.get("", 0.0)
    known = by_country.drop("", errors="ignore").head(5)
    if known.empty:
        ui.notice("No orders with a known country in this period", "info")
    else:
        ui.ranked([(COUNTRIES.get(code, code), v) for code, v in known.items()], money)
        if unknown:
            st.caption(f"{unknown / by_country.sum():.0%} of revenue comes from customers with no country on file")

# ── secondary figures ───────────────────────────────────────────────────────
gross = period_orders["gross_usd"].sum()
net = period_orders["net_usd"].sum()
n_orders = len(period_orders)
ui.strip([
    dict(label="Customers", value=f"{period_orders['customer_id'].nunique():,}", icon="users",
         note="Unique buyers in the period"),
    dict(label="Repeat orders", value=f"{(~period_orders['is_first_order']).sum() / n_orders:.1%}" if n_orders
         else "n/a", icon="repeat", note="Orders from returning customers"),
    dict(label="CAC", value=f"${now['CAC']:,.2f}", icon="megaphone", note="Ad spend per new customer"),
    dict(label="Conversion rate", value=f"{now['Conversion rate']:.2%}", icon="funnel", note="Orders per session"),
    dict(label="Refund rate", value=f"{period_orders['refunded_usd'].sum() / gross:.1%}" if gross else "n/a",
         icon="undo", note="Refunded share of gross sales"),
    dict(label="Gross margin", value=f"{period_orders['margin_usd'].sum() / net:.1%}" if net else "n/a",
         icon="percent", note="Share of net revenue"),
])

# ── channel table ───────────────────────────────────────────────────────────
with ui.card("channels", "Channels in the period", f"{start:%d %b} to {last_day:%d %b}"):
    by_ch = period.groupby("channel", as_index=False)[
        ["sessions", "orders", "new_customers", "net_revenue_usd", "spend_usd", "clicks"]].sum()
    by_ch["roas"] = by_ch["net_revenue_usd"] / by_ch["spend_usd"].where(by_ch["spend_usd"] > 0)
    by_ch["cac"] = by_ch["spend_usd"] / by_ch["new_customers"].where(
        (by_ch["spend_usd"] > 0) & (by_ch["new_customers"] > 0))
    by_ch["share"] = by_ch["net_revenue_usd"] / by_ch["net_revenue_usd"].sum()
    by_ch["channel"] = by_ch["channel"].map(CHANNEL_LABELS)
    st.dataframe(
        by_ch.sort_values("net_revenue_usd", ascending=False),
        hide_index=True, width="stretch",
        column_config={
            "channel": "Channel", "sessions": st.column_config.NumberColumn("Sessions", format="%d"),
            "orders": st.column_config.NumberColumn("Orders", format="%d"),
            "new_customers": st.column_config.NumberColumn("New customers", format="%d"),
            "net_revenue_usd": st.column_config.NumberColumn("Net revenue", format="$%.0f"),
            "spend_usd": st.column_config.NumberColumn("Spend", format="$%.0f"),
            "clicks": st.column_config.NumberColumn("Ad clicks", format="%d"),
            "roas": st.column_config.NumberColumn("ROAS", format="%.2fx"),
            "cac": st.column_config.NumberColumn("CAC", format="$%.2f"),
            "share": st.column_config.ProgressColumn("Revenue share", format="percent", min_value=0, max_value=1),
        },
    )

# ── revenue bridge: why did revenue move last week? ─────────────────────────
with ui.card("bridge", "Why revenue moved", "Week over week, split into order count and basket size per channel"):
    bridge = query("select * from marts.mart_revenue_bridge order by week_start, channel")
    if bridge.empty:
        ui.notice("The bridge needs two complete Monday-to-Sunday weeks of data", "info")
    else:
        for col in ("revenue_usd", "prior_revenue_usd", "change_usd", "volume_effect_usd", "price_effect_usd"):
            bridge[col] = bridge[col].astype(float)
        weeks = sorted(bridge["week_start"].unique(), reverse=True)
        week = st.selectbox("Week starting", weeks, format_func=lambda d: pd.Timestamp(d).strftime("%a %d %b %Y"))
        b = bridge[(bridge["week_start"] == week) & bridge["channel"].isin(channels)]
        b = b.set_index("channel").reindex(shown).dropna(subset=["revenue_usd"])

        steps_x, steps_y, steps_m = ["Prior week"], [b["prior_revenue_usd"].sum()], ["absolute"]
        for ch, row in b.iterrows():
            short = CHANNEL_LABELS[ch].split(" (")[0]
            steps_x += [f"{short}: orders", f"{short}: basket"]
            steps_y += [row["volume_effect_usd"], row["price_effect_usd"]]
            steps_m += ["relative", "relative"]
        steps_x.append("This week")
        steps_y.append(b["revenue_usd"].sum())
        steps_m.append("total")
        fig = go.Figure(go.Waterfall(
            x=steps_x, y=steps_y, measure=steps_m,
            increasing=dict(marker_color=UP), decreasing=dict(marker_color=DOWN), totals=dict(marker_color=ui.NAVY),
            connector=dict(line=dict(color=NEUTRAL, width=1)),
            hovertemplate="%{x}: $%{y:,.0f}<extra></extra>",
        ))
        fig.update_layout(height=360, yaxis_tickprefix="$", showlegend=False)
        ui.chart(fig)
        change = b["change_usd"].sum()
        st.caption(
            f"Revenue {'rose' if change >= 0 else 'fell'} {money(abs(change))} week over week. "
            "Orders = more or fewer orders at last week's basket size; basket = change in average order value. "
            "Blue raises revenue, red lowers it."
        )

# ── targets and cohorts ─────────────────────────────────────────────────────
t_col, c_col = st.columns(2)
with t_col, ui.card("targets", "Revenue against the finance plan", "Months with both a target and revenue"):
    targets = query("select * from marts.mart_target_tracking where revenue_usd > 0 or month_start <= today() "
                    "order by month_start, channel")
    targets = targets[targets["channel"].isin(channels) & (targets["revenue_usd"] > 0)]
    if targets.empty:
        ui.notice("No months with both a target and revenue yet", "info")
    else:
        targets["month"] = pd.to_datetime(targets["month_start"]).dt.strftime("%b %Y") + \
            targets["is_month_in_progress"].astype(bool).map({True: " (in progress)", False: ""})
        targets["channel"] = targets["channel"].map(CHANNEL_LABELS)
        st.dataframe(
            targets[["month", "channel", "revenue_usd", "revenue_target_usd", "revenue_attainment", "spend_usd",
                     "budget_usd"]],
            hide_index=True, width="stretch",
            column_config={
                "month": "Month", "channel": "Channel",
                "revenue_usd": st.column_config.NumberColumn("Revenue", format="$%.0f"),
                "revenue_target_usd": st.column_config.NumberColumn("Target", format="$%.0f"),
                "revenue_attainment": st.column_config.ProgressColumn("Attainment", format="percent",
                                                                      min_value=0, max_value=1.5),
                "spend_usd": st.column_config.NumberColumn("Spend", format="$%.0f"),
                "budget_usd": st.column_config.NumberColumn("Budget", format="$%.0f"),
            },
        )

with c_col, ui.card("cohorts", "Customer cohorts", "Share of each first-order cohort that bought again"):
    cohorts = query("select * from marts.mart_customer_cohorts order by cohort_month, months_since_first_order")
    if cohorts.empty:
        ui.notice("No cohorts yet", "info")
    else:
        cohorts["cohort"] = pd.to_datetime(cohorts["cohort_month"]).dt.strftime("%b %Y")
        size = cohorts[cohorts["months_since_first_order"] == 0].set_index("cohort")["active_customers"]
        grid = cohorts.pivot(index="cohort", columns="months_since_first_order", values="active_customers")
        grid = grid.reindex(size.index)
        retention = grid.div(size, axis=0)
        retention.columns = [f"Month {c}" for c in retention.columns]
        retention.insert(0, "Customers", size)
        st.dataframe(
            retention, width="stretch",
            column_config={c: st.column_config.NumberColumn(c, format="percent") for c in retention.columns[1:]},
        )
        st.caption("The window is short (Nov to Jan), so only the earliest cohorts show repeat months.")
