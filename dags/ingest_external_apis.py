"""Public holidays, weather and FRED macro data -> raw.holidays___*, raw.weather___*, raw.fred___*."""
import pendulum
from airflow.sdk import dag, task

from dags._util import DEFAULT_ARGS, emit_if_new
from pipelines import assets


@dag(schedule="@daily", start_date=pendulum.datetime(2025, 11, 1, tz="UTC"), catchup=False,
     max_active_runs=1, default_args=DEFAULT_ARGS,
     tags=["ingest", "api"], doc_md=__doc__)
def ingest_external_apis():
    @task(outlets=[assets.RAW_HOLIDAYS])
    def holidays() -> dict:
        from pipelines import apis  # heavy import stays out of DAG parsing

        return emit_if_new(apis.run_holidays())

    @task(outlets=[assets.RAW_WEATHER])
    def weather() -> dict:
        from pipelines import apis

        return emit_if_new(apis.run_weather())

    @task(outlets=[assets.RAW_FRED])
    def fred() -> dict:
        from pipelines import apis

        return emit_if_new(apis.run_fred())

    holidays()
    weather()
    fred()


ingest_external_apis()
