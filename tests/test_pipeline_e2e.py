"""End-to-end MVP path (pure, no Max, no network): brief → DIRECT → gaps → COMPILE →
resolve → critic → best-of-N → render jobs. This is the whole value core proven off-Max.
"""

import json

from maxdirector.core.assets import detect_gaps
from maxdirector.core.critic import critique_shot, has_blockers
from maxdirector.core.director import compile_plan, direct
from maxdirector.core.models import Brief, RenderBackend
from maxdirector.core.render.backend import plan_jobs
from maxdirector.core.render.vantage import vantage_commands
from maxdirector.core.resolve import resolve_plan
from maxdirector.core.scoring import pick_best, score_candidate


def _canned(reply):
    def _c(key, system, messages, model="x", max_tokens=8192, post=None):
        return reply
    return _c


STORYBOARD = json.dumps({
    "director_style": "villeneuve", "grade_mood": "golden hour", "fps": 24,
    "shots": [
        {"id": "s1", "beat": "establish", "intent": "reveal the room", "camera_move": "establish",
         "subject_node": "sofa_grp", "duration_s": 6, "mood": "golden hour"},
        {"id": "s2", "beat": "detail", "intent": "orbit the sofa", "camera_move": "orbit",
         "subject_node": "sofa_grp", "duration_s": 5},
    ],
})

PLAN = json.dumps({
    "shots": [
        {"id": "s1", "camera": {"name": "MD_Cam_01", "class": "VRayPhysicalCamera", "fov_mm": 24},
         "anchor": {"relative_to": "sofa_grp", "standpoint": "front-high", "distance_m": 4.0, "height_m": 1.6},
         "path": {"kind": "establish"}, "duration_s": 6},
        {"id": "s2", "camera": {"name": "MD_Cam_02", "class": "VRayPhysicalCamera", "fov_mm": 35},
         "anchor": {"relative_to": "sofa_grp", "standpoint": "three-quarter", "distance_m": 3.0, "height_m": 1.4},
         "path": {"kind": "orbit", "around": "sofa_grp", "degrees": 40}, "duration_s": 5},
    ],
    "lights": [{"op": "create", "class": "VRaySun", "time_of_day": "17:30"}],
    "environment": {"hdri_asset": "polyhaven:kloofendal_48d", "gamma": 2.2},
    "render": {"backend": "vantage", "size": [3840, 2160], "fps": 24, "format": "exr"},
    "status": "ready",
})


def test_full_mvp_pipeline(living_room):
    # ③ DIRECT
    sb, notes, _ = direct("k", living_room, Brief(prompt="cinematic reveal", render_backend=RenderBackend.VANTAGE),
                          complete=_canned(STORYBOARD))
    assert sb and len(sb.shots) == 2

    # ④ gap detection: establish shot + no env → sky gap
    gaps = detect_gaps(sb, living_room)
    assert any(g.kind == "sky" for g in gaps)

    # ⑤ COMPILE
    plan, errors, _ = compile_plan("k", living_room, sb, complete=_canned(PLAN))
    assert plan and not errors
    assert plan.render.backend.value == "vantage"

    # ⑤·5 resolve + critic — no blockers on a sane plan
    resolved = resolve_plan(plan, living_room)
    assert len(resolved) == 2
    all_findings = []
    for rs in resolved:
        subj = living_room.node_by_name("sofa_grp")
        all_findings += critique_shot(rs, living_room, subject_center=subj.bbox.center)
    assert not has_blockers(all_findings)

    # best-of-N (no sidecar → composition-only) picks a candidate
    cands = [score_candidate("s1", i, subject_screen_pos=(sp, 1 / 3, 0.0)) for i, sp in enumerate([0.5, 1 / 3])]
    assert pick_best(cands).candidate_index == 1  # the on-thirds candidate wins

    # ⑥ render jobs + Vantage batch commands (one per shot, sequential)
    jobs = plan_jobs(plan)
    assert len(jobs) == 2
    cmds = vantage_commands(jobs, {"s1": "s1.vantage", "s2": "s2.vantage"}, console_exe="vc.exe")
    assert len(cmds) == 2 and cmds[0][0] == "vc.exe"


def test_pipeline_flags_camera_in_void(living_room):
    """A plan that puts the camera absurdly far (huge distance) must be caught by the critic."""
    bad = json.loads(PLAN)
    bad["shots"] = [bad["shots"][0]]
    bad["shots"][0]["anchor"]["distance_m"] = 200.0  # clamped max, still far outside a small room
    plan, _, _ = compile_plan("k", living_room, None or _sb1(), complete=_canned(json.dumps(bad)))
    resolved = resolve_plan(plan, living_room)
    findings = critique_shot(resolved[0], living_room)
    assert any(f.code == "camera_in_void" for f in findings)


def _sb1():
    from maxdirector.core.models import Storyboard, StoryboardShot, CameraMove
    return Storyboard(shots=[StoryboardShot("s1", "establish", "x", CameraMove.ESTABLISH, "sofa_grp")])
