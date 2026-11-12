"""Insight Narrator: detect (SQL) -> explain (LLM or mock) -> verify -> render -> persist.

    python -m agents.narrator.run [--week 2026-01-12] [--force]

Reads marts as agent_reader (read-only); writes ai.briefs, ai.agent_runs and reports/*.md as ai_writer.
"""
import argparse
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from agents.core import llm, tools
from agents.narrator import brief, detect, mock, prompts

DDL = [
    """CREATE TABLE IF NOT EXISTS ai.briefs (
        brief_id String, week_start Date, created_at DateTime, mode String, model String,
        verified UInt8, headline String, brief_json String, markdown String
    ) ENGINE = MergeTree ORDER BY (week_start, created_at)""",
    """CREATE TABLE IF NOT EXISTS ai.agent_runs (
        run_id String, agent String, started_at DateTime, seconds Float32, mode String, model String,
        input_tokens UInt32, output_tokens UInt32, status String, error String
    ) ENGINE = MergeTree ORDER BY started_at""",
]


def ai_writer():
    import clickhouse_connect

    client = clickhouse_connect.get_client(
        host=os.getenv("CLICKHOUSE_HOST", "clickhouse"), username="ai_writer",
        password=os.getenv("CLICKHOUSE_AI_WRITER_PASSWORD", ""), autogenerate_session_id=False)
    for stmt in DDL:
        client.command(stmt)
    return client


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def run(week: str | None = None, force: bool = False, run_query=None, writer=None, reports_dir: Path | None = None) -> dict:
    run_query = run_query or tools.make_runner()
    writer = writer or ai_writer()
    started, t0, run_id = _now(), time.time(), uuid.uuid4().hex[:12]
    mode, model, tokens = llm.resolve_mode(), "", (0, 0)

    def log(status: str, error: str = ""):
        writer.insert("ai.agent_runs", [[run_id, "narrator", started, round(time.time() - t0, 2), mode, model,
                                         tokens[0], tokens[1], status, error[:500]]],
                      column_names=["run_id", "agent", "started_at", "seconds", "mode", "model",
                                    "input_tokens", "output_tokens", "status", "error"])

    try:
        if mode == "off":
            log("skipped", "AI_MODE=off")
            return dict(status="skipped", reason="AI_MODE=off")
        week, evidence = detect.fetch_evidence(run_query, week)
        if not force:
            have = writer.query("select count() from ai.briefs where week_start = {w:Date} and mode = {m:String}",
                                parameters={"w": week, "m": mode}).result_rows[0][0]
            if have:
                log("skipped", f"brief for {week} already exists")
                return dict(status="skipped", reason=f"brief for week {week} already exists", week=week)
        signals = detect.find_signals(evidence)
        pool = detect.numeric_pool(evidence, signals)

        result = llm.generate_json(prompts.SYSTEM, prompts.user_prompt(week, evidence, signals),
                                   mock_fn=lambda: mock.draft(signals))
        mode, model, tokens = result.mode, result.model, (result.input_tokens, result.output_tokens)
        checked = brief.verify(result.data, {e["id"] for e in evidence}, pool)
        checked["evidence"] = evidence  # kept so the Hub can show the proof behind each claim
        markdown = brief.render(checked, week, dict(model=model, mode=mode))

        writer.insert("ai.briefs", [[uuid.uuid4().hex[:12], datetime.strptime(week, "%Y-%m-%d").date(), _now(), mode, model,
                                     int(checked["verification"]["passed"]), checked["headline"],
                                     json.dumps(checked, default=str), markdown]],
                      column_names=["brief_id", "week_start", "created_at", "mode", "model", "verified", "headline",
                                    "brief_json", "markdown"])
        out_dir = reports_dir or Path(os.getenv("PROJECT_ROOT", ".")) / "reports"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"weekly_brief_{week}.md"
        path.write_text(markdown, encoding="utf-8")
        log("success")
        return dict(status="success", week=week, mode=mode, model=model, verified=checked["verification"]["passed"],
                    drivers=len(checked["drivers"]), report=str(path))
    except Exception as e:  # noqa: BLE001 - record any failure, then let Airflow see it
        log("failed", f"{type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", help="Monday of the week to explain; default: latest complete week")
    ap.add_argument("--force", action="store_true", help="regenerate even if a brief exists")
    a = ap.parse_args()
    print(json.dumps(run(week=a.week, force=a.force), indent=2, default=str))
