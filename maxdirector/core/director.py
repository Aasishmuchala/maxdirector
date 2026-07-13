"""The Director — stages ③ DIRECT (storyboard) and ⑤ COMPILE (authoring plan).

Builds the prompts (digest + brief + cinematic pack + the JSON schema, since the gateway
can't do tools), calls the model through the provider, parses the reply with the
balanced-brace extractor, and validates into the pure dataclasses. The LLM call is injected
(``complete``) so the whole orchestration is unit-tested with canned replies — no network.
"""

from __future__ import annotations

import base64
import json
import os
from typing import Callable, List, Optional, Tuple

from . import provider as _provider
from .cinematic import CinematicPack, load as load_cinematic
from .digest_format import digest_block
from .models import AuthoringPlan, Brief, Digest, Storyboard
from .omega import image_block, parse_json_from_text, text_block
from .packs import VerifiedPack, default_vray_pack
from .plan_schema import PLAN_SCHEMA_HINT, parse_plan
from .storyboard import STORYBOARD_SCHEMA, parse_storyboard

Complete = Callable[..., str]

_DIRECT_SYS = """You are the DIRECTOR inside MaxDirector, planning a cinematic multi-shot \
sequence for a real 3ds Max archviz scene. You are shown SCOUT VIEWS — thumbnail renders of the \
scene from known camera positions, each with an id. LOOK at them: they show you the real space, \
where the light and windows are, what is worth framing. Design an ordered SHOT LIST that tells a \
story with real camera moves. For each shot pick the scout view whose vantage is closest to what \
you want (set from_scout to its id) and describe the move and framing you'd make from there. Node \
names in archviz scenes are often meaningless (Box001, Editable_Poly_47) — TRUST THE IMAGES, not \
the names. Foresee ASSET GAPS (a shot that needs a sky, foreground, prop the scene lacks).

Return ONLY a JSON object (no markdown fences, no prose) matching this schema:
%s

SCOUT VIEWS (ids you may reference as from_scout):
%s

CINEMATIC VOCABULARY:
%s

SCENE (object list — names may be unreliable; the images are ground truth):
%s

BRIEF:
%s
"""

_COMPILE_SYS = """You are the COMPILER inside MaxDirector. Turn the approved STORYBOARD into a \
technical AUTHORING PLAN for 3ds Max + V-Ray 7, using the SCOUT VIEWS you are shown. CRITICAL: \
place each camera VISION-FIRST with a scout_anchor — pick the from_scout id whose thumbnail is \
closest to the shot, then nudge in camera-local METRES: dolly_m (positive = push IN toward what you see, \
negative = pull back), truck_m (+ right), pedestal_m (+ up), and set fov_mm. The plugin resolves this from the scout's \
KNOWN pose, so it lands in real geometry — never emit world coordinates. Use an object anchor only \
if a named object is unmistakably the subject. Use only VRayPhysicalCamera / VRaySun / VRayLight; \
keep params sane; animate only anim_safe nodes.

Return ONLY a JSON object (no fences, no prose) shaped like this example:
%s

SCOUT VIEWS:
%s

SCENE:
%s

STORYBOARD:
%s
"""


def _scout_legend(digest: Digest) -> str:
    if not digest.scouts:
        return "(no scout thumbnails available — reason from the object list, less reliable)"
    return "\n".join(f"  id={sv.id}: {sv.label}" for sv in digest.scouts)


def _scout_blocks(digest: Digest) -> list:
    """Image content blocks for the multimodal call — the scout thumbnails the model reasons
    over. Skips any scout whose thumbnail wasn't rendered (degrades to text-only)."""
    blocks = []
    for sv in digest.scouts:
        if sv.thumb_path and os.path.exists(sv.thumb_path):
            try:
                with open(sv.thumb_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("ascii")
                blocks.append(text_block(f"scout id={sv.id} ({sv.label}):"))
                blocks.append(image_block(b64, "image/png"))
            except OSError:
                pass
    return blocks


def _user_content(instruction: str, digest: Digest) -> list:
    return [text_block(instruction)] + _scout_blocks(digest)


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
        _scout_legend(digest),
        cine.prompt_block(brief.director_style),
        digest_block(digest),
        json.dumps(brief.to_prompt_dict(), indent=1),
    )
    content = _user_content("Study the scout views and design the shot list.", digest)
    raw = complete(key, system, [{"role": "user", "content": content}], model=model)
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
        _scout_legend(digest),
        digest_block(digest),
        _shots_json(storyboard),
    )
    content = _user_content("Compile the authoring plan using scout_anchors.", digest)
    raw = complete(key, system, [{"role": "user", "content": content}], model=model)
    obj = parse_json_from_text(raw)
    if obj is None:
        return None, ["model did not return valid JSON"], raw
    plan, errors = parse_plan(obj, digest, pack=pack, opted_in_nodes=opted_in_nodes)
    return plan, errors, raw
