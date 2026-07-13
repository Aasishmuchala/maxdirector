from maxdirector.core.anchors import length, sub
from maxdirector.core.plan_schema import parse_plan
from maxdirector.core.resolve import meters_to_units, resolve_plan


def _plan_dict():
    return {"shots": [{
        "id": "s1",
        "camera": {"name": "MD_Cam_01", "class": "VRayPhysicalCamera", "fov_mm": 28},
        "anchor": {"relative_to": "sofa_grp", "standpoint": "front", "distance_m": 3.0, "height_m": 1.5},
        "path": {"kind": "orbit", "around": "sofa_grp", "degrees": 45},
        "duration_s": 6,
    }]}


def test_resolve_produces_keyframed_states(living_room):
    plan, _ = parse_plan(_plan_dict(), living_room)
    shots = resolve_plan(plan, living_room)
    assert len(shots) == 1
    st = shots[0].states
    assert len(st) >= 5              # orbit emits a smooth arc
    assert st[0][1].fov_mm == 28     # lens carried from the camera spec
    # every state looks at the subject centre
    c = living_room.node_by_name("sofa_grp").bbox.center
    assert all(s.look_at == c for _, s in st)


def test_meters_to_units():
    assert meters_to_units("meters") == 1.0
    assert abs(meters_to_units("centimeters") - 100.0) < 1e-6
    assert abs(meters_to_units("inches") - (1 / 0.0254)) < 1e-3


def test_missing_subject_falls_back_to_scene(living_room):
    d = _plan_dict()
    d["shots"][0]["anchor"]["relative_to"] = "ghost"
    d["shots"][0]["path"]["around"] = None
    plan, errors = parse_plan(d, living_room)
    shots = resolve_plan(plan, living_room)   # must not raise
    assert shots and shots[0].states
