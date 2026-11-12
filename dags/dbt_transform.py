"""dbt project -> Airflow tasks with Cosmos: each seed, model and its tests becomes a task.

Triggered by Assets, not a clock: it runs when any raw source family has published new rows (see
pipelines/assets.py). Ingestion skips when nothing changed, so dbt only rebuilds when data actually moved.
Cosmos' own parser reads the project files (no `dbt ls` at parse time, which is slow on a laptop).
"""
import pendulum
from cosmos import DbtDag, ExecutionConfig, ProfileConfig, ProjectConfig, RenderConfig
from cosmos.constants import LoadMode, TestBehavior

from dags._util import DEFAULT_ARGS
from pipelines import assets

DBT_PROJECT = "/opt/project/dbt"

# daily sources, any of which moving is a reason to rebuild; static ones (holidays, FRED) ride along
TRIGGERS = (assets.RAW_SHOP | assets.RAW_GA4 | assets.RAW_META_ADS | assets.RAW_GOOGLE_ADS
            | assets.RAW_EMAIL | assets.RAW_BUDGET | assets.RAW_WEATHER)

dbt_transform = DbtDag(
    dag_id="dbt_transform",
    project_config=ProjectConfig(DBT_PROJECT),
    profile_config=ProfileConfig(
        profile_name="dtc_growth", target_name="dev", profiles_yml_filepath=f"{DBT_PROJECT}/profiles.yml"
    ),
    execution_config=ExecutionConfig(dbt_executable_path="/opt/airflow/dbt-venv/bin/dbt"),
    render_config=RenderConfig(load_method=LoadMode.CUSTOM, test_behavior=TestBehavior.AFTER_ALL),
    operator_args={"install_deps": False},
    schedule=TRIGGERS,
    start_date=pendulum.datetime(2025, 11, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    max_active_tasks=2,
    default_args=DEFAULT_ARGS,
    tags=["dbt", "transform"],
)
