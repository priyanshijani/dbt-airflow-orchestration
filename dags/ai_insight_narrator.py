"""Weekly AI brief: explains why revenue moved in the latest complete week (Insight Narrator, ADR-028).

Runs Monday 06:00 UTC, or on demand from the Insights Hub ("Generate now"). The week comes from the data, not the
wall clock, so it works with the simulated clock too. It skips if a brief for that week already exists, unless
`force` is set. AI_MODE (mock | live | off) decides whether a model is called (ADR-015).
"""
import pendulum
from airflow.sdk import Param, dag, task

from dags._util import DEFAULT_ARGS


@dag(schedule="0 6 * * 1", start_date=pendulum.datetime(2025, 11, 1, tz="UTC"), catchup=False,
     is_paused_upon_creation=True, max_active_runs=1, default_args={**DEFAULT_ARGS, "retries": 1},
     params={"force": Param(False, type="boolean", description="Regenerate even if a brief exists for the week"),
             "week": Param("", type="string", description="Monday of the week (YYYY-MM-DD); blank = latest complete week")},
     tags=["ai", "narrator"], doc_md=__doc__)
def ai_insight_narrator():
    @task
    def narrate(params=None) -> dict:
        from agents.narrator import run

        return run.run(week=(params or {}).get("week") or None, force=bool((params or {}).get("force")))

    narrate()


ai_insight_narrator()
