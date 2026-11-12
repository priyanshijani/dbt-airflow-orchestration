"""File drops on the S3 landing bucket -> raw.<source>___<table> (Meta Ads, Google Ads, email, budget).

Raw means as delivered:
- CSV columns stay text, because dlt's timestamp auto-detection is switched off. dbt staging does the typing.
- JSONL keeps its structure; nested objects flatten into `profile__email`, `properties__campaign_id`, ...
- every row carries `_source_file`, so staging can dedupe re-exports and pick the latest budget version.
- each file loads exactly once: dlt tracks the newest file modification time it has seen.
"""
import csv
import io
import json
import os
from collections.abc import Iterator

import dlt
from dlt.sources.credentials import AwsCredentials
from dlt.sources.filesystem import FileItemDict, filesystem

from pipelines import common


def _credentials() -> AwsCredentials:
    return AwsCredentials(
        aws_access_key_id=os.environ["S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["S3_SECRET_KEY"],
        endpoint_url=os.environ["S3_ENDPOINT_URL"],
    )


def _files(glob: str):
    resource = filesystem(bucket_url=f"s3://{common.bucket()}", file_glob=glob, credentials=_credentials())
    resource.apply_hints(incremental=dlt.sources.incremental("modification_date"))
    return resource


@dlt.transformer(standalone=True)
def read_csv_text(items: Iterator[FileItemDict]):
    for file_obj in items:
        with file_obj.open() as handle:
            for row in csv.DictReader(io.TextIOWrapper(handle, encoding="utf-8-sig")):
                row["_source_file"] = file_obj["file_name"]
                yield row


@dlt.transformer(standalone=True)
def read_jsonl_rows(items: Iterator[FileItemDict]):
    for file_obj in items:
        with file_obj.open() as handle:
            for line in io.TextIOWrapper(handle, encoding="utf-8"):
                if line.strip():
                    row = json.loads(line)
                    row["_source_file"] = file_obj["file_name"]
                    yield row


@dlt.transformer(standalone=True)
def read_budget_workbook(items: Iterator[FileItemDict]):
    """Finance's layout is a title row, merged month headers over Budget/Target sub-columns, and a notes column.

    A sheet is not a table, so the layout is flattened here into one row per channel x month x metric.
    Cell values are untouched; staging maps finance's channel labels to ours.
    """
    from openpyxl import load_workbook

    metrics = {"budget": "budget_usd", "revenue target": "revenue_target_usd"}
    for file_obj in items:
        with file_obj.open() as handle:
            sheet = load_workbook(handle, data_only=True).active
        month_row, metric_row = 3, 4
        month_by_col, last_month = {}, None
        for col in range(2, sheet.max_column + 1):
            last_month = sheet.cell(row=month_row, column=col).value or last_month  # merged cells: only the first holds the value
            month_by_col[col] = last_month
        for r in range(metric_row + 1, sheet.max_row + 1):
            channel = sheet.cell(row=r, column=1).value
            if not channel:
                continue
            for col, month in month_by_col.items():
                label = str(sheet.cell(row=metric_row, column=col).value or "").lower()
                metric = next((m for key, m in metrics.items() if key in label), None)
                value = sheet.cell(row=r, column=col).value
                if metric and value is not None:
                    yield {"channel_label": channel, "month_label": month, "metric": metric,
                           "value": value, "sheet_row": r, "_source_file": file_obj["file_name"]}


@dlt.source(name="files")
def file_sources():
    # raw stays as delivered: no automatic "this looks like a timestamp" conversion
    dlt.current.source_schema().remove_type_detection("iso_timestamp")
    return [
        (_files("meta_ads/*.csv") | read_csv_text).with_name("meta_ads_daily"),
        (_files("google_ads/*.csv") | read_csv_text).with_name("google_ads_daily"),
        (_files("email/*.jsonl") | read_jsonl_rows).with_name("email_events"),
        (_files("budget/*.xlsx") | read_budget_workbook).with_name("budget_monthly"),
    ]


# Each family loads through its own dlt pipeline, so a break in one export does not block the others
FAMILIES = {
    "meta_ads": ["meta_ads_daily"],
    "google_ads": ["google_ads_daily"],
    "email": ["email_events"],
    "budget": ["budget_monthly"],
}


def run(family: str) -> dict:
    fs = common.s3()
    if not fs.exists(common.bucket()):
        return common.log_skipped(family, "landing bucket does not exist yet")
    selected = file_sources().with_resources(*FAMILIES[family])
    # one pipeline name per family keeps incremental state independent
    return common.run_pipeline(family, selected, mode="live")
