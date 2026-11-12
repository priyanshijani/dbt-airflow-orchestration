"""Meta Ads, Google Ads, email and budget files on the S3 landing bucket -> raw.<family>___*.

Four independent tasks: a malformed export from one agency must not block the others.
"""
import pendulum
from airflow.sdk import dag, task

from dags._util import DEFAULT_ARGS, emit_if_new
from pipelines import assets


@dag(schedule="@hourly", start_date=pendulum.datetime(2025, 11, 1, tz="UTC"), catchup=False,
     max_active_runs=1, default_args=DEFAULT_ARGS,
     tags=["ingest", "files"], doc_md=__doc__)
def ingest_file_drops():
    def _load(family: str) -> dict:
        from pipelines import files  # heavy import stays out of DAG parsing

        return emit_if_new(files.run(family))

    @task(outlets=[assets.RAW_META_ADS])
    def meta_ads() -> dict:
        return _load("meta_ads")

    @task(outlets=[assets.RAW_GOOGLE_ADS])
    def google_ads() -> dict:
        return _load("google_ads")

    @task(outlets=[assets.RAW_EMAIL])
    def email() -> dict:
        return _load("email")

    @task(outlets=[assets.RAW_BUDGET])
    def budget() -> dict:
        return _load("budget")

    meta_ads()
    google_ads()
    email()
    budget()


ingest_file_drops()
