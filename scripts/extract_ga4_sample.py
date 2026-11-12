"""One-off: extract the committed GA4 sample from BigQuery into data/samples/ga4/.

The committed Parquet file is what makes the repo run without GCP keys (ADR-006).
Re-run only to change the extract shape.

    python scripts/extract_ga4_sample.py --profile          # event counts + bytes scanned, no download
    python scripts/extract_ga4_sample.py                    # write data/samples/ga4/ga4_events.parquet

Needs GCP_PROJECT_ID and GOOGLE_APPLICATION_CREDENTIALS (service account with BigQuery Job User).
"""
import argparse
import os
from pathlib import Path

import pyarrow.parquet as pq
from google.cloud import bigquery

ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "pipelines" / "ga4" / "ga4_events.sql"
OUT_PATH = ROOT / "data" / "samples" / "ga4" / "ga4_events.parquet"

DEFAULT_EVENTS = [
    "session_start", "first_visit", "view_item", "add_to_cart",
    "begin_checkout", "add_shipping_info", "add_payment_info", "purchase",
]


def query_params(events: list[str], sample_pct: int) -> list:
    return [
        bigquery.ScalarQueryParameter("start_suffix", "STRING", "20201101"),
        bigquery.ScalarQueryParameter("end_suffix", "STRING", "20210131"),
        bigquery.ArrayQueryParameter("event_names", "STRING", events),
        bigquery.ScalarQueryParameter("sample_pct", "INT64", sample_pct),
    ]


def profile(client: bigquery.Client, sample_pct: int) -> None:
    sql = f"SELECT event_name, COUNT(*) AS n FROM ({SQL_PATH.read_text()}) GROUP BY 1 ORDER BY 2 DESC"
    cfg = bigquery.QueryJobConfig(query_parameters=query_params(DEFAULT_EVENTS, sample_pct))
    dry = client.query(sql, job_config=bigquery.QueryJobConfig(dry_run=True, query_parameters=cfg.query_parameters))
    print(f"bytes to scan: {dry.total_bytes_processed / 1e9:.2f} GB")
    for row in client.query(sql, job_config=cfg).result():
        print(f"{row.event_name:<20} {row.n:>10,}")


def extract(client: bigquery.Client, events: list[str], sample_pct: int) -> None:
    cfg = bigquery.QueryJobConfig(query_parameters=query_params(events, sample_pct))
    table = client.query(SQL_PATH.read_text(), job_config=cfg).to_arrow(create_bqstorage_client=False)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, OUT_PATH, compression="zstd", compression_level=9)
    print(f"wrote {table.num_rows:,} rows -> {OUT_PATH} ({OUT_PATH.stat().st_size / 1e6:.1f} MB)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--sample-pct", type=int, default=100)
    parser.add_argument("--events", nargs="+", default=DEFAULT_EVENTS)
    args = parser.parse_args()

    client = bigquery.Client(project=os.environ["GCP_PROJECT_ID"])
    if args.profile:
        profile(client, args.sample_pct)
    else:
        extract(client, args.events, args.sample_pct)


if __name__ == "__main__":
    main()
