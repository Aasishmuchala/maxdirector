"""Model routing — pick the gateway wire format from the model id.

Opus 4.8 is proven on the Anthropic-compatible ``/v1/messages`` path (LightMatch runs on
it). GPT-5.5 *may* need the OpenAI-compatible ``/v1/chat/completions`` path through the
same Omega gateway. This module abstracts that so the rest of the plugin calls
``complete(...)`` without caring which model is selected. Phase-0 spike
``scripts/spike_provider_ping.py`` confirms which path GPT-5.5 needs; until then Opus 4.8
is the default. Same contract as omega.call: NO tools, non-streaming, retries; returns
reply TEXT (callers parse with ``omega.parse_json_from_text``).
"""

from __future__ import annotations

import json
import time

from . import omega
from .omega import BACKOFF_S, OmegaError, TIMEOUT_S

BASE = "https://omega.kesarcloud.in/v1"
CHAT_URL = f"{BASE}/chat/completions"

_ANTHROPIC_PREFIXES = ("claude", "opus", "sonnet", "haiku", "fable")
_OPENAI_PREFIXES = ("gpt", "o1", "o3", "o4")

DEFAULT_MODEL = omega.DEFAULT_MODEL


def wire_for(model: str) -> str:
    """'anthropic' or 'openai' for a model id; default anthropic (the proven path)."""
    m = (model or "").lower()
    if any(m.startswith(p) for p in _OPENAI_PREFIXES):
        return "openai"
    return "anthropic"


def _flatten(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(b.get("text", "") for b in content if isinstance(b, dict))
    return str(content)


def _openai_extract_text(payload: dict) -> str:
    choices = payload.get("choices") or []
    if not choices:
        return ""
    msg = choices[0].get("message") or {}
    return _flatten(msg.get("content")).strip()


def _openai_call(key, system, messages, model, max_tokens, post) -> str:
    if not key:
        raise OmegaError("No API key set — paste your oc_ key in MaxDirector's settings.", "auth")
    chat_messages = [{"role": "system", "content": system}]
    for m in messages:
        chat_messages.append({"role": m.get("role", "user"), "content": _flatten(m.get("content"))})
    body = json.dumps(
        {"model": model, "max_tokens": max_tokens, "stream": False, "messages": chat_messages}
    ).encode("utf-8")
    headers = {"content-type": "application/json", "authorization": f"Bearer {key}"}
    last = "gateway request failed"
    for attempt in range(len(BACKOFF_S) + 1):
        status = None
        text_body = ""
        try:
            status, text_body = post(CHAT_URL, headers, body, TIMEOUT_S)
        except Exception as e:  # noqa: BLE001
            last = f"network error: {e}"
        if status is not None:
            if status == 401:
                raise OmegaError("Gateway returned 401 — the API key is missing or invalid.", "auth")
            if 200 <= status < 300:
                try:
                    payload = json.loads(text_body)
                except ValueError:
                    payload = {}
                text = _openai_extract_text(payload)
                if text:
                    return text
                last = "the model returned no text"
            elif status == 429 or 500 <= status <= 599:
                last = f"gateway HTTP {status}"
            else:
                raise OmegaError(f"Gateway request failed: HTTP {status} — {text_body[:200]}", "other", text_body[:2000])
        if attempt < len(BACKOFF_S):
            time.sleep(BACKOFF_S[attempt])
    raise OmegaError(last, "network")


def _has_images(messages) -> bool:
    for m in messages:
        c = m.get("content")
        if isinstance(c, list) and any(isinstance(b, dict) and b.get("type") == "image" for b in c):
            return True
    return False


def complete(key, system, messages, model=DEFAULT_MODEL, max_tokens=8192, post=omega._default_post) -> str:
    """Route to the correct wire format for ``model`` and return the reply TEXT."""
    if wire_for(model) == "openai":
        # The OpenAI chat path flattens content to text — it would SILENTLY drop scout images
        # and gut the vision-first bet. Fail loud instead until image_url translation is wired.
        if _has_images(messages):
            raise OmegaError(
                f"{model} uses the OpenAI wire path, which can't carry scout images yet — "
                "use claude-opus-4-8 for the vision-first stages (DIRECT/COMPILE).", "other")
        return _openai_call(key, system, messages, model, max_tokens, post)
    return omega.call(key, system, messages, model=model, max_tokens=max_tokens, post=post)


def ping(key, model=DEFAULT_MODEL, post=omega._default_post) -> str:
    text = complete(
        key, "Reply with exactly the two characters: OK",
        [{"role": "user", "content": "ping"}], model=model, max_tokens=16, post=post,
    )
    return f"gateway reachable ({model}, {wire_for(model)}): {text.strip()[:24]!r}"
