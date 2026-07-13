"""Format the digest for the LLM prompt, and compute PRE-FLIGHT warnings — PURE.

The warnings are the "silent value-wrecker" census generalised from LightMatch: things that
will quietly ruin a shot (no camera-worthy subject, exposure control eating EV, gamma != 2.2,
multiple suns, no environment for an exterior). They're surfaced in the storyboard and the UI.
"""

from __future__ import annotations

import json
from typing import List

from .models import Category, Digest


def preflight_warnings(digest: Digest) -> List[str]:
    w: List[str] = []
    if digest.exposure_control_active:
        w.append("Scene exposure control is active — it can override camera/EV moves.")
    if digest.gamma is not None and abs(digest.gamma - 2.2) > 0.05:
        w.append(f"Display gamma is {digest.gamma} (not 2.2) — lighting/exposure will read off.")
    if len(digest.suns) > 1:
        w.append(f"{len(digest.suns)} suns in the scene — shadows may fight; expect one key.")
    geo = [n for n in digest.nodes if n.category == Category.GEOMETRY]
    if not geo:
        w.append("No geometry found — nothing to frame.")
    if digest.scene_bounds is None:
        w.append("Scene bounds unknown — camera distances may be off.")
    return w


def digest_block(digest: Digest) -> str:
    """The compact JSON block the Director prompt embeds (names/bounds/counts only)."""
    d = digest.to_prompt_dict()
    d["warnings"] = list(set(d.get("warnings", []) + preflight_warnings(digest)))
    return json.dumps(d, indent=1)
