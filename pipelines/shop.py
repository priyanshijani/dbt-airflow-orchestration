"""Store database (Postgres OLTP) -> raw.shop___<table>.

Incremental on `updated_at`, append-only. Each source table lands as a ReplacingMergeTree keyed by its
primary key and versioned by updated_at, so a row that changes status is simply inserted again and
ClickHouse keeps the newest version at merge time (ADR-004). Exact reads use FINAL / argMax downstream.
"""
import os
from datetime import datetime, timezone

import dlt
from dlt.destinations.adapters import clickhouse_adapter
from dlt.sources.sql_database import sql_table

from pipelines import common

SOURCE = "shop"
TABLES = {  # table -> primary key
    "customers": "customer_id",
    "products": "product_id",
    "orders": "order_id",
    "order_items": "order_item_id",
    "refunds": "refund_id",
}


def _url() -> str:
    return (f"postgresql+psycopg2://{os.environ['SHOP_DB_USER']}:{os.environ['SHOP_DB_PASSWORD']}"
            f"@{os.getenv('POSTGRES_HOST', 'postgres')}:5432/shop")


@dlt.source(name=SOURCE)
def shop_source():
    resources = []
    for table, pk in TABLES.items():
        resource = sql_table(
            credentials=_url(),
            table=table,
            schema="public",
            incremental=dlt.sources.incremental(
                "updated_at", initial_value=datetime(2000, 1, 1, tzinfo=timezone.utc)),
            backend="sqlalchemy",
            chunk_size=5000,
            reflection_level="full_with_precision",
        )
        resource.apply_hints(
            write_disposition="append",
            primary_key=pk,
            columns={"updated_at": {"name": "updated_at", "dedup_sort": "desc"}},
        )
        clickhouse_adapter(resource, table_engine_type="replacing_merge_tree", sort=[pk])
        resources.append(resource)
    return resources


def run() -> dict:
    return common.run_pipeline(SOURCE, shop_source(), mode="live")
