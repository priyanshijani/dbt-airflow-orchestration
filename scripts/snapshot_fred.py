"""One-off: snapshot FRED series into data/samples/fred/ so the repo runs without a key (ADR-006).

    FRED_API_KEY=... python scripts/snapshot_fred.py
"""
import csv
import os
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "data" / "samples" / "fred" / "fred_observations.csv"

# Demand-side context for a US DTC brand (05_DATA_STRATEGY §3)
SERIES = {
    "UMCSENT": "University of Michigan consumer sentiment",
    "CPIAUCSL": "CPI, all urban consumers",
    "RSXFS": "Advance retail sales excluding food services",
}
START, END = "2025-01-01", "2026-06-30"


def fetch(series_id: str, api_key: str) -> list[dict]:
    resp = requests.get(
        "https://api.stlouisfed.org/fred/series/observations",
        params={
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "observation_start": START,
            "observation_end": END,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["observations"]


def main() -> None:
    api_key = os.environ["FRED_API_KEY"]
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["series_id", "series_name", "date", "value", "realtime_start"])
        for series_id, name in SERIES.items():
            for obs in fetch(series_id, api_key):
                writer.writerow([series_id, name, obs["date"], obs["value"], obs["realtime_start"]])
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
