"""The Director — stages ③ DIRECT (storyboard) and ⑤ COMPILE (authoring plan).

Builds the prompts (digest + brief + cinematic pack + the JSON schema, since the gateway
can't do tools), calls the model through the provider, parses the reply with the
balanced-brace extractor, and validates into the pure dataclasses. The LLM call is injected
(``complete``) so the whole orchestration is unit-tested with canned replies — no network.
"""

from __future__ import annotations

import json
from typing import Callable, List, Optional, Tuple

from . import provider as _provider
from .cinematic import CinematicPack, load as load_cinematic
from .digest_format import digest_block
from .models import AuthoringPlan, Brief, Digest, Storyboard
from .omega import parse_json_from_text
from .packs import VerifiedPack, default_vray_pack
from .plan_schema import PLAN_SCHEMA_HINT, parse_plan
from .storyboard import STORYBOARD_SCHEMA, parse_storyboard

Complete = Callable[..., str]

_DIRECT_SYS = """You are the DIRECTOR inside MaxDirector, planning a cinematic multi-shot \
sequence for a real 3ds Max archviz scene. You are given the SCENE (real named objects with \
sizes and positions), the BRIEF, and the CINEMATIC vocabulary. Design an ordered SHOT LIST \
that tells a story with real camera moves, choosing a subject object BY NAME for each shot \
from the scene. Foresee ASSET GAPS (a shot that needs a sky, foreground, prop, or entourage \
the scene lacks). Do NOT invent objects that aren't in the scene.

Return ONLY a JSON object (no markdown fences, no prose) matching this schema:
%s

CINEMATIC VOCABULARY:
%s

SCENE:
%s

BRIEF:
%s
"""

_COMPILE_SYS = """You are the COMPILER inside MaxDirector. Turn the approved STORYBOARD into a \
technical AUTHORING PLAN for 3ds Max + V-Ray 7. CRITICAL: express camera placement as SEMANTIC \
ANCHORS relative to real named objects (relative_to, standpoint, distance_m in METRES, height_m, \
subject_screen_pos) — NEVER world coordinates; the plugin computes transforms from real geometry. \
Use only VRayPhysicalCamera / VRaySun / VRayLight. Keep params within sane ranges. For any object \
animation, only reference nodes marked anim_safe in the scene.

Return ONLY a JSON object (no fences, no prose) shaped like this example:
%s

SCENE:
%s

STORYBOARD:
%s
"""


def _shots_json(sb: Storyboard) -> str:
    return json.dumps({
        "director_style": sb.director_style, "grade_mood": sb.grade_mood,
        "aspect": sb.aspect, "fps": sb.fps,
        "shots": [{
            "id": s.id, "beat": s.beat, "intent": s.intent,
            "camera_move": s.camera_move.value, "subject_node": s.subject_node,
            "framing": s.framing, "mood": s.mood, "duration_s": s.duration_s,
        } for s in sb.shots],
        "asset_gaps": [{"shot_id": g.shot_id, "kind": g.kind, "reason": g.reason,
                        "keywords": g.keywords} for g in sb.asset_gaps],
    }, indent=1)


def direct(
    key: str,
    digest: Digest,
    brief: Brief,
    complete: Complete = _provider.complete,
    model: str = _provider.DEFAULT_MODEL,
    cinematic: Optional[CinematicPack] = None,
) -> Tuple[Optional[Storyboard], List[str], str]:
    """Stage ③. Returns (storyboard | None, notes, raw_reply)."""
    cine = cinematic or load_cinematic()
    system = _DIRECT_SYS % (
        json.dumps(STORYBOARD_SCHEMA, indent=1),
        cine.prompt_block(brief.director_style),
        digest_block(digest),
        json.dumps(brief.to_prompt_dict(), indent=1),
    )
    raw = complete(key, system, [{"role": "user", "content": "Design the shot list."}], model=model)
    obj = parse_json_from_text(raw)
    if obj is None:
        return None, ["model did not return valid JSON"], raw
    sb, notes = parse_storyboard(obj, digest)
    return sb, notes, raw


def compile_plan(
    key: str,
    digest: Digest,
    storyboard: Storyboard,
    complete: Complete = _provider.complete,
    model: str = _provider.DEFAULT_MODEL,
    pack: Optional[VerifiedPack] = None,
    opted_in_nodes: Optional[set] = None,
) -> Tuple[Optional[AuthoringPlan], List[str], str]:
    """Stage ⑤. Returns (plan | None, errors, raw_reply)."""
    pack = pack or default_vray_pack()
    system = _COMPILE_SYS % (
        json.dumps(PLAN_SCHEMA_HINT, indent=1),
        digest_block(digest),
        _shots_json(storyboard),
    )
    raw = complete(key, system, [{"role": "user", "content": "Compile the authoring plan."}], model=model)
    obj = parse_json_from_text(raw)
    if obj is None:
        return None, ["model did not return valid JSON"], raw
    plan, errors = parse_plan(obj, digest, pack=pack, opted_in_nodes=opted_in_nodes)
    return plan, errors, raw
