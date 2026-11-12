"""Step 1 of the Insight Narrator: deterministic detection (ADR-011).

SQL and Python decide WHAT changed and by how much. The model never computes a number; it only explains
the evidence pack built here. Every evidence item has an id (E1..E5) that the brief must cite.
"""
import re
import statistics

CHANNEL_LABEL = {
    "paid_social": "Paid social (Meta)",
    "paid_search": "Paid search (Google)",
    "email": "Email",
    "organic_direct_referral": "Organic, direct and referral",
}


class NoCompleteWeek(RuntimeError):
    pass


def label(channel: str) -> str:
    return CHANNEL_LABEL.get(channel, channel)


def _div(a, b):
    return a / b if b else 0.0


def _pct(now, before):
    return (now - before) / before if before else 0.0


def fetch_evidence(run, week: str | None = None) -> tuple[str, list[dict]]:
    """Run the fixed, vetted queries for one complete Monday-to-Sunday week and the week before it."""
    if week is None:
        rows = run("select max(week_start) as w from marts.mart_revenue_bridge")
        week = rows[0]["w"] if rows else None
        if not week or str(week).startswith("1970"):
            raise NoCompleteWeek("no complete week with a prior week in marts.mart_revenue_bridge")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(week)):
        raise ValueError(f"bad week: {week}")
    w = f"toDate('{week}')"
    in_two_weeks = f"report_date >= {w} - 7 and report_date < {w} + 7"
    period = f"if(report_date >= {w}, 'this_week', 'prior_week')"

    e1 = run(f"""select {period} as period, sum(orders) as orders, sum(new_customers) as new_customers,
                        sum(net_revenue_usd) as revenue_usd, sum(sessions) as sessions, sum(spend_usd) as spend_usd
                 from marts.mart_kpi_daily where {in_two_weeks} group by period""")
    e2 = run(f"""select channel, revenue_usd, prior_revenue_usd, change_usd, volume_effect_usd, price_effect_usd
                 from marts.mart_revenue_bridge where week_start = {w} order by abs(change_usd) desc""")
    e3 = run(f"""select channel, {period} as period, sum(sessions) as sessions, sum(clicks) as clicks, sum(orders) as orders,
                        sum(new_customers) as new_customers, sum(net_revenue_usd) as revenue_usd, sum(spend_usd) as spend_usd
                 from marts.mart_channel_performance where {in_two_weeks} group by channel, period order by channel, period""")
    e4 = run(f"""select report_date, orders, net_revenue_usd as revenue_usd, sessions, spend_usd
                 from marts.mart_kpi_daily where {in_two_weeks} order by report_date""")
    e5 = run(f"""select s.d as report_date, s.ga4_purchases as ga4_purchases, k.orders as shop_orders
                 from (select session_date as d, countIf(purchased) as ga4_purchases from marts.fct_sessions
                       where session_date >= {w} and session_date < {w} + 7 group by d) as s
                 inner join marts.mart_kpi_daily as k on k.report_date = s.d order by s.d""")

    for r in e1:  # derived, computed here and never by the model
        r["aov_usd"] = round(_div(r["revenue_usd"], r["orders"]), 2)
        r["conversion_rate"] = round(_div(r["orders"], r["sessions"]), 4)
        r["mer"] = round(_div(r["revenue_usd"], r["spend_usd"]), 2)
    for r in e3:
        r["roas"] = round(_div(r["revenue_usd"], r["spend_usd"]), 2)
        r["cac_usd"] = round(_div(r["spend_usd"], r["new_customers"]), 2)
    return str(week), [
        dict(id="E1", title="Weekly totals, this week vs the week before", rows=e1),
        dict(id="E2", title="Revenue bridge by channel: volume effect (more or fewer orders) and price effect (basket size)", rows=e2),
        dict(id="E3", title="Channel traffic, spend and efficiency, this week vs the week before", rows=e3),
        dict(id="E4", title="Daily revenue, orders, sessions and spend over both weeks", rows=e4),
        dict(id="E5", title="Daily GA4 purchases vs orders in the shop database", rows=e5),
    ]


def _by(rows, key="period"):
    return {r[key]: r for r in rows}


