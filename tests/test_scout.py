"""Scout views + vision-first placement — the load-bearing redesign."""

from dataclasses import replace

from maxdirector.core.anchors import length, sub
from maxdirector.core.models import ScoutAnchor
from maxdirector.core.plan_schema import parse_plan
from maxdirector.core.resolve import resolve_plan
from maxdirector.core.scout import resolve_scout_camera, scout_poses


def test_scout_poses_cover_scene(living_room):
    views = scout_poses(living_room.scene_bounds)
    labels = [v.label for v in views]
    assert "plan" in labels and "high_3q" in labels
    assert sum(1 for l in labels if l.startswith("corner")) == 4
    # corner cams sit at eye height (floor=0, eye ~1.6) and look across at eye height
    corner = next(v for v in views if v.label == "corner_0")
    assert 1.0 < corner.pose.pos[2] < 2.5
    assert abs(corner.pose.look_at[2] - corner.pose.pos[2]) < 1e-6
    # plan cam is above the scene looking down
    plan = next(v for v in views if v.label == "plan")
    assert plan.pose.pos[2] > living_room.scene_bounds.hi[2]


def test_feature_directed_scouts_added_with_nodes(living_room):
    # the north wall (8m wide, 3m tall) is the dominant vertical feature
    views = scout_poses(living_room.scene_bounds, nodes=living_room.nodes)
    labels = [v.label for v in views]
    assert "feature_low" in labels and "feature_high" in labels
    # feature scouts are deliverable-like ~35mm, not 18mm ultra-wide
    feat = next(v for v in views if v.label == "feature_low")
    assert feat.pose.fov_mm == 35.0
    # and they aim at a real feature's centre, not the room centre
    assert feat.pose.look_at != living_room.scene_bounds.center


def test_no_feature_scouts_without_nodes(living_room):
    views = scout_poses(living_room.scene_bounds)   # no nodes → just the coverage set
    assert not any(v.label.startswith("feature") for v in views)


def test_resolve_scout_dolly_moves_toward_look(living_room):
    scout = scout_poses(living_room.scene_bounds)[0]
    c = scout.pose.look_at
    pushed = resolve_scout_camera(ScoutAnchor(from_scout=0, dolly_m=1.0), scout)   # + = push in
    pulled = resolve_scout_camera(ScoutAnchor(from_scout=0, dolly_m=-1.0), scout)  # - = pull out
    assert length(sub(pushed.pos, c)) < length(sub(scout.pose.pos, c))
    assert length(sub(pulled.pos, c)) > length(sub(scout.pose.pos, c))


def test_resolve_scout_pedestal_raises(living_room):
    scout = scout_poses(living_room.scene_bounds)[0]
    up = resolve_scout_camera(ScoutAnchor(from_scout=0, pedestal_m=0.5), scout)
    assert up.pos[2] > scout.pose.pos[2]


def test_scout_anchored_plan_resolves(living_room):
    d = replace(living_room, scouts=scout_poses(living_room.scene_bounds))
    plan, errors = parse_plan({"shots": [{
        "id": "s1", "camera": {"name": "MD_Cam_01", "fov_mm": 24},
        "scout_anchor": {"from_scout": 1, "dolly_m": -1.5, "truck_m": 0.3, "pedestal_m": -0.1, "fov_mm": 24},
        "path": {"kind": "push_in", "distance_m": 1.0}, "duration_s": 5,
    }]}, d)
    assert not errors
    assert plan.shots[0].scout_anchor is not None and plan.shots[0].anchor is None
    shots = resolve_plan(plan, d)
    assert shots and len(shots[0].states) >= 2


def test_bad_scout_id_flagged(living_room):
    d = replace(living_room, scouts=scout_poses(living_room.scene_bounds))
    plan, errors = parse_plan({"shots": [{
        "id": "s1", "camera": {}, "scout_anchor": {"from_scout": 99}}]}, d)
    assert any("from_scout 99" in e for e in errors)


def test_object_anchor_still_works(living_room):
    plan, errors = parse_plan({"shots": [{
        "id": "s1", "camera": {"fov_mm": 35},
        "anchor": {"relative_to": "sofa_grp", "standpoint": "front", "distance_m": 3, "height_m": 1.5},
        "path": {"kind": "static"}}]}, living_room)
    assert not errors
    assert plan.shots[0].anchor is not None and plan.shots[0].scout_anchor is None
    assert resolve_plan(plan, living_room)
