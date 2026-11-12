"""Advance the simulated clock by one day: new orders, status updates and files appear in the sources,
then the sources a new day touches are ingested straight away (ADR-020, ADR-024).
"""
import pendulum
from airflow.sdk import dag, task

from dags._ingest import DAILY_SOURCES, ingest_task


@dag(schedule=None, start_date=pendulum.datetime(2025, 11, 1, tz="UTC"), catchup=False,
     is_paused_upon_creation=False, max_active_runs=1, max_active_tasks=2,
     tags=["orchestration", "simulator"], doc_md=__doc__)
def simulator_advance_day():
    @task
    def advance() -> dict:
        from generators import release

        return release.release(next_day=True)

    advance() >> [ingest_task(name) for name in DAILY_SOURCES]


simulator_advance_day()
