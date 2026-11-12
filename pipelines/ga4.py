"""GA4 events -> raw.ga4___events, from BigQuery (live) or the committed Parquet sample (ADR-006).

Unlike the other sources this does NOT go through dlt (ADR-023). GA4 is 1.1M rows of nested structs; moving
that through Python took over 30 minutes on the demo container (dlt schema inference per row, then pyarrow
decode alone ~2 min). ClickHouse reads Parquet natively, so the file is POSTed to its HTTP interface and
parsed server-side, filtered by the simulated clock as it goes. Nested fields keep their native types
(`Array(Tuple(...))`), which dbt staging unnests with array functions.

Both paths use the same extract shape (pipelines/ga4/ga4_events.sql). Raw dates stay in the original 2020-21
calendar; the dbt `ga4_date_shift` macro moves them into the simulation window (ADR-020).
"""
import io
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import requests

from generators import config
from pipelines import common

SOURCE = "ga4"
TABLE = "raw.ga4___events"
SQL_PATH = config.ROOT / "pipelines" / "ga4" / "ga4_events.sql"
EVENTS = ["session_start", "first_visit", "view_item", "add_to_cart", "begin_checkout",
          "add_shipping_info", "add_payment_info", "purchase"]
FIRST_SUFFIX_EXCLUSIVE = "20201031"
KEY_TYPES = {  # top-level columns used in ORDER BY must be non-nullable
    "event_date": "String", "event_timestamp": "Int64",
    "event_name": "LowCardinality(String)", "user_pseudo_id": "String",
}


def mode() -> str:
    """GA4_SOURCE=sample|live forces a path; the default (auto) goes live only when BigQuery credentials exist."""
    forced = os.getenv("GA4_SOURCE", "auto").lower()
    if forced in ("sample", "live"):
        return forced
    creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    return "live" if os.getenv("GCP_PROJECT_ID") and creds and Path(creds).exists() else "sample"


def _unshift(day: date) -> str:
    """Simulated date -> the original GA4 date it corresponds to, as a table suffix."""
    return (day - timedelta(days=config.GA4_SHIFT_DAYS)).strftime("%Y%m%d")


def _ch_type(t: pa.DataType) -> str:
    if pa.types.is_struct(t):
        return "Tuple(" + ", ".join(f"`{f.name}` {_ch_type(f.type)}" for f in t) + ")"
    if pa.types.is_list(t) or pa.types.is_large_list(t):
        return f"Array({_ch_type(t.value_type)})"
    if pa.types.is_string(t) or pa.types.is_large_string(t):
        return "Nullable(String)"
    if pa.types.is_integer(t):
        return "Nullable(Int64)"
    if pa.types.is_floating(t) or pa.types.is_decimal(t):
        return "Nullable(Float64)"
    if pa.types.is_boolean(t):
        return "Nullable(Bool)"
    raise TypeError(f"no ClickHouse mapping for Arrow type {t}")


def _structure(schema: pa.Schema) -> str:
    return ", ".join(f"`{f.name}` {KEY_TYPES.get(f.name, _ch_type(f.type))}" for f in schema)


def _ensure_table(client, schema: pa.Schema) -> None:
    client.command(f"""
        CREATE TABLE IF NOT EXISTS {TABLE} (
            {_structure(schema)},
            `_loaded_at`   DateTime64(3, 'UTC') DEFAULT now64(3),
            `_source_file` LowCardinality(String)
        ) ENGINE = MergeTree
        PARTITION BY substring(event_date, 1, 6)
        ORDER BY (event_date, event_name, user_pseudo_id, event_timestamp)
    """)


