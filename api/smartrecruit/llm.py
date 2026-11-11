"""Thin wrapper over an OpenAI-compatible chat API, with JSON output and retries."""
import base64
import json
import re
import threading
import time

from openai import OpenAI, RateLimitError

from . import config

_client = None


def client() -> OpenAI:
    global _client
    if _client is None:
        if not config.LLM_API_KEY:
            raise RuntimeError("LLM_API_KEY is not set (see .env.example)")
        _client = OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)
    return _client


def _parse_json(text: str) -> dict:
    text = text.strip()
    # Some models wrap JSON in ```json fences despite instructions
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object in model output: {text[:200]}")
    return json.loads(text[start:end + 1])


def chat_json(system: str, user: str, model: str | None = None, retries: int = 2) -> dict:
    """Send a system + user prompt and return the parsed JSON answer."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    return _call(messages, model or config.LLM_MODEL, retries)


def vision_json(system: str, text: str, png_pages: list[bytes], retries: int = 2) -> dict:
    """Same as chat_json, with page images attached to the user message."""
    content = [{"type": "text", "text": text}]
    for png in png_pages:
        b64 = base64.b64encode(png).decode()
        content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
    messages = [{"role": "system", "content": system}, {"role": "user", "content": content}]
    return _call(messages, config.VISION_MODEL, retries)


# models whose daily quota is used up in this process: skipped until restart
_exhausted: set[str] = set()
_local = threading.local()


def last_model() -> str:
    """The model that answered the last call in this thread (may be a fallback model)."""
    return getattr(_local, "model", config.LLM_MODEL)


def _is_daily_quota(e: RateLimitError) -> bool:
    text = str(getattr(e, "body", "")) + str(e)
    return "per day" in text.lower() or "PerDay" in text


def _call(messages: list, model: str, retries: int) -> dict:
    """Try the model, then the fallback models (LLM_FALLBACK_MODELS) when a daily quota is exhausted."""
    candidates = [m for m in [model, *config.LLM_FALLBACK_MODELS] if m not in _exhausted] or [model]
    last_error = None
    for current in candidates:
        try:
            out = _call_one(messages, current, max(retries, 3))
            _local.model = current
            return out
        except RateLimitError as e:
            last_error = e
            if _is_daily_quota(e):
                _exhausted.add(current)  # no point retrying today: move to the next model
                continue
            raise RuntimeError(f"LLM rate limit on {current}: {e}") from e
    raise RuntimeError(f"All models are out of quota ({', '.join(candidates)}): {last_error}")


def _call_one(messages: list, model: str, retries: int) -> dict:
    last_error = None
    for attempt in range(retries + 1):
        try:
            resp = client().chat.completions.create(
                model=model,
                messages=messages,
                temperature=config.LLM_TEMPERATURE,
                response_format={"type": "json_object"},
            )
            return _parse_json(resp.choices[0].message.content or "")
        except (ValueError, json.JSONDecodeError) as e:
            # Invalid JSON: ask again, reminding the model of the format
            last_error = e
            messages = messages + [{"role": "user", "content": "Your last answer was not valid JSON. Answer again with one JSON object only."}]
        except RateLimitError as e:
            if _is_daily_quota(e) or attempt == retries:
                raise
            # per-minute limit: wait for the window to reset
            last_error = e
            time.sleep(20 * (attempt + 1))
        except Exception as e:  # network errors, 503 "high demand"
            last_error = e
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"LLM call failed after {retries + 1} attempts on {model}: {last_error}")
