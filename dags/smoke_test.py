"""Phase 1 smoke test: proves Airflow can reach every backing service.

Trigger it manually after `docker compose up`. All three tasks green means the
stack is wired correctly.
"""
import os

import pendulum
from airflow.sdk import dag, task


@dag(schedule=None, start_date=pendulum.datetime(2025, 11, 1, tz="UTC"), catchup=False, tags=["infra"])
def smoke_test():
    @task
    def check_clickhouse() -> str:
        import clickhouse_connect

        client = clickhouse_connect.get_client(
            host="clickhouse", username="etl_writer", password=os.environ["CLICKHOUSE_ETL_PASSWORD"]
        )
        dbs = {r[0] for r in client.query("SELECT name FROM system.databases").result_rows}
        missing = {"raw", "staging", "intermediate", "marts", "meta", "ai"} - dbs
        assert not missing, f"missing databases: {missing}"
        return client.command("SELECT version()")

    @task
    def check_shop_postgres() -> list[str]:
        from airflow.providers.postgres.hooks.postgres import PostgresHook

        rows = PostgresHook(postgres_conn_id="shop_postgres").get_records(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY 1"
        )
        tables = [r[0] for r in rows]
        assert {"customers", "orders", "order_items", "products", "refunds"} <= set(tables), tables
        return tables

    @task
    def check_s3_landing() -> list[str]:
        import s3fs

        fs = s3fs.S3FileSystem(
            key=os.environ["S3_ACCESS_KEY"],
            secret=os.environ["S3_SECRET_KEY"],
            client_kwargs={"endpoint_url": os.environ["S3_ENDPOINT_URL"]},
        )
        bucket = os.environ.get("S3_BUCKET", "landing")
        if not fs.exists(bucket):
            fs.mkdir(bucket)
        return fs.ls(bucket)

    check_clickhouse()
    check_shop_postgres()
    check_s3_landing()


smoke_test()
