"""Offline tests for the Insight Narrator: no database, no API key, no cost (AI_MODE=mock).

    python -m unittest agents.tests.test_narrator -v

The fake data reproduces two planted stories (generators/STORIES.md): #4 Google spend up with no traffic,
#5 payment outage (shop orders fall while GA4 purchases look normal).
"""
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

os.environ["AI_MODE"] = "mock"

from agents.core import tools  # noqa: E402
from agents.narrator import brief, detect, run as narrator  # noqa: E402

WEEK = "2026-01-19"
D0 = date.fromisoformat(WEEK)


def fake_run(sql: str):
    if "max(week_start)" in sql:
        return [{"w": WEEK}]
    if "from marts.mart_kpi_daily where" in sql and "group by period" in sql:
        return [dict(period="this_week", orders=500, new_customers=200, revenue_usd=40000.0, sessions=20000, spend_usd=14000.0),
                dict(period="prior_week", orders=700, new_customers=260, revenue_usd=56000.0, sessions=20500, spend_usd=9000.0)]
    if "mart_revenue_bridge" in sql:
        return [dict(channel="paid_search", revenue_usd=9000.0, prior_revenue_usd=19000.0, change_usd=-10000.0,
                     volume_effect_usd=-9000.0, price_effect_usd=-1000.0),
                dict(channel="email", revenue_usd=12000.0, prior_revenue_usd=13000.0, change_usd=-1000.0,
                     volume_effect_usd=-900.0, price_effect_usd=-100.0)]
    if "mart_channel_performance" in sql:
        return [dict(channel="paid_search", period="this_week", sessions=5000, clicks=3000, orders=120, new_customers=60,
                     revenue_usd=9000.0, spend_usd=7000.0),
                dict(channel="paid_search", period="prior_week", sessions=5100, clicks=3100, orders=260, new_customers=90,
                     revenue_usd=19000.0, spend_usd=3500.0)]
    if "fct_sessions" in sql:  # GA4 purchases stay ~100/day; shop orders collapse for two days
        shop = [72, 71, 70, 69, 30, 28, 70]
        return [dict(report_date=(D0 + timedelta(i)).isoformat(), ga4_purchases=85, shop_orders=shop[i]) for i in range(7)]
    if "from marts.mart_kpi_daily where" in sql:
        return [dict(report_date=(D0 + timedelta(i - 7)).isoformat(), orders=100, revenue_usd=8000.0, sessions=3000, spend_usd=1300.0)
                for i in range(14)]
    raise AssertionError(f"unexpected query: {sql[:80]}")


class FakeWriter:
    def __init__(self, existing=0):
        self.inserts, self.existing = [], existing

    def insert(self, table, rows, column_names=None):
        self.inserts.append((table, rows))

    def query(self, *_a, **_k):
        return type("R", (), {"result_rows": [[self.existing]]})()


class SqlGuard(unittest.TestCase):
    def test_allows_select_on_marts_and_adds_limit(self):
        self.assertTrue(tools.check_select("select 1 from marts.mart_kpi_daily").endswith("LIMIT 500"))
        tools.check_select("with a as (select 1 from marts.fct_orders) select * from a")

    def test_rejects_writes_other_schemas_and_multi_statements(self):
        for bad in ["drop table marts.x", "select * from raw.shop_orders", "select 1; select 2",
                    "select * from marts.x into outfile 'f'", "insert into marts.x values (1)",
                    "select * from url('http://x', CSV)"]:
            with self.assertRaises(tools.UnsafeQuery, msg=bad):
                tools.check_select(bad)


class Detection(unittest.TestCase):
    def setUp(self):
        self.week, self.evidence = detect.fetch_evidence(fake_run)
        self.signals = detect.find_signals(self.evidence)
        self.kinds = {s["kind"] for s in self.signals}

    def test_finds_planted_stories(self):
        self.assertEqual(self.week, WEEK)
        self.assertIn("spend_without_traffic", self.kinds)  # story 4
        self.assertIn("backend_gap", self.kinds)            # story 5
        gap = next(s for s in self.signals if s["kind"] == "backend_gap")
        self.assertEqual(gap["days"], [(D0 + timedelta(4)).isoformat(), (D0 + timedelta(5)).isoformat()])

    def test_headline_numbers_come_from_data(self):
        head = self.signals[0]
        self.assertEqual((head["revenue_usd"], head["change_usd"]), (40000.0, -16000.0))


class Verification(unittest.TestCase):
    def setUp(self):
        _, self.evidence = detect.fetch_evidence(fake_run)
        self.signals = detect.find_signals(self.evidence)
        self.pool = detect.numeric_pool(self.evidence, self.signals)
        self.ids = {e["id"] for e in self.evidence}

    def test_mock_brief_passes_its_own_verification(self):
        from agents.narrator import mock

        checked = brief.verify(mock.draft(self.signals), self.ids, self.pool)
        self.assertTrue(checked["verification"]["passed"], checked["verification"]["notes"])
        self.assertGreaterEqual(len(checked["drivers"]), 3)

    def test_hallucinated_drivers_are_dropped(self):
        draft = dict(headline="Revenue fell", summary="", watch_items=[], caveats=[], drivers=[
            dict(title="Invented", direction="down", impact_usd=None, explanation="Lost $123,456 to a competitor.", evidence=["E2"]),
            dict(title="No proof", direction="down", impact_usd=None, explanation="Something happened.", evidence=[]),
            dict(title="Real", direction="down", impact_usd=-10000.0, explanation="Paid search lost $10,000.", evidence=["E2"]),
        ])
        checked = brief.verify(draft, self.ids, self.pool)
        self.assertEqual([d["title"] for d in checked["drivers"]], ["Real"])
        self.assertFalse(checked["verification"]["passed"])
        self.assertEqual(len(checked["verification"]["notes"]), 2)


class EndToEnd(unittest.TestCase):
    def test_run_writes_brief_log_and_markdown(self):
        writer = FakeWriter()
        with tempfile.TemporaryDirectory() as tmp:
            out = narrator.run(run_query=fake_run, writer=writer, reports_dir=Path(tmp))
            self.assertEqual((out["status"], out["mode"], out["verified"]), ("success", "mock", True))
            text = (Path(tmp) / f"weekly_brief_{WEEK}.md").read_text(encoding="utf-8")
            self.assertIn("Orders dropped while web analytics still saw purchases", text)
        self.assertEqual([t for t, _ in writer.inserts], ["ai.briefs", "ai.agent_runs"])

    def test_weekly_gate_skips_when_brief_exists(self):
        out = narrator.run(run_query=fake_run, writer=FakeWriter(existing=1))
        self.assertEqual(out["status"], "skipped")


if __name__ == "__main__":
    unittest.main()