def find_signals(evidence: list[dict]) -> list[dict]:
    """Deterministic findings. Each one names the evidence that proves it."""
    ev = {e["id"]: e["rows"] for e in evidence}
    totals = _by(ev["E1"])
    now, before = totals.get("this_week"), totals.get("prior_week")
    if not now or not before:
        raise NoCompleteWeek("missing this week or prior week totals")
    change = now["revenue_usd"] - before["revenue_usd"]
    signals = [dict(kind="headline", evidence=["E1"], revenue_usd=now["revenue_usd"],
                    prior_revenue_usd=before["revenue_usd"], change_usd=round(change, 2),
                    change_pct=round(_pct(now["revenue_usd"], before["revenue_usd"]), 4))]

    # which channels explain the move
    for r in ev["E2"][:3]:
        if abs(r["change_usd"]) >= max(250.0, 0.1 * abs(change)):
            signals.append(dict(kind="channel_move", evidence=["E2"], channel=r["channel"],
                                change_usd=r["change_usd"], volume_effect_usd=r["volume_effect_usd"],
                                price_effect_usd=r["price_effect_usd"]))

    # conversion shift (orders per session)
    cvr_change = _pct(now["conversion_rate"], before["conversion_rate"])
    if abs(cvr_change) >= 0.10:
        signals.append(dict(kind="conversion_shift", evidence=["E1"], conversion_now=now["conversion_rate"],
                            conversion_before=before["conversion_rate"], change_pct=round(cvr_change, 4)))

    # paid-channel efficiency
    per_channel: dict[str, dict] = {}
    for r in ev["E3"]:
        per_channel.setdefault(r["channel"], {})[r["period"]] = r
    for ch, p in per_channel.items():
        a, b = p.get("this_week"), p.get("prior_week")
        if not a or not b or b["spend_usd"] <= 0:
            continue
        spend_up, sessions_up = _pct(a["spend_usd"], b["spend_usd"]), _pct(a["sessions"], b["sessions"])
        if spend_up >= 0.30 and sessions_up < 0.10 and a["spend_usd"] - b["spend_usd"] >= 500:
            signals.append(dict(kind="spend_without_traffic", evidence=["E3"], channel=ch,
                                spend_now=a["spend_usd"], spend_before=b["spend_usd"], spend_change_pct=round(spend_up, 4),
                                sessions_now=a["sessions"], sessions_before=b["sessions"],
                                sessions_change_pct=round(sessions_up, 4)))
        elif b["roas"] and _pct(a["roas"], b["roas"]) <= -0.15:
            signals.append(dict(kind="efficiency_drop", evidence=["E3"], channel=ch, roas_now=a["roas"],
                                roas_before=b["roas"], change_pct=round(_pct(a["roas"], b["roas"]), 4),
                                clicks_change_pct=round(_pct(a["clicks"], b["clicks"]), 4)))

    # shop orders falling while GA4 still sees purchases: the problem is after the click (payments, checkout)
    ratios = [(r["report_date"], _div(r["shop_orders"], r["ga4_purchases"])) for r in ev["E5"] if r["ga4_purchases"]]
    if len(ratios) >= 4:
        typical = statistics.median(x for _, x in ratios)
        bad = [d for d, x in ratios if typical and x < 0.7 * typical]
        if bad:
            signals.append(dict(kind="backend_gap", evidence=["E5"], days=bad, typical_orders_per_ga4_purchase=round(typical, 2)))

    # a single day far below the rest of its week
    this_week_days = [r for r in ev["E4"] if r["report_date"] >= (ev["E5"][0]["report_date"] if ev["E5"] else "")]
    if len(this_week_days) >= 5:
        typical_rev = statistics.median(r["revenue_usd"] for r in this_week_days)
        worst = min(this_week_days, key=lambda r: r["revenue_usd"])
        already = signals and any(s["kind"] == "backend_gap" and worst["report_date"] in s["days"] for s in signals)
        if typical_rev and worst["revenue_usd"] < 0.6 * typical_rev and not already:
            signals.append(dict(kind="weak_day", evidence=["E4"], day=worst["report_date"],
                                revenue_usd=worst["revenue_usd"], typical_day_revenue_usd=typical_rev))
    for i, s in enumerate(signals, 1):
        s["id"] = f"S{i}"
    return signals


def numeric_pool(evidence: list[dict], signals: list[dict]) -> list[float]:
    """Every number the model is allowed to quote (absolute values), for the verification step."""
    pool = set()

    def walk(x):
        if isinstance(x, bool):
            return
        if isinstance(x, (int, float)):
            pool.add(abs(float(x)))
        elif isinstance(x, dict):
            [walk(v) for v in x.values()]
        elif isinstance(x, list):
            [walk(v) for v in x]

    walk([e["rows"] for e in evidence])
    walk(signals)
    return sorted(pool)
