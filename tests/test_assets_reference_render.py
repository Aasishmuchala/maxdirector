from maxdirector.core.assets import detect_gaps, hdri_file_urls, search_hdris
from maxdirector.core.models import (
    AuthoringPlan, CameraMove, CameraSpec, Anchor, PlanShot, RenderSpec,
    Storyboard, StoryboardShot,
)
from maxdirector.core.reference import (
    anchor_seed_from_calibration, decide_similarity, fov_mm_from_vfov, move_from_motion,
)
from maxdirector.core.render import plan_jobs, vantage_commands


# ---- assets ----

def test_detect_sky_gap_for_exterior_without_env(living_room):
    sb = Storyboard(shots=[StoryboardShot("s1", "establish", "reveal", CameraMove.ESTABLISH, "sofa_grp",
                                          mood="golden hour")])
    gaps = detect_gaps(sb, living_room)
    assert any(g.kind == "sky" and g.shot_id == "s1" for g in gaps)
    sky = [g for g in gaps if g.kind == "sky"][0]
    assert "sunset" in sky.keywords


def test_search_hdris_ranks_by_overlap():
    fake = {
        "sunset_field": {"name": "Sunset Field", "tags": ["sunset", "field"], "categories": ["outdoor"], "download_count": 5000},
        "studio_small": {"name": "Studio", "tags": ["studio"], "categories": ["indoor"], "download_count": 9000},
    }
    res = search_hdris(["sunset", "outdoor"], fetch_json=lambda url: fake)
    assert res and res[0]["id"] == "sunset_field"


def test_hdri_file_urls():
    fake = {"hdri": {"4k": {"hdr": {"url": "https://x/f.hdr"}}}}
    urls = hdri_file_urls("id", fetch_json=lambda url: fake)
    assert urls["hdr"].endswith(".hdr")


# ---- reference ----

def test_similarity_gate_rejects_low_confidence():
    ok, msg = decide_similarity({"match": True, "confidence": 0.3, "reason": "maybe"})
    assert not ok and "rejected" in msg


def test_similarity_gate_accepts_high_confidence():
    ok, msg = decide_similarity({"match": True, "confidence": 0.9, "reason": "same room type"})
    assert ok


def test_fov_from_vfov_monotonic():
    wide = fov_mm_from_vfov(80)
    tele = fov_mm_from_vfov(20)
    assert tele > wide  # narrower FoV = longer lens


def test_anchor_seed_low_angle_from_upward_pitch():
    anchor, fov = anchor_seed_from_calibration({"vfov_deg": 50, "pitch_deg": 20}, "sofa_grp")
    assert anchor.standpoint.value == "front-low"
    assert fov > 0


def test_move_from_motion_orbit():
    move, params = move_from_motion({"type": "orbit", "arc_deg": 60})
    assert move.value == "orbit" and params["degrees"] == 60


def test_move_from_motion_push_in():
    move, _ = move_from_motion({"type": "dolly", "dolly_frac": -0.3})
    assert move.value == "push_in"


# ---- render ----

def _two_shot_plan():
    shots = [
        PlanShot("s1", CameraSpec("MD_Cam_01"), Anchor("sofa_grp"), duration_s=4),
        PlanShot("s2", CameraSpec("MD_Cam_02"), Anchor("sofa_grp"), duration_s=6),
    ]
    return AuthoringPlan(shots=shots, render=RenderSpec(size=(1920, 1080), fps=24, fmt="exr"))


def test_plan_jobs_uses_local_ranges():
    jobs = plan_jobs(_two_shot_plan())
    assert len(jobs) == 2
    # each shot renders over its OWN local range (its camera is keyed 0..dur locally)
    assert jobs[0].frame_start == 0 and jobs[0].frame_end == 95    # 4s*24 -> 0..95
    assert jobs[1].frame_start == 0 and jobs[1].frame_end == 143   # 6s*24 -> 0..143 (NOT 96..)


def test_vantage_commands_one_per_shot():
    jobs = plan_jobs(_two_shot_plan())
    scene_files = {"s1": "C:/x/s1.vantage", "s2": "C:/x/s2.vantage"}
    cmds = vantage_commands(jobs, scene_files, console_exe="vantage_console.exe")
    assert len(cmds) == 2
    assert any(a.startswith("-frames=0-95") for a in cmds[0])
    assert any(a.startswith("-scenefile=C:/x/s2.vantage") for a in cmds[1])