def _insert_parquet(data: bytes, schema: pa.Schema, after: str, upto: str, source_file: str) -> None:
    """ClickHouse parses the Parquet bytes itself and keeps only days in (after, upto]."""
    query = (f"INSERT INTO {TABLE} ({', '.join(f'`{f.name}`' for f in schema)}, `_source_file`) "
             f"SELECT *, '{source_file}' FROM input('{_structure(schema)}') "
             f"WHERE event_date > '{after}' AND event_date <= '{upto}' FORMAT Parquet")
    response = requests.post(
        f"http://{os.getenv('CLICKHOUSE_HOST', 'clickhouse')}:8123/",
        params={"query": query, "user": "etl_writer", "password": os.environ["CLICKHOUSE_ETL_PASSWORD"],
                "input_format_null_as_default": 1,
                # small blocks and few threads: nested Parquet decode must fit the 1 GB default query memory cap
                "max_threads": 2, "input_format_parquet_max_block_size": 20000,
                "max_insert_block_size": 100000, "min_insert_block_size_rows": 100000},
        data=data, timeout=900)
    if response.status_code != 200:
        raise RuntimeError(f"ClickHouse rejected the GA4 insert: {response.text[:800]}")


def _live_pages(after: str, upto: str):
    from google.cloud import bigquery, bigquery_storage

    client = bigquery.Client(project=os.environ["GCP_PROJECT_ID"])
    # the extract SQL filters on BETWEEN; GA4 days are whole, so "after the last loaded day" = next suffix
    start = (date.fromisoformat(f"{after[:4]}-{after[4:6]}-{after[6:]}") + timedelta(days=1)).strftime("%Y%m%d")
    job = client.query(SQL_PATH.read_text(), job_config=bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("start_suffix", "STRING", start),
        bigquery.ScalarQueryParameter("end_suffix", "STRING", upto),
        bigquery.ArrayQueryParameter("event_names", "STRING", EVENTS),
        bigquery.ScalarQueryParameter("sample_pct", "INT64", 100),
    ]))
    # the Storage Read API streams columnar data in bulk; plain REST paging takes hours for nested rows
    # (needs the "BigQuery Read Session User" role on the service account)
    reader = bigquery_storage.BigQueryReadClient(credentials=client._credentials)
    for page in job.result().to_arrow_iterable(bqstorage_client=reader):
        yield pa.Table.from_batches([page]) if isinstance(page, pa.RecordBatch) else page


def run() -> dict:
    through = common.released_through()
    if through is None:
        return common.log_skipped(SOURCE, "no data released yet (simulated clock not started)")

    common.ensure_meta_tables()
    client = common.ch_client()
    source_mode, upto = mode(), _unshift(through)
    started = datetime.now(timezone.utc)
    try:
        if source_mode == "sample":
            schema = pq.read_schema(config.GA4_SAMPLE)
            _ensure_table(client, schema)
        # the table itself is the cursor: newest day already loaded (days load whole, so strictly after it)
        after = client.command(f"SELECT max(event_date) FROM {TABLE}") if client.command(
            f"EXISTS TABLE {TABLE}") else ""
        after = str(after) if after and str(after) != "0" else FIRST_SUFFIX_EXCLUSIVE
        before = client.command(f"SELECT count() FROM {TABLE}") if after != FIRST_SUFFIX_EXCLUSIVE else 0

        if source_mode == "sample":
            _insert_parquet(Path(config.GA4_SAMPLE).read_bytes(), schema, after, upto, "ga4_events.parquet")
        else:
            for n, page in enumerate(_live_pages(after, upto)):
                if n == 0:
                    schema = page.schema
                    _ensure_table(client, schema)
                buffer = io.BytesIO()
                pq.write_table(page, buffer)
                _insert_parquet(buffer.getvalue(), schema, after, upto, "bigquery")
        rows = int(client.command(f"SELECT count() FROM {TABLE}")) - int(before)
    except Exception as exc:
        # all-or-nothing: the table's newest date is the cursor, so a half-loaded run must not leave rows behind
        try:
            client.command(f"ALTER TABLE {TABLE} DELETE WHERE _loaded_at >= toDateTime64('{started:%Y-%m-%d %H:%M:%S}', 3, 'UTC') "
                           "SETTINGS mutations_sync = 1")
        except Exception:
            pass
        common.log_run(SOURCE, source_mode, "failed", 0, started, "", f"{type(exc).__name__}: {exc}"[:2000])
        raise
    status = "success" if rows else "no_new_data"
    common.log_run(SOURCE, source_mode, status, rows, started, "", "")
    return {"status": status, "rows": rows, "load_id": ""}
