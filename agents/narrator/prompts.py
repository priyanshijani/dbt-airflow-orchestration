"""Compact, stable prompt (kept short for free-tier quotas, ADR-017)."""
import json

SYSTEM = """You are the weekly revenue analyst for a direct-to-consumer brand. Write for a busy business owner: plain English, no jargon.
You get an evidence pack (E1..E5) and deterministic findings (S1..). Explain why revenue moved.
Rules:
- Use ONLY numbers that appear in the evidence or findings. Never calculate new ones. Never invent causes.
- Every driver must cite evidence ids (E1..E5) that prove it. If the evidence cannot explain something, say so in caveats.
- Say what the data shows, and what to check next. Do not claim certainty about causes the data cannot show.
- Be brief: headline one sentence, summary 2 sentences max, each driver explanation 1-2 sentences, at most 5 drivers.
Return only JSON."""

SCHEMA_HINT = {
    "headline": "one sentence with the revenue change",
    "summary": "two sentences max",
    "drivers": [{"title": "short", "direction": "up|down|flat", "impact_usd": "number from evidence or null",
                 "explanation": "1-2 sentences", "evidence": ["E2"]}],
    "watch_items": ["what to check next"],
    "caveats": ["limits of the data"],
}


def user_prompt(week: str, evidence: list[dict], signals: list[dict]) -> str:
    return json.dumps({"week_start": week, "evidence": evidence, "findings": signals,
                       "return_json_shaped_like": SCHEMA_HINT}, default=str, separators=(",", ":"))
