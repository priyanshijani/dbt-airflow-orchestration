"""Ad platform exports: Meta Ads (human-readable CSV) and Google Ads (agency script CSV).

Spend is grounded in reality where possible: Google paid-search spend follows the real GA4
cpc session counts. Platform-reported conversions over-claim versus backend orders, which is
the attribution problem this project exists to expose (01_BUSINESS_PROBLEM).
"""
import csv
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from generators import config
from generators.ga4 import session_sources

FX_PER_USD = {"USD": 1.0, "GBP": 0.79, "EUR": 0.92}

META_CAMPAIGNS = [  # (slug, export name, account, currency, base daily USD, active from, active to)
    ("prospecting_broad", "Prospecting - Broad", "Kestrel Goods US", "USD", 260, None, None),
    ("prospecting_lal2", "Prospecting - Lookalike 2%", "Kestrel Goods US", "USD", 180, None, None),
    ("retargeting_dpa", "Retargeting - DPA", "Kestrel Goods US", "USD", 140, None, None),
    ("uk_prospecting", "UK | Prospecting", "Kestrel Goods UK", "GBP", 70, None, None),
    ("eu_prospecting", "EU | Prospecting", "Kestrel Goods EU", "EUR", 60, None, None),
    ("bfcm_2025", "BFCM Sale 2025", "Kestrel Goods US", "USD", 400, date(2025, 11, 20), date(2025, 12, 2)),
]
AD_SETS = ["Video - 15s", "Carousel - Bestsellers"]

GOOGLE_CAMPAIGNS = [  # (slug, name, id, channel type, share of cpc sessions, cpc USD)
    ("brand_exact", "KG | Brand | Exact", 20190001, "SEARCH", .40, .55),
    ("generic_apparel", "KG | Generic | Apparel", 20190002, "SEARCH", .25, 1.45),
    ("generic_drinkware", "KG | Generic | Drinkware", 20190003, "SEARCH", .15, 1.20),
    ("shopping_all", "KG | Shopping | All Products", 20190004, "SHOPPING", .20, .95),
]
PMAX_NEW_YEAR = ("pmax_new_year", "KG | PMax | New Year", 20260001, "PERFORMANCE_MAX")


def _seasonality(d: date) -> float:
    if d == config.BLACK_FRIDAY or d == config.CYBER_MONDAY:
        return 2.2
    if config.in_range(d, config.PROMO_WINDOW):
        return 1.6
    if date(2025, 12, 3) <= d <= date(2025, 12, 20):
        return 1.3
    if date(2025, 12, 21) <= d <= date(2025, 12, 31):
        return .7
    if d.month == 1:
        return .85
    return 1.0


def _weekday(d: date) -> float:
    return [1.0, 1.0, 1.0, 1.05, 1.1, 1.15, 1.05][d.weekday()]


def _backend_orders(orders: pd.DataFrame, utm_source: str) -> pd.DataFrame:
    """Daily backend orders + revenue per campaign slug, from first-version rows."""
    first = orders.sort_values("valid_from").drop_duplicates("order_id")
    first = first[first.utm_source == utm_source].copy()
    first["day"] = first.created_at.map(lambda t: t.date())
    return first.groupby(["day", "utm_campaign"]).agg(n=("order_id", "count"), rev=("total_usd", "sum"))


