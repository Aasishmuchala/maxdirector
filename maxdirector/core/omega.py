"""Omega gateway client — the plugin's single LLM network surface.

Ported verbatim (contract-wise) from LightMatch's proven client. The hard-won wire
contract, verified live against the real gateway:
  - NO tools / tool_choice (the gateway 500s on them) — the JSON schema is embedded
    in the system prompt and the reply is parsed out of the TEXT blocks;
  - non-streaming; Bearer key; anthropic-version header;
  - retries with backoff on 429/5xx; ~120s wall-clock ceiling per attempt;
  - multimodal via image blocks (used by the reference-similarity + framing loops).

This module is one of only two allowed to touch the network (the other is
``core.assets`` for the Poly Haven asset API); a test enforces that ``core`` imports no
pymxs, and network calls are funnelled here so they can be mocked wholesale in tests.
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional

GATEWAY_URL = "https://omega.kesarcloud.in/v1/messages"
TIMEOUT_S = 120
BACKOFF_S = (2.0, 6.0, 15.0)
DEFAULT_MODEL = "claude-opus-4-8"


class OmegaError(RuntimeError):
    def __init__(self, message: str, kind: str = "other", raw: str = ""):
        super().__init__(message)
        self.kind = kind
        self.raw = raw


def extract_text(payload: dict) -> str:
    blocks = payload.get("content") or []
    return "\n".join(
        b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"
    ).strip()


def parse_json_from_text(text: str) -> Optional[dict]:
    """First balanced top-level {...} object in the reply. The model is told to output
    ONLY the JSON, but thinking spill / stray prose must not break parsing."""
    start = text.find("{")
    while start != -1:
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[start : i + 1])
                        if isinstance(obj, dict):
                            return obj
                    except json.JSONDecodeError:
                        break
                    break
        start = text.find("{", start + 1)
    return None


def _default_post(url: str, headers: dict, body: bytes, timeout: int) -> tuple[int, str]:
    """Stdlib HTTP POST, imported lazily so tests never touch the network by accident.

    Returns (status_code, text). Uses urllib to avoid a hard requests dependency at
    import time; the real plugin ships requests, but the pure suite can run without it.
    """
    import urllib.error
    import urllib.request

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 fixed https base
            return resp.getcode(), resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:  # 4xx/5xx still carry a body we want to inspect
        return e.code, e.read().decode("utf-8", errors="replace")


def call(
    key: str,
    system: str,
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    max_tokens: int = 8192,
    post=_default_post,
) -> str:
    """One resilient gateway round; returns the reply TEXT. Raises OmegaError with a
    typed kind (auth | network | other) on failure. ``post`` is injectable for tests."""
    if not key:
        raise OmegaError("No API key set — paste your oc_ key in MaxDirector's settings.", "auth")
    body = json.dumps(
        {
            "model": model,
            "max_tokens": max_tokens,
            "stream": False,
            "system": system,
            "messages": messages,
        }
    ).encode("utf-8")
    headers = {
        "content-type": "application/json",
        "authorization": f"Bearer {key}",
        "anthropic-version": "2023-06-01",
    }
    last = "gateway request failed"
    for attempt in range(len(BACKOFF_S) + 1):
        status = None
        text_body = ""
        try:
            status, text_body = post(GATEWAY_URL, headers, body, TIMEOUT_S)
        except Exception as e:  # noqa: BLE001 network layer surfaces as a ret!yable miss
            last = f"network error: {e}"
        if status is not None:
            if status == 401:
                raise OmegaError("Gateway returned 401 — the API key is missing or invalid.", "auth")
            if 200 <= status < 300:
                try:
                    payload = json.loads(text_body)
                except ValueError:
                    payload = {}
                text = extract_text(payload)
                if text:
                    return text
                last = "the model returned no text"
            elif status == 429 or 500 <= status <= 599:
                last = f"gateway HTTP {status}"
            else:
                raise OmegaError(
                    f"Gateway request failed: HTTP {status} — {text_body[:200]}",
                    "other",
                    text_body[:2000],
                )
        if attempt < len(BACKOFF_S):
            time.sleep(BACKOFF_S[attempt])
    raise OmegaError(last, "network")


def text_block(text: str) -> dict[str, Any]:
    return {"type": "text", "text": text}


def image_block(b64: str, media_type: str = "image/png") -> dict[str, Any]:
    """A multimodal image content block (reference-similarity + framing-compare loops)."""
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}}
