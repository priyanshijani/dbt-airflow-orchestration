"""Smoke test: every Insights Hub page runs end to end against the live ClickHouse without raising.

Run inside the hub container: docker compose exec insights-hub python -m insights_hub.tests.test_pages
"""
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
PAGES = [ROOT / "home.py", *sorted((ROOT / "pages").glob("*.py"))]


def main() -> int:
    failed = 0
    for page in PAGES:
        at = AppTest.from_file(str(page), default_timeout=60).run()
        errors = [e.value for e in at.exception] + [e.body for e in at.error]
        status = "FAIL" if at.exception else "ok"
        failed += bool(at.exception)
        print(f"{status:4} {page.name}: {len(at.metric)} metrics, {len(at.dataframe)} tables, "
              f"{len(at.get('plotly_chart'))} charts" + (f"\n     {errors}" if errors else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
