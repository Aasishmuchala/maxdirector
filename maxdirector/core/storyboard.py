"""Storyboard schema (stage ③) — the creative plan the LLM returns, parsed + validated.

The JSON shape is embedded verbatim in the system prompt (the gateway can't do tools). We
parse defensively: unknown moves fall back to a sane default and are recorded as notes
rather than crashing, and subject references that aren't in the scene are flagged so the
compile stage doesn't build against a ghost.
"""

from __future__ import annotations

from typing import List, Tuple

from .models import AssetGap, CameraMove, Digest, Storyboard, StoryboardShot

# Embedded in the prompt so the model emits exactly this shape.
STORYBOARD_SCHEMA = {
    "type": "object",
    "required": ["shots"],
    "properties": {
        "director_style": {"type": "string"},
        "grade_mood": {"type": "string"},
        "aspect": {"type": "string"},
        "fps": {"type": "integer"},
        "shots": {
            "type": "array",
            "minItems": 1,
            "maxItems": 12,
            "items": {
                "type": "object",
                "required": ["id", "beat", "intent", "camera_move", "duration_s"],
                "properties": {
                    "id": {"type": "string"},
                    "beat": {"type": "string"},
                    "intent": {"type": "string"},
                    "camera_move": {"enum": [m.value for m in CameraMove]},
                    "subject_node": {"type": ["string", "null"]},
                    "framing": {"type": "string"},
                    "mood": {"type": "string"},
                    "duration_s": {"type": "number"},
                    "transition_in": {"type": "string"},
                },
            },
        },
        "asset_gaps": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["shot_id", "kind", "reason"],
                "properties": {
                    "shot_id": {"type": "string"},
                    "kind": {"type": "string"},
                    "reason": {"type": "string"},
                    "keywords": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}


def parse_storyboard(obj: dict, digest: Digest) -> Tuple[Storyboard, List[str]]:
    """Parse + validate. Returns (storyboard, notes). Never raises on model quirks; instead
    it repairs and records a note, so a single odd shot can't sink the whole reel."""
    notes: List[str] = []
    sb = Storyboard(
        director_style=str(obj.get("director_style", "")),
        grade_mood=str(obj.get("grade_mood", "")),
        aspect=str(obj.get("aspect", digest and "16:9" or "16:9")),
        fps=int(obj.get("fps", 24) or 24),
    )
    targets = set(digest.named_targets())
    raw_shots = obj.get("shots")
    if not isinstance(raw_shots, list) or not raw_shots:
        notes.append("no shots in storyboard")
        return sb, notes

    for i, s in enumerate(raw_shots):
        if not isinstance(s, dict):
            notes.append(f"shot #{i} not an object — skipped")
            continue
        move_raw = str(s.get("camera_move", "")).strip()
        try:
            move = CameraMove(move_raw)
        except ValueError:
            move = CameraMove.PUSH_IN
            notes.append(f"shot {s.get('id', i)}: unknown move {move_raw!r} → push_in")
        subj = s.get("subject_node")
        if subj is not None and subj not in targets:
            notes.append(f"shot {s.get('id', i)}: subject {subj!r} not in scene")
            subj = None
        sb.shots.append(StoryboardShot(
            id=str(s.get("id", f"s{i+1}")),
            beat=str(s.get("beat", "")),
            intent=str(s.get("intent", "")),
            camera_move=move,
            subject_node=subj,
            framing=str(s.get("framing", "")),
            mood=str(s.get("mood", "")),
            duration_s=float(s.get("duration_s", 4.0) or 4.0),
            transition_in=str(s.get("transition_in", "cut")),
        ))

    for g in obj.get("asset_gaps", []) or []:
        if isinstance(g, dict) and g.get("kind"):
            sb.asset_gaps.append(AssetGap(
                shot_id=str(g.get("shot_id", "")),
                kind=str(g.get("kind")),
                reason=str(g.get("reason", "")),
                keywords=[str(k) for k in (g.get("keywords") or [])],
            ))
    return sb, notes
