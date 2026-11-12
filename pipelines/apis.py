"""Public REST APIs -> raw.holidays___*, raw.weather___*, raw.fred___* (ADR-006 fallbacks included).

- Nager.Date public holidays: no key
- Open-Meteo historical weather: no key, loaded up to the simulated date
- FRED macro series: live with FRED_API_KEY, otherwise the committed snapshot in data/samples/fred/
"""
import csv
import os
from datetime import date, timedelta

import dlt
import requests

from generators import config
from pipelines import common

HOLIDAY_YEARS = (2025, 2026)
HOLIDAY_COUNTRIES = ("US", "GB")
CITIES = {  # name: (lat, lon, country): where the brand's demand sits
    "New York": (40.71, -74.01, "US"),
    "Los Angeles": (34.05, -118.24, "US"),
    "Chicago": (41.88, -87.63, "US"),
    "Austin": (30.27, -97.74, "US"),
    "London": (51.51, -0.13, "GB"),
}
FRED_SERIES = {
    "UMCSENT": "University of Michigan consumer sentiment",
    "CPIAUCSL": "CPI, all urban consumers",
    "RSXFS": "Advance retail sales excluding food services",
}
FRED_SNAPSHOT = config.ROOT / "data" / "samples" / "fred" / "fred_observations.csv"


def _get(url: str, **params) -> requests.Response:
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response


# ── holidays ────────────────────────────────────────────────────────────────

@dlt.resource(name="public_holidays", write_disposition="replace")
def holidays():
    for year in HOLIDAY_YEARS:
        for country in HOLIDAY_COUNTRIES:
            yield from _get(f"https://date.nager.at/api/v3/PublicHolidays/{year}/{country}").json()


# ── weather ─────────────────────────────────────────────────────────────────

@dlt.resource(name="daily", write_disposition="append", primary_key=("city", "date"))
def weather(through: date, cursor=dlt.sources.incremental(
        "date", initial_value=(config.WINDOW_START - timedelta(days=1)).isoformat())):
    """Only fetches days after the last one loaded, up to the simulated date (incremental, ADR-020)."""
    start = date.fromisoformat(cursor.last_value) + timedelta(days=1)
    if start > through:
        return
    for city, (lat, lon, country) in CITIES.items():
        body = _get("https://archive-api.open-meteo.com/v1/archive", latitude=lat, longitude=lon,
                    start_date=start.isoformat(), end_date=through.isoformat(), timezone="UTC",
                    daily="temperature_2m_max,temperature_2m_min,precipitation_sum").json()["daily"]
        for i, day in enumerate(body["time"]):
            yield {"city": city, "country": country, "date": day,
                   "temp_max_c": body["temperature_2m_max"][i], "temp_min_c": body["temperature_2m_min"][i],
                   "precipitation_mm": body["precipitation_sum"][i]}


# ── FRED ────────────────────────────────────────────────────────────────────

def fred_mode() -> str:
    return "live" if os.getenv("FRED_API_KEY") else "snapshot"


@dlt.resource(name="observations", write_disposition="replace")
def fred():
    if fred_mode() == "live":
        for series_id, name in FRED_SERIES.items():
            body = _get("https://api.stlouisfed.org/fred/series/observations", series_id=series_id,
                        api_key=os.environ["FRED_API_KEY"], file_type="json",
                        observation_start="2025-01-01", observation_end="2026-06-30").json()
            for obs in body["observations"]:
                yield {"series_id": series_id, "series_name": name, "date": obs["date"], "value": obs["value"],
                       "realtime_start": obs["realtime_start"]}
    else:
        with FRED_SNAPSHOT.open(newline="", encoding="utf-8") as handle:
            yield from csv.DictReader(handle)


# ── entry points ────────────────────────────────────────────────────────────

def run_holidays() -> dict:
    return common.run_pipeline("holidays", holidays())


def run_weather() -> dict:
    through = common.released_through()
    if through is None:
        return common.log_skipped("weather", "no data released yet (simulated clock not started)")
    return common.run_pipeline("weather", weather(through))


def run_fred() -> dict:
    return common.run_pipeline("fred", fred(), mode=fred_mode())
