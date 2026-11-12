"""Read the GA4 sample and expose what the synthetic shop needs: purchases, items, sessions.

The shop is *derived from* GA4 so web behaviour and orders tell one coherent story:
every tracked order corresponds to a real GA4 purchase session (dates shifted, ADR-018).
"""
from datetime import timedelta
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from generators import config


def _param(params, key: str):
    for p in params if params is not None else []:
        if p["key"] == key:
            return p["int_value"] if p["int_value"] is not None else p["string_value"]
    return None


def load_events(path: Path = config.GA4_SAMPLE) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"GA4 sample not found at {path}. Run scripts/extract_ga4_sample.py "
            "(needs GCP keys) or `python -m generators.ga4_fixture` for a synthetic stand-in."
        )
    cols = ["event_timestamp", "event_name", "user_pseudo_id", "event_params",
            "device", "geo", "traffic_source", "ecommerce", "items"]
    # only these two event types feed the shop and ad generators; skipping the other ~1M funnel events
    # keeps generation fast and within the Airflow container's memory limit
    df = pq.read_table(path, columns=cols,
                       filters=[("event_name", "in", ["purchase", "session_start"])]).to_pandas()
    df["ga_session_id"] = df["event_params"].map(lambda p: _param(p, "ga_session_id"))
    shifted = pd.to_datetime(df["event_timestamp"], unit="us", utc=True) + timedelta(days=config.GA4_SHIFT_DAYS)
    df["event_ts"] = shifted
    df["event_date"] = shifted.dt.date
    return df


def session_sources(events: pd.DataFrame) -> pd.DataFrame:
    """Session-scoped source/medium/campaign, taken from session_start params (user-scoped fallback)."""
    starts = events[events["event_name"] == "session_start"].copy()
    starts["source"] = starts["event_params"].map(lambda p: _param(p, "source"))
    starts["medium"] = starts["event_params"].map(lambda p: _param(p, "medium"))
    starts["campaign"] = starts["event_params"].map(lambda p: _param(p, "campaign"))
    fallback = starts["traffic_source"].map(lambda t: t or {})
    starts["source"] = starts["source"].fillna(fallback.map(lambda t: t.get("source")))
    starts["medium"] = starts["medium"].fillna(fallback.map(lambda t: t.get("medium")))
    starts["campaign"] = starts["campaign"].fillna(fallback.map(lambda t: t.get("name")))
    return (starts[["user_pseudo_id", "ga_session_id", "source", "medium", "campaign"]]
            .drop_duplicates(["user_pseudo_id", "ga_session_id"]))


def purchases(events: pd.DataFrame) -> pd.DataFrame:
    p = events[events["event_name"] == "purchase"].copy()
    p = p.merge(session_sources(events), on=["user_pseudo_id", "ga_session_id"], how="left")
    p["device_category"] = p["device"].map(lambda d: (d or {}).get("category"))
    p["country"] = p["geo"].map(lambda g: (g or {}).get("country"))
    p["region"] = p["geo"].map(lambda g: (g or {}).get("region"))
    p["city"] = p["geo"].map(lambda g: (g or {}).get("city"))
    p["items"] = p["items"].map(lambda xs: [dict(x) for x in xs] if xs is not None else [])
    # obfuscated rows sometimes carry no items; the shop can't sell nothing
    p = p[p["items"].map(len) > 0]
    p = p[(p["event_date"] >= config.WINDOW_START) & (p["event_date"] <= config.WINDOW_END)]
    text_cols = ["source", "medium", "campaign", "device_category", "country", "region", "city"]
    # real GA4 has sessions with no source/medium; pandas stores those as NaN floats, so make them None
    p[text_cols] = p[text_cols].astype(object).where(p[text_cols].notna(), None)
    keep = ["event_ts", "event_date", "user_pseudo_id", "ga_session_id", *text_cols, "items"]
    return p[keep].sort_values("event_ts").reset_index(drop=True)


def catalog_items(purchase_rows: pd.DataFrame) -> pd.DataFrame:
    rows = [item for items in purchase_rows["items"] for item in items]
    items = pd.DataFrame(rows)
    items = items[items["item_id"].notna() & items["price_in_usd"].notna() & (items["price_in_usd"] > 0)]
    return (items.groupby("item_id")
                 .agg(item_name=("item_name", "first"),
                      item_category=("item_category", "first"),
                      price_usd=("price_in_usd", "median"))
                 .reset_index())
