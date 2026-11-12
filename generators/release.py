"""Release generated data into the source systems up to a simulated date (ADR-020).

    python -m generators.release                     # initial load: through INITIAL_RELEASE_THROUGH
    python -m generators.release --through 2026-01-25
    python -m generators.release --next-day          # advance the simulated clock by one day

- Postgres `shop`: upserts the latest version of every row with valid_from <= cutoff, so
  `updated_at` advances exactly like a live application database.
- S3 landing bucket: uploads every file whose delivered_on <= cutoff.
- The clock is stored at s3://<bucket>/_control/sim_clock.json; GA4 ingestion reads it.

Idempotent: re-running for the same date changes nothing.
"""
import argparse
import json
import os
from datetime import date, datetime, time, timedelta, timezone

import pandas as pd
import psycopg2
import s3fs
from psycopg2.extras import execute_values

from generators import config

TABLES = [  # (table, primary key) in foreign-key order
    ("customers", "customer_id"),
    ("products", "product_id"),
    ("orders", "order_id"),
    ("order_items", "order_item_id"),
    ("refunds", "refund_id"),
]
CLOCK_KEY = "_control/sim_clock.json"


def _s3() -> s3fs.S3FileSystem:
    return s3fs.S3FileSystem(key=os.environ["S3_ACCESS_KEY"], secret=os.environ["S3_SECRET_KEY"],
                             client_kwargs={"endpoint_url": os.getenv("S3_ENDPOINT_URL", "http://localhost:8333")})


def _bucket() -> str:
    return os.getenv("S3_BUCKET", "landing")


def read_clock(fs: s3fs.S3FileSystem) -> date | None:
    path = f"{_bucket()}/{CLOCK_KEY}"
    if not fs.exists(path):
        return None
    return date.fromisoformat(json.loads(fs.cat(path))["released_through"])


def release_postgres(cutoff: date) -> dict[str, int]:
    end = datetime.combine(cutoff, time.max, tzinfo=timezone.utc)
    conn = psycopg2.connect(host=os.getenv("POSTGRES_HOST", "localhost"), dbname="shop",
                            user=os.environ["SHOP_DB_USER"], password=os.environ["SHOP_DB_PASSWORD"])
    counts = {}
    with conn, conn.cursor() as cur:
        for table, pk in TABLES:
            df = pd.read_parquet(config.SHOP_DIR / f"{table}.parquet")
            df = df[df.valid_from <= end].sort_values("valid_from").drop_duplicates(pk, keep="last")
            df = df.rename(columns={"valid_from": "updated_at"})
            df = df.astype(object).where(df.notna(), None)
            cols = list(df.columns)
            updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c != pk)
            execute_values(cur, f"""
                INSERT INTO {table} ({", ".join(cols)}) VALUES %s
                ON CONFLICT ({pk}) DO UPDATE SET {updates}
                WHERE {table}.updated_at < EXCLUDED.updated_at
            """, df.itertuples(index=False, name=None), page_size=1000)
            counts[table] = len(df)
    conn.close()
    return counts


def release_files(fs: s3fs.S3FileSystem, cutoff: date) -> int:
    manifest = pd.read_csv(config.LANDING_DIR / "manifest.csv", parse_dates=["delivered_on"])
    due = manifest[manifest.delivered_on.dt.date <= cutoff]
    if not fs.exists(_bucket()):
        fs.mkdir(_bucket())
    uploaded = 0
    for rel in due.path:
        target = f"{_bucket()}/{rel}"
        if not fs.exists(target):
            fs.put(str(config.LANDING_DIR / rel), target)
            uploaded += 1
    return uploaded


def release(through: date | None = None, next_day: bool = False) -> dict:
    """Release data into the sources. Used by the CLI below and by the bootstrap / simulator DAGs."""
    fs = _s3()
    if next_day:
        current = read_clock(fs) or config.INITIAL_RELEASE_THROUGH
        cutoff = current + timedelta(days=1)
    else:
        cutoff = through or config.INITIAL_RELEASE_THROUGH
    if cutoff > config.WINDOW_END:
        raise ValueError(f"Simulation window ends {config.WINDOW_END}; nothing left to release.")

    counts = release_postgres(cutoff)
    uploaded = release_files(fs, cutoff)
    fs.pipe(f"{_bucket()}/{CLOCK_KEY}", json.dumps({"released_through": cutoff.isoformat()}).encode())
    return {"released_through": cutoff.isoformat(), "postgres_rows": counts, "new_landing_files": uploaded}


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--through", type=date.fromisoformat)
    group.add_argument("--next-day", action="store_true")
    args = parser.parse_args()
    try:
        print(release(args.through, args.next_day))
    except ValueError as exc:
        raise SystemExit(str(exc))


if __name__ == "__main__":
    main()
