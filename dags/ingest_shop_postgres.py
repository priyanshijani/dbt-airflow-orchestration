"""Store database -> raw.shop___*. Hourly, incremental on updated_at, publishes RAW_SHOP when rows land."""
import pendulum
from airflow.sdk import dag, task

from dags._util import DEFAULT_ARGS, emit_if_new
from pipelines import assets


@dag(schedule="@hourly", start_date=pendulum.datetime(2025, 11, 1, tz="UTC"), catchup=False,
     max_active_runs=1, default_args=DEFAULT_ARGS,
     tags=["ingest", "postgres"], doc_md=__doc__)
def ingest_shop_postgres():
    @task(outlets=[assets.RAW_SHOP])
    def load() -> dict:
        from pipelines import shop  # heavy import stays out of DAG parsing

        return emit_if_new(shop.run())

    load()


ingest_shop_postgres()
