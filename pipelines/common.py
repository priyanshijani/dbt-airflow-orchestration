"""Shared plumbing for every ingestion pipeline (ADR-005, ADR-022).

- one dlt pipeline per source, all landing in ClickHouse database `raw` as `<source>___<table>`
- every run is logged to meta.ingestion_log (success, skipped or failed)
- schema changes reported by dlt are logged to meta.schema_changes for the drift agent
- the simulated clock (ADR-020) tells time-aware sources how far data has been "released"
"""
import json
import os
from datetime import date, datetime, timezone

import clickhouse_connect
import dlt
import s3fs

RAW_DB = "raw"
CLOCK_KEY = "_control/sim_clock.json"

META_DDL = [
    """
    CREATE TABLE IF NOT EXISTS meta.ingestion_log (
        load_id      String,
        source       LowCardinality(String),
        mode         LowCardinality(String),
        status       LowCardinality(String),
        rows_loaded  UInt64,
        started_at   DateTime64(3, 'UTC'),
        finished_at  DateTime64(3, 'UTC'),
        error        String
    ) ENGINE = MergeTree ORDER BY (source, started_at)
    """,
    """
    CREATE TABLE IF NOT EXISTS meta.schema_changes (
        detected_at  DateTime64(3, 'UTC'),
        source       LowCardinality(String),
        table_name   String,
        change_type  LowCardinality(String),
        column_name  String,
        column_type  String,
        load_id      String
    ) ENGINE = MergeTree ORDER BY (detected_at, source)
    """,
]


def ch_client():
    return clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "clickhouse"),
        username="etl_writer",
        password=os.environ["CLICKHOUSE_ETL_PASSWORD"],
    )


def destination():
    return dlt.destinations.clickhouse(credentials={
        "host": os.getenv("CLICKHOUSE_HOST", "clickhouse"),
        "port": 9000,
        "http_port": 8123,
        "database": RAW_DB,
        "username": "etl_writer",
        "password": os.environ["CLICKHOUSE_ETL_PASSWORD"],
        "secure": 0,
    })


def s3() -> s3fs.S3FileSystem:
    return s3fs.S3FileSystem(
        key=os.environ["S3_ACCESS_KEY"],
        secret=os.environ["S3_SECRET_KEY"],
        client_kwargs={"endpoint_url": os.environ["S3_ENDPOINT_URL"]},
    )


def bucket() -> str:
    return os.getenv("S3_BUCKET", "landing")


def released_through() -> date | None:
    """Simulated 'today' (ADR-020). None until the first release has happened."""
    fs, path = s3(), f"{bucket()}/{CLOCK_KEY}"
    if not fs.exists(path):
        return None
    return date.fromisoformat(json.loads(fs.cat(path))["released_through"])


def ensure_meta_tables() -> None:
    client = ch_client()
    for ddl in META_DDL:
        client.command(ddl)


def run_pipeline(source: str, data, *, mode: str = "live", **run_kwargs) -> dict:
    """Run one dlt pipeline and write its outcome to meta.ingestion_log.

    Returns {"status", "rows", "load_id"}. Failures are logged, then re-raised so Airflow marks the task failed.
    """
    ensure_meta_tables()
    pipeline = dlt.pipeline(pipeline_name=f"dtc_{source}", destination=destination(), dataset_name=source)
    started = datetime.now(timezone.utc)
    load_id, rows, error = "", 0, ""
    try:
        info = pipeline.run(data, **run_kwargs)
        load_id = ",".join(info.loads_ids)
        # nothing extracted (e.g. no new files) means the normalize step never ran, so there is no info to read
        normalized = pipeline.last_trace.last_normalize_info
        counts = normalized.row_counts if normalized else {}
        rows = sum(n for table, n in counts.items() if not table.startswith("_dlt"))
        _log_schema_changes(source, info)
        status = "success" if rows else "no_new_data"
    except Exception as exc:
        status, error = "failed", f"{type(exc).__name__}: {exc}"[:2000]
        log_run(source, mode, status, 0, started, load_id, error)
        raise
    log_run(source, mode, status, rows, started, load_id, error)
    return {"status": status, "rows": rows, "load_id": load_id}


def log_skipped(source: str, reason: str, mode: str = "n/a") -> dict:
    """Record that a run had nothing to do (e.g. no data released yet)."""
    ensure_meta_tables()
    now = datetime.now(timezone.utc)
    log_run(source, mode, "skipped", 0, now, "", reason)
    return {"status": "skipped", "rows": 0, "load_id": ""}


def log_run(source, mode, status, rows, started, load_id, error) -> None:
    ch_client().insert(
        "meta.ingestion_log",
        [[load_id, source, mode, status, rows, started, datetime.now(timezone.utc), error]],
        column_names=["load_id", "source", "mode", "status", "rows_loaded", "started_at", "finished_at", "error"],
    )


def _log_schema_changes(source: str, info) -> None:
    """dlt reports only what changed in each load package (new tables, new columns). Never drops: that is by design."""
    rows = []
    now = datetime.now(timezone.utc)
    for package in info.load_packages:
        for table, spec in (package.schema_update or {}).items():
            if table.startswith("_dlt"):  # dlt's own bookkeeping tables are not source schema
                continue
            columns = {c: d for c, d in (spec.get("columns") or {}).items() if not c.startswith("_dlt")}
            is_new_table = "_dlt_load_id" in (spec.get("columns") or {})
            for column, definition in columns.items():
                rows.append([now, source, table, "table_created" if is_new_table else "column_added",
                             column, str(definition.get("data_type", "")), package.load_id])
    if rows:
        ch_client().insert(
            "meta.schema_changes", rows,
            column_names=["detected_at", "source", "table_name", "change_type", "column_name", "column_type", "load_id"],
        )
