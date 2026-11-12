"""GA4 events -> raw.ga4___events. Live from BigQuery when GCP credentials exist, else the committed sample."""
import pendulum
from airflow.sdk import dag, task

from dags._util import DEFAULT_ARGS, emit_if_new
from pipelines import assets


@dag(schedule="@daily", start_date=pendulum.datetime(2025, 11, 1, tz="UTC"), catchup=False,
     max_active_runs=1, default_args=DEFAULT_ARGS,
     tags=["ingest", "bigquery"], doc_md=__doc__)
def ingest_ga4():
    @task(outlets=[assets.RAW_GA4], execution_timeout=pendulum.duration(minutes=30))
    def load() -> dict:
        from pipelines import ga4  # heavy import stays out of DAG parsing

        return emit_if_new(ga4.run())

    load()


ingest_ga4()