def build_meta(orders: pd.DataFrame, rng: np.random.Generator, out_dir: Path) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    backend = _backend_orders(orders, "facebook")
    manifest = []
    header = ["Reporting starts", "Reporting ends", "Account name", "Campaign name", "Ad set name", "Currency",
              "Amount spent", "Impressions", "Reach", "Link clicks", "Purchases", "Purchases conversion value"]

    def rows_for(d: date, maturity: float) -> list[list]:
        rows = []
        for slug, name, account, cur, base, start, end in META_CAMPAIGNS:
            if (start and d < start) or (end and d > end):
                continue
            n_backend, rev_backend = backend.loc[(d, slug)] if (d, slug) in backend.index else (0, 0.0)
            for ad_set in AD_SETS:
                spend_usd = base / len(AD_SETS) * _seasonality(d) * _weekday(d) * rng.lognormal(0, .12)
                cpm = 11.0 * (1.6 if config.in_range(d, config.META_CPM_SPIKE) else 1.0) \
                    * (1.35 if config.in_range(d, config.PROMO_WINDOW) else 1.0) * rng.lognormal(0, .08)
                impressions = int(spend_usd / cpm * 1000)
                # platform over-claims (view-through + modelled conversions); matures over days
                purchases = n_backend / len(AD_SETS) * rng.uniform(1.3, 1.7) * maturity
                rows.append([d.isoformat(), d.isoformat(), account, name, ad_set, cur,
                             f"{spend_usd * FX_PER_USD[cur]:.2f}", impressions,
                             int(impressions / rng.uniform(1.4, 1.9)), int(impressions * rng.normal(.011, .0015)),
                             round(purchases, 1),
                             f"{rev_backend / len(AD_SETS) * rng.uniform(1.3, 1.7) * maturity * FX_PER_USD[cur]:.2f}"])
        return rows

    for d in config.window_days():
        path = out_dir / f"meta_ads_{d.isoformat()}.csv"
        _write_csv(path, header, rows_for(d, maturity=.85))
        manifest.append(dict(source="meta_ads", path=path, delivered_on=d + timedelta(days=1)))
        if d.weekday() == 0 and d + timedelta(days=3) <= config.WINDOW_END:
            # weekly re-export of Monday after the attribution window matures → duplicate rows to dedupe
            path = out_dir / f"meta_ads_{d.isoformat()}_reexport.csv"
            _write_csv(path, header, rows_for(d, maturity=1.0))
            manifest.append(dict(source="meta_ads", path=path, delivered_on=d + timedelta(days=3)))
    return manifest


def build_google(events: pd.DataFrame, orders: pd.DataFrame, rng: np.random.Generator, out_dir: Path) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    sessions = session_sources(events)
    sessions = sessions[sessions.medium.fillna("").str.lower() == "cpc"]
    starts = events[events.event_name == "session_start"][["user_pseudo_id", "ga_session_id", "event_date"]]
    cpc_daily = sessions.merge(starts, on=["user_pseudo_id", "ga_session_id"]).groupby("event_date").size()
    backend = _backend_orders(orders, "google")

    header = ["date", "campaign_id", "campaign_name", "advertising_channel_type", "impressions", "clicks",
              "cost_micros", "conversions", "conversions_value"]
    manifest = []
    for d in config.window_days():
        cpc_sessions = int(cpc_daily.get(d, 0))
        rows = []
        for slug, name, cid, ctype, share, cpc in GOOGLE_CAMPAIGNS:
            clicks = max(int(cpc_sessions * share * rng.uniform(1.05, 1.25)), 0)  # clicks > sessions
            cost = clicks * cpc * rng.lognormal(0, .1)
            n_backend, rev_backend = backend.loc[(d, slug)] if (d, slug) in backend.index else (0, 0.0)
            rows.append([d.strftime("%m/%d/%Y"), cid, name, ctype, int(clicks / rng.uniform(.03, .07)), clicks,
                         int(cost * 1_000_000), round(n_backend * rng.uniform(1.1, 1.4), 2),
                         round(rev_backend * rng.uniform(1.1, 1.4), 2)])
        if d >= config.GOOGLE_SHOPPING_LAUNCH[0]:
            # story: new PMax campaign burns budget with almost no incremental traffic
            cost = 450 * rng.lognormal(0, .1)
            clicks = int(rng.integers(8, 25))
            rows.append([d.strftime("%m/%d/%Y"), PMAX_NEW_YEAR[2], PMAX_NEW_YEAR[1], PMAX_NEW_YEAR[3],
                         int(rng.integers(9000, 15000)), clicks, int(cost * 1_000_000),
                         round(rng.uniform(4, 9), 2), round(rng.uniform(300, 700), 2)])
        path = out_dir / f"google_ads_{d.isoformat()}.csv"
        _write_csv(path, header, rows)
        manifest.append(dict(source="google_ads", path=path, delivered_on=d + timedelta(days=1)))
    return manifest


def _write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
