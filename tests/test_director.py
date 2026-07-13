"""Director orchestration with a mocked LLM — no network."""

import json

from maxdirector.core.director import compile_plan, direct
from maxdirector.core.models import Brief


def _fake_complete(reply: str):
    def _c(key, system, messages, model="x", max_tokens=8192, post=None):
        return reply
    return _c


def test_direct_parses_storyboard(living_room):
    reply = json.dumps({
        "director_style": "villeneuve", "grade_mood": "golden hour", "aspect": "16:9", "fps": 24,
        "shots": [
            {"id": "s1", "beat": "establish", "intent": "reveal the living room",
             "camera_move": "establish", "subject_node": "sofa_grp", "duration_s": 6},
            {"id": "s2", "beat": "detail", "intent": "orbit the sofa",
             "camera_move": "orbit", "subject_node": "sofa_grp", "duration_s": 5},
        ],
        "asset_gaps": [{"shot_id": "s1", "kind": "sky", "reason": "no env", "keywords": ["sunset"]}],
    })
    sb, notes, raw = direct("oc_key", living_room, Brief(prompt="cinematic reveal"),
                            complete=_fake_complete(reply))
    assert sb is not None and len(sb.shots) == 2
    assert sb.shots[1].camera_move.value == "orbit"
    assert sb.asset_gaps and sb.asset_gaps[0].kind == "sky"


def test_direct_bad_json_returns_note(living_room):
    sb, notes, raw = direct("k", living_room, Brief(), complete=_fake_complete("sorry, no json here"))
    assert sb is None and any("JSON" in n for n in notes)


def test_direct_flags_ghost_subject(living_room):
    reply = json.dumps({"shots": [
        {"id": "s1", "beat": "x", "intent": "y", "camera_move": "push_in",
         "subject_node": "spaceship", "duration_s": 4}]})
    sb, notes, raw = direct("k", living_room, Brief(), complete=_fake_complete(reply))
    assert sb.shots[0].subject_node is None
    assert any("spaceship" in n for n in notes)


def test_compile_parses_plan(living_room):
    from maxdirector.core.models import Storyboard, StoryboardShot, CameraMove
    sb = Storyboard(shots=[StoryboardShot("s1", "establish", "reveal", CameraMove.ORBIT, "sofa_grp")])
    reply = json.dumps({"shots": [{
        "id": "s1", "camera": {"name": "MD_Cam_01", "class": "VRayPhysicalCamera", "fov_mm": 24},
        "anchor": {"relative_to": "sofa_grp", "standpoint": "three-quarter", "distance_m": 2.5, "height_m": 1.5},
        "path": {"kind": "orbit", "around": "sofa_grp", "degrees": 30}, "duration_s": 6}],
        "render": {"backend": "vray", "size": [1920, 1080], "fps": 24, "format": "exr"}})
    plan, errors, raw = compile_plan("k", living_room, sb, complete=_fake_complete(reply))
    assert plan is not None and not errors
    assert plan.shots[0].anchor.relative_to == "sofa_grp"
