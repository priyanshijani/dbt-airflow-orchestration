"""Provider-agnostic LLM client with run modes and cost caps (ADR-015, ADR-017).

AI_MODE: live = call the model, mock = no API call (the caller supplies a deterministic stand-in), off = skip.
Unset: live if a key for LLM_PROVIDER exists, else mock. Only Gemini is wired in; Anthropic is a later adapter.
"""
import json
import os
import re
import time
from dataclasses import dataclass, field


class AgentDisabled(RuntimeError):
    pass


@dataclass
class Result:
    data: dict
    mode: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    notes: list = field(default_factory=list)


def resolve_mode() -> str:
    mode = os.getenv("AI_MODE", "").strip().lower()
    if mode in {"live", "mock", "off"}:
        return mode
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    key = os.getenv("GEMINI_API_KEY" if provider == "gemini" else "ANTHROPIC_API_KEY", "").strip()
    return "live" if key else "mock"


def _est_tokens(text: str) -> int:
    return len(text) // 4


def generate_json(system: str, prompt: str, mock_fn, task: str = "narrator") -> Result:
    """One structured call. mock_fn() returns the dict a model would, used in mock mode."""
    mode = resolve_mode()
    if mode == "off":
        raise AgentDisabled("AI_MODE=off")
    if mode == "mock":
        return Result(mock_fn(), "mock", "rule-based-mock")

    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    if provider != "gemini":
        raise NotImplementedError(f"LLM_PROVIDER={provider}: only gemini is implemented so far")
    model = os.getenv("LLM_MODEL_REASONING", "").strip()
    if not model:
        raise RuntimeError("Set LLM_MODEL_REASONING in .env to a model your Gemini key can use (see ADR-017)")
    max_in = int(os.getenv("AI_MAX_INPUT_TOKENS", "50000"))
    if _est_tokens(system + prompt) > max_in:
        raise RuntimeError(f"prompt is about {_est_tokens(system + prompt)} tokens, over AI_MAX_INPUT_TOKENS={max_in}")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    config = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        max_output_tokens=int(os.getenv("AI_MAX_OUTPUT_TOKENS", "4000")),
        temperature=0.2,
    )
    delay, last = 4.0, None
    for attempt in range(4):  # exponential backoff on 429 / transient errors (free-tier quotas)
        try:
            resp = client.models.generate_content(model=model, contents=prompt, config=config)
            text = (resp.text or "").strip()
            text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
            usage = resp.usage_metadata
            return Result(json.loads(text), "live", model,
                          getattr(usage, "prompt_token_count", 0) or 0,
                          getattr(usage, "candidates_token_count", 0) or 0)
        except Exception as e:  # noqa: BLE001 - provider SDK raises many types
            last = e
            retryable = "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e) or "503" in str(e) or isinstance(e, json.JSONDecodeError)
            if not retryable or attempt == 3:
                break
            time.sleep(delay)
            delay *= 2
    raise RuntimeError(f"LLM call failed after retries: {type(last).__name__}") from last
