"""Generate the whole Kestrel Goods universe into data/generated/ (seeded, reproducible).

    python -m generators.run

Writes:
  data/generated/shop/*.parquet          version histories of the OLTP tables
  data/generated/landing/<source>/*      files to deliver to the S3 landing bucket
  data/generated/landing/manifest.csv    which file is delivered on which simulated day
"""
import shutil

import numpy as np
import pandas as pd

from generators import ads, budget, config, email_events, ga4, shop


def main() -> None:
    rng = np.random.default_rng(config.SEED)
    if config.OUT_DIR.exists():
        shutil.rmtree(config.OUT_DIR)
    config.SHOP_DIR.mkdir(parents=True)

    events = ga4.load_events()
    purchases = ga4.purchases(events)
    products = shop.build_products(ga4.catalog_items(purchases), rng)
    tables = shop.build_orders(purchases, products, rng, config.SEED, email_events.campaigns())

    events_out, unsubs = email_events.build_events(tables["customers"], rng)
    tables["customers"] = _apply_unsubscribes(tables["customers"], unsubs)
    tables["products"] = products

    manifest = []
    manifest += email_events.write_files(events_out, config.LANDING_DIR / "email")
    manifest += ads.build_meta(tables["orders"], rng, config.LANDING_DIR / "meta_ads")
    manifest += ads.build_google(events, tables["orders"], rng, config.LANDING_DIR / "google_ads")
    manifest += budget.build(tables["orders"], tables["_order_channels"], rng, config.LANDING_DIR / "budget")

    for name, df in tables.items():
        if not name.startswith("_"):
            df.to_parquet(config.SHOP_DIR / f"{name}.parquet", index=False)
    m = pd.DataFrame(manifest)
    m["path"] = m["path"].map(lambda p: p.relative_to(config.LANDING_DIR).as_posix())
    m.sort_values(["delivered_on", "source", "path"]).to_csv(config.LANDING_DIR / "manifest.csv", index=False)

    _summary(tables, m, len(events_out))


def _apply_unsubscribes(customers: pd.DataFrame, unsubs: pd.DataFrame) -> pd.DataFrame:
    """Email unsubscribes flow back into the shop DB as a new customer version (cross-system consistency)."""
    if unsubs.empty:
        return customers
    key = customers.email.str.strip().str.lower()
    changed = customers.assign(email_key=key).merge(unsubs, on="email_key")
    changed = changed.assign(accepts_marketing=False, valid_from=changed.unsubscribed_at)
    return pd.concat([customers, changed[customers.columns]], ignore_index=True)


def _summary(tables: dict, manifest: pd.DataFrame, n_email: int) -> None:
    orders = tables["orders"].drop_duplicates("order_id", keep="last")
    print(f"customers   {tables['customers'].customer_id.nunique():>8,}")
    print(f"products    {tables['products'].product_id.nunique():>8,}")
    print(f"orders      {len(orders):>8,}   (versions: {len(tables['orders']):,})")
    print(f"order_items {len(tables['order_items']):>8,}")
    print(f"refunds     {len(tables['refunds']):>8,}")
    print(f"email evts  {n_email:>8,}")
    print("landing files by source:", manifest.groupby("source").size().to_dict())
    print("final order status mix:", orders.status.value_counts().to_dict())


if __name__ == "__main__":
    main()
