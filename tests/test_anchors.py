"""Anchor resolver + path sampler — the deterministic camera-move core."""

import math

from maxdirector.core.anchors import (
    length,
    normalize,
    resolve_camera,
    rotate_about_axis,
    sample_path,
    sub,
)
from maxdirector.core.models import (
    Anchor,
    BBox,
    CameraMove,
    NodeInfo,
    PathSpec,
    Standpoint,
    UpAxis,
)


def _sofa() -> NodeInfo:
    # a 2x1x0.8m sofa centred at origin, sitting on the floor (z from 0..0.8)
    return NodeInfo(handle=1, name="sofa_grp", klass="Editable_Poly",
                    bbox=BBox(lo=(-1.0, -0.5, 0.0), hi=(1.0, 0.5, 0.8)))


def test_front_standpoint_places_camera_on_minus_y():
    cam = resolve_camera(Anchor(relative_to="sofa_grp", standpoint=Standpoint.FRONT,
                                distance_m=3.0, height_m=1.5), _sofa())
    # front = -Y side, 3 units away, looking back at the subject centre
    assert cam.pos[1] < -2.0
    assert abs(cam.pos[0]) < 1e-6
    assert cam.look_at == _sofa().bbox.center
    assert cam.pos[2] == 1.5  # height above base (base=0)


def test_top_standpoint_is_overhead():
    cam = resolve_camera(Anchor(relative_to="sofa_grp", standpoint=Standpoint.TOP,
                                distance_m=4.0, height_m=1.0), _sofa())
    c = _sofa().bbox.center
    assert abs(cam.pos[0] - c[0]) < 1e-6 and abs(cam.pos[1] - c[1]) < 1e-6
    assert cam.pos[2] > c[2]


def test_distance_scales_with_units():
    a = Anchor(relative_to="sofa_grp", standpoint=Standpoint.FRONT, distance_m=2.0, height_m=1.0)
    cm = resolve_camera(a, _sofa(), meters_to_units=1.0)
    inch = resolve_camera(a, _sofa(), meters_to_units=39.37)
    assert length(sub(inch.pos, _sofa().bbox.center)) > length(sub(cm.pos, _sofa().bbox.center)) * 30


def test_rodrigues_quarter_turn():
    v = (1.0, 0.0, 0.0)
    r = rotate_about_axis(v, (0.0, 0.0, 1.0), math.radians(90))
    assert abs(r[0]) < 1e-6 and abs(r[1] - 1.0) < 1e-6


def test_orbit_sweeps_around_subject():
    cam = resolve_camera(Anchor(relative_to="sofa_grp", standpoint=Standpoint.FRONT,
                                distance_m=3.0, height_m=1.0), _sofa())
    keys = sample_path(cam, PathSpec(kind="orbit", degrees=90.0), CameraMove.ORBIT,
                       _sofa(), duration_s=6.0)
    assert len(keys) >= 5
    first, last = keys[0][1], keys[-1][1]
    c = _sofa().bbox.center
    # radius preserved; end rotated ~90° from start about +Z
    r0 = length(sub(first.pos, c))
    r1 = length(sub(last.pos, c))
    assert abs(r0 - r1) < 1e-6
    # start on -Y, a +90° turn about Z lands near -X (or +X); either way |x| grows, |y| shrinks
    assert abs(last.pos[0]) > abs(first.pos[0])
    assert abs(last.pos[1]) < abs(first.pos[1]) + 1e-6


def test_push_in_moves_toward_subject():
    cam = resolve_camera(Anchor(relative_to="sofa_grp", standpoint=Standpoint.FRONT,
                                distance_m=4.0, height_m=1.0), _sofa())
    keys = sample_path(cam, PathSpec(kind="push_in", distance_m=1.0), CameraMove.PUSH_IN,
                       _sofa(), duration_s=4.0)
    c = _sofa().bbox.center
    assert length(sub(keys[-1][1].pos, c)) < length(sub(keys[0][1].pos, c))


def test_pull_out_moves_away():
    cam = resolve_camera(Anchor(relative_to="sofa_grp", standpoint=Standpoint.FRONT,
                                distance_m=4.0, height_m=1.0), _sofa())
    keys = sample_path(cam, PathSpec(kind="pull_out", distance_m=1.0), CameraMove.PULL_OUT,
                       _sofa(), duration_s=4.0)
    c = _sofa().bbox.center
    assert length(sub(keys[-1][1].pos, c)) > length(sub(keys[0][1].pos, c))


def test_crane_up_raises_camera():
    cam = resolve_camera(Anchor(relative_to="sofa_grp", standpoint=Standpoint.FRONT,
                                distance_m=4.0, height_m=1.0), _sofa())
    keys = sample_path(cam, PathSpec(kind="crane_up", distance_m=2.0), CameraMove.CRANE_UP,
                       _sofa(), duration_s=4.0)
    assert keys[-1][1].pos[2] > keys[0][1].pos[2]


def test_dolly_zoom_changes_fov():
    cam = resolve_camera(Anchor(relative_to="sofa_grp", standpoint=Standpoint.FRONT,
                                distance_m=5.0, height_m=1.0), _sofa())
    keys = sample_path(cam, PathSpec(kind="dolly_zoom", distance_m=2.0), CameraMove.DOLLY_ZOOM,
                       _sofa(), duration_s=4.0)
    assert keys[-1][1].fov_mm != keys[0][1].fov_mm
