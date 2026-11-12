"""First load, end to end: generate the universe (if absent), release the first 78 days, ingest all nine sources.

Trigger once after `docker compose up`. dbt joins this chain in Phase 3.
"""
import pendulum
from airflow.sdk import dag, task

from dags._ingest import SOURCES, ingest_task


@dag(schedule=None, start_date=pendulum.datetime(2025, 11, 1, tz="UTC"), catchup=False,
     is_paused_upon_creation=False, max_active_runs=1, max_active_tasks=2,
     tags=["orchestration"], doc_md=__doc__)
def bootstrap():
    @task
    def generate() -> str:
        from generators import config, run

        if (config.LANDING_DIR / "manifest.csv").exists():
            return "seed data already present"
        run.main()
        return "generated"

    @task
    def release() -> dict:
        from generators import release as release_mod

        return release_mod.release()

    generate() >> release() >> [ingest_task(name) for name in SOURCES]


bootstrap()
