"""Synthetic GA4-shaped events, used for tests/CI and before the real sample exists.

Mirrors the schema produced by pipelines/ga4/ga4_events.sql. Not used in the demo:
the committed real sample is (ADR-006).

    python -m generators.ga4_fixture [--out PATH]
"""
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from generators import config

CATALOG = [
    ("GGOEGAAX0001", "Google Navy Speckled Tee", "Apparel", 24.0),
    ("GGOEGAAX0002", "Google Crewneck Sweatshirt Grey", "Apparel", 44.0),
    ("GGOEGDHX0003", "Google Campus Bike Tumbler", "Drinkware", 18.0),
    ("GGOEGDHX0004", "YouTube Insulated Water Bottle", "Drinkware", 22.0),
    ("GGOEGBRX0005", "Android Everyday Backpack", "Bags", 58.0),
    ("GGOEGOAX0006", "Google Sticker Sheet", "Office", 4.0),
    ("GGOEGHGX0007", "Chrome Dino Beanie", "Apparel", 18.0),
    ("GGOEGLFX0008", "Google Kids Puzzle", "Lifestyle", 16.0),
]
SOURCES = [("google", "organic", "(organic)"), ("(direct)", "(none)", "(direct)"),
           ("google", "cpc", "<Other>"), ("<Other>", "referral", "(referral)"),
           ("(data deleted)", "(data deleted)", "(data deleted)")]
SOURCE_P = [0.38, 0.25, 0.12, 0.13, 0.12]


def build(n_sessions_per_day: int = 250, seed: int = config.SEED) -> pa.Table:
    rng = np.random.default_rng(seed)
    start = config.WINDOW_START - timedelta(days=config.GA4_SHIFT_DAYS)
    rows = []
    for d in range((config.WINDOW_END - config.WINDOW_START).days + 1):
        day = datetime.combine(start + timedelta(days=d), datetime.min.time(), tzinfo=timezone.utc)
        for s in range(n_sessions_per_day):
            user = f"{rng.integers(1e9)}.{rng.integers(1e9)}"
            sid = int(day.timestamp()) + s
            src, med, camp = SOURCES[rng.choice(len(SOURCES), p=SOURCE_P)]
            ts = day + timedelta(seconds=int(rng.integers(0, 86_000)))
            base = dict(user_pseudo_id=user,
                        device={"category": rng.choice(["desktop", "mobile", "tablet"], p=[.55, .42, .03]),
                                "operating_system": "Web", "browser": "Chrome"},
                        geo={"country": "United States", "region": "California", "city": "San Jose"},
                        traffic_source={"source": src, "medium": med, "name": camp},
                        user_first_touch_timestamp=int(ts.timestamp() * 1e6))
            funnel = ["session_start", "view_item"]
            if rng.random() < .12: funnel.append("add_to_cart")
            if len(funnel) > 2 and rng.random() < .5: funnel.append("begin_checkout")
            if len(funnel) > 3 and rng.random() < .35: funnel.append("purchase")
            for i, ev in enumerate(funnel):
                params = [{"key": "ga_session_id", "string_value": None, "int_value": sid, "double_value": None}]
                if ev == "session_start":
                    params += [{"key": k, "string_value": v, "int_value": None, "double_value": None}
                               for k, v in (("source", src), ("medium", med), ("campaign", camp))]
                items = []
                if ev == "purchase":
                    for idx in rng.choice(len(CATALOG), size=int(rng.integers(1, 4)), replace=False):
                        iid, name, cat, price = CATALOG[idx]
                        qty = int(rng.integers(1, 3))
                        items.append({"item_id": iid, "item_name": name, "item_category": cat,
                                      "price_in_usd": price, "quantity": qty, "item_revenue_in_usd": price * qty})
                rows.append(dict(base, event_date=(ts.date()).strftime("%Y%m%d"),
                                 event_timestamp=int((ts + timedelta(seconds=30 * i)).timestamp() * 1e6),
                                 event_name=ev, event_params=params,
                                 ecommerce={"transaction_id": f"T{sid}" if items else None,
                                            "purchase_revenue_in_usd": sum(x["item_revenue_in_usd"] for x in items) or None,
                                            "total_item_quantity": sum(x["quantity"] for x in items) or None},
                                 items=items))
    return pa.Table.from_pylist(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=config.GA4_SAMPLE)
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    table = build()
    pq.write_table(table, args.out, compression="zstd")
    print(f"wrote {table.num_rows:,} fixture events -> {args.out}")


if __name__ == "__main__":
    main()
