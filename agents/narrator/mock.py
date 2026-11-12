"""Mock-mode explainer: a rule-based stand-in for the model (ADR-015).

It turns the deterministic signals into the same JSON a model would return, so the whole pipeline (detect,
verify, render, persist, Hub page) runs and tests at zero cost, and the zero-key path shows a real, data-grounded
brief (ADR-006). Live mode replaces only this step.
"""
from agents.narrator.detect import label


def usd(x: float) -> str:
    return f"${abs(x):,.0f}"


def _dir(x: float) -> str:
    return "up" if x > 0 else "down" if x < 0 else "flat"


def draft(signals: list[dict]) -> dict:
    head = next(s for s in signals if s["kind"] == "headline")
    pct = head["change_pct"]
    verb = "rose" if pct > 0 else "fell" if pct < 0 else "held flat"
    headline = (f"Revenue {verb} {abs(pct):.1%} to {usd(head['revenue_usd'])}, "
                f"{'+' if head['change_usd'] >= 0 else '-'}{usd(head['change_usd'])} vs the prior week")

    drivers, watch = [], []
    for s in signals:
        k = s["kind"]
        if k == "channel_move":
            d = _dir(s["change_usd"])
            drivers.append(dict(
                title=f"{label(s['channel'])} {'added' if d == 'up' else 'lost'} {usd(s['change_usd'])}",
                direction=d, impact_usd=s["change_usd"], evidence=s["evidence"],
                explanation=(f"Order volume moved revenue by {'+' if s['volume_effect_usd'] >= 0 else '-'}{usd(s['volume_effect_usd'])} "
                             f"and basket size by {'+' if s['price_effect_usd'] >= 0 else '-'}{usd(s['price_effect_usd'])}.")))
        elif k == "conversion_shift":
            d = _dir(s["change_pct"])
            drivers.append(dict(
                title="Visitors converted " + ("better" if d == "up" else "worse"), direction=d, impact_usd=None,
                evidence=s["evidence"],
                explanation=(f"Orders per session went from {s['conversion_before']:.2%} to {s['conversion_now']:.2%} "
                             f"({s['change_pct']:+.1%}).")))
        elif k == "spend_without_traffic":
            drivers.append(dict(
                title=f"{label(s['channel'])} spend rose without more traffic", direction="down", impact_usd=None,
                evidence=s["evidence"],
                explanation=(f"Spend went from {usd(s['spend_before'])} to {usd(s['spend_now'])} ({s['spend_change_pct']:+.0%}) "
                             f"while sessions moved only {s['sessions_change_pct']:+.0%}.")))
            watch.append(f"Review recent campaign changes in {label(s['channel'])}: more spend is not bringing visitors.")
        elif k == "efficiency_drop":
            drivers.append(dict(
                title=f"{label(s['channel'])} return on spend fell", direction="down", impact_usd=None,
                evidence=s["evidence"],
                explanation=(f"Revenue per $1 of spend went from {s['roas_before']:.2f} to {s['roas_now']:.2f} "
                             f"({s['change_pct']:+.0%}); clicks moved {s['clicks_change_pct']:+.0%}.")))
            watch.append(f"Check costs and bids in {label(s['channel'])}.")
        elif k == "backend_gap":
            days = ", ".join(s["days"])
            drivers.append(dict(
                title="Orders dropped while web analytics still saw purchases", direction="down", impact_usd=None,
                evidence=s["evidence"],
                explanation=(f"On {days}, shop orders per GA4 purchase fell well below the usual {s['typical_orders_per_ga4_purchase']:.2f}. "
                             "Shoppers reached the purchase step but the order did not complete, which points to payment or checkout.")))
            watch.append(f"Check the payment provider and checkout errors for {days}.")
        elif k == "weak_day":
            drivers.append(dict(
                title=f"{s['day']} was unusually weak", direction="down", impact_usd=None, evidence=s["evidence"],
                explanation=f"Revenue was {usd(s['revenue_usd'])} against a typical day of {usd(s['typical_day_revenue_usd'])}."))

    names = [d["title"] for d in drivers[:2]]
    summary = ("Main drivers: " + "; ".join(names) + ".") if names else "No single channel or metric explains the move."
    return dict(
        headline=headline, summary=summary, drivers=drivers,
        watch_items=watch or ["Nothing needs action beyond normal monitoring."],
        caveats=["GA4 under-counts purchases (consent, ad blockers), so shop-database orders are the source of truth for revenue.",
                 "Figures cover complete Monday-to-Sunday weeks only."],
    )
