"""One task per source family, shared by the bootstrap and simulator DAGs (ADR-024).

Running ingestion as plain tasks inside one DAG run, two at a time, is far lighter than triggering four
other DAGs: fewer parsed files, fewer processes, and a memory ceiling the demo container can honour.
The scheduled ingest_* DAGs call the very same functions.
"""
import importlib
from datetime import timedelta

from airflow.sdk import task

from dags._util import emit_if_new
from pipelines import assets

# task_id, asset published when rows land, "module.function", arguments
SOURCES = {
    "shop": ("shop", assets.RAW_SHOP, "pipelines.shop.run", ()),
    "ga4": ("ga4", assets.RAW_GA4, "pipelines.ga4.run", ()),
    "meta_ads": ("meta_ads", assets.RAW_META_ADS, "pipelines.files.run", ("meta_ads",)),
    "google_ads": ("google_ads", assets.RAW_GOOGLE_ADS, "pipelines.files.run", ("google_ads",)),
    "email": ("email", assets.RAW_EMAIL, "pipelines.files.run", ("email",)),
    "budget": ("budget", assets.RAW_BUDGET, "pipelines.files.run", ("budget",)),
    "holidays": ("holidays", assets.RAW_HOLIDAYS, "pipelines.apis.run_holidays", ()),
    "weather": ("weather", assets.RAW_WEATHER, "pipelines.apis.run_weather", ()),
    "fred": ("fred", assets.RAW_FRED, "pipelines.apis.run_fred", ()),
}
DAILY_SOURCES = ["shop", "ga4", "meta_ads", "google_ads", "email", "weather"]  # what a new simulated day changes


def ingest_task(name: str):
    task_id, outlet, target, args = SOURCES[name]

    @task(task_id=f"ingest_{task_id}", outlets=[outlet], execution_timeout=timedelta(minutes=45))
    def run() -> dict:
        module, function = target.rsplit(".", 1)  # heavy imports stay out of DAG parsing
        return emit_if_new(getattr(importlib.import_module(module), function)(*args))

    return run()
