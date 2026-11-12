"""Helpers shared by the ingestion DAGs."""
from datetime import timedelta

from airflow.sdk.exceptions import AirflowSkipException

DEFAULT_ARGS = {
    "owner": "analytics-engineering",
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
    "retry_exponential_backoff": True,
}


def emit_if_new(result: dict) -> dict:
    """Skip (so no Asset event is emitted) when a run loaded nothing: downstream only reacts to real change."""
    if result["rows"] == 0:
        raise AirflowSkipException(f"{result['status']}: no new rows, no asset event")
    return result
