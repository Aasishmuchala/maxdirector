from maxdirector.core.plan_schema import parse_plan


def _good_plan():
    return {
        "shots": [{
            "id": "s1",
            "camera": {"name": "MD_Cam_01", "class": "VRayPhysicalCamera", "fov_mm": 24},
            "anchor": {"relative_to": "sofa_grp", "standpoint": "front-high",
                       "distance_m": 2.5, "height_m": 1.5, "subject_screen_pos": [0.5, 0.45]},
            "path": {"kind": "orbit", "around": "sofa_grp", "degrees": 30},
            "keyframes": [{"t_s": 0, "ease": "in_out", "fov_mm": 24}],
            "duration_s": 6,
        }],
        "lights": [{"op": "create", "class": "VRaySun", "time_of_day": "17:30"}],
        "environment": {"hdri_asset": "polyhaven:kloofendal_48d", "gamma": 2.2},
        "render": {"backend": "vray", "size": [3840, 2160], "fps": 24, "format": "exr",
                   "shots": [{"id": "s1", "frames": [0, 144], "output": "r/s1.####.exr"}]},
        "status": "ready",
    }


def test_valid_plan_parses(living_room):
    plan, errors = parse_plan(_good_plan(), living_room)
    assert not errors
    assert len(plan.shots) == 1
    assert plan.shots[0].camera.fov_mm == 24
    assert plan.render.size == (3840, 2160)
    assert plan.lights[0].klass == "VRaySun"


def test_anchor_subject_not_in_scene_flagged(living_room):
    p = _good_plan()
    p["shots"][0]["anchor"]["relative_to"] = "cathedral_nave"
    plan, errors = parse_plan(p, living_room)
    assert any("cathedral_nave" in e for e in errors)


def test_illegal_camera_class_flagged(living_room):
    p = _good_plan()
    p["shots"][0]["camera"]["class"] = "SomeRandomCam"
    plan, errors = parse_plan(p, living_room)
    assert any("not in pack" in e for e in errors)
    assert plan.shots[0].camera.klass == "VRayPhysicalCamera"  # repaired


def test_fov_and_distance_clamped(living_room):
    p = _good_plan()
    p["shots"][0]["camera"]["fov_mm"] = 999
    p["shots"][0]["anchor"]["distance_m"] = 9999
    plan, _ = parse_plan(p, living_room)
    assert plan.shots[0].camera.fov_mm <= 300
    assert plan.shots[0].anchor.distance_m <= 200


def test_animation_on_rigged_node_refused(living_room):
    p = _good_plan()
    p["animation"] = [{"op": "keyframe", "node": "character_01", "track": "rotation",
                       "safe_required": True, "keys": [{"t_s": 0, "value": [0, 0, 0]}]}]
    plan, errors = parse_plan(p, living_room)
    assert any("character_01" in e and "refused" in e for e in errors)
    assert not plan.animation  # not added


def test_animation_on_safe_node_allowed(living_room):
    p = _good_plan()
    p["animation"] = [{"op": "keyframe", "node": "door_01", "track": "rotation",
                       "keys": [{"t_s": 0, "value": [0, 0, 0]}, {"t_s": 2, "value": [0, 0, 85]}]}]
    plan, errors = parse_plan(p, living_room)
    assert plan.animation and plan.animation[0].node == "door_01"


def test_opt_in_overrides_guard(living_room):
    p = _good_plan()
    p["animation"] = [{"op": "keyframe", "node": "character_01", "track": "rotation",
                       "keys": [{"t_s": 0, "value": [0, 0, 0]}]}]
    plan, errors = parse_plan(p, living_room, opted_in_nodes={"character_01"})
    assert plan.animation and plan.animation[0].node == "character_01"
