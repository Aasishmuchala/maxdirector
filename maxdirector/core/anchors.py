"""Anchor resolver — turn SEMANTIC anchors into concrete camera poses. PURE math.

This is the fix for the single biggest failure mode (LLM emitting world coordinates that
land in the void): the model plans in scene-relative intent, and this module computes the
actual camera position/look-at from the subject's REAL geometry (bbox/pivot) that the
bridge read from the scene. Everything here is deterministic and unit-tested; the bridge
just feeds it real NodeInfo and applies the CameraStates it returns.

Conventions (3ds Max default is Z-up):
* Horizontal "front" = the -Y side (camera on -Y looking toward +Y); back +Y; right +X;
  left -X; three-quarter = front-right blend. Y-up scenes swap the vertical axis.
* Distances/heights arrive in METRES and are scaled to scene units by ``meters_to_units``.
"""

from __future__ import annotations

import math
from typing import List, Tuple

from .models import (
    Anchor,
    CameraMove,
    CameraState,
    NodeInfo,
    PathSpec,
    Standpoint,
    UpAxis,
    Vec3,
)

# ------------------------------------------------------------------ vector helpers

def add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def scale(a: Vec3, s: float) -> Vec3:
    return (a[0] * s, a[1] * s, a[2] * s)


def dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def length(a: Vec3) -> float:
    return math.sqrt(dot(a, a))


def normalize(a: Vec3) -> Vec3:
    n = length(a)
    return a if n == 0.0 else scale(a, 1.0 / n)


def rotate_about_axis(v: Vec3, axis: Vec3, radians: float) -> Vec3:
    """Rodrigues rotation of ``v`` about a unit-ish ``axis`` by ``radians``."""
    k = normalize(axis)
    c = math.cos(radians)
    s = math.sin(radians)
    return add(
        add(scale(v, c), scale(cross(k, v), s)),
        scale(k, dot(k, v) * (1.0 - c)),
    )


# ------------------------------------------------------------------ axis helpers

def _up_vec(up_axis: UpAxis) -> Vec3:
    return (0.0, 0.0, 1.0) if up_axis == UpAxis.Z else (0.0, 1.0, 0.0)


SENSOR_W_MM = 36.0
SENSOR_H_MM = 24.0


def reaim(pos: Vec3, look: Vec3, up: Vec3, fov_mm: float, screen: Vec3) -> Vec3:
    """Re-aim so the current look target lands at screen position (u,v) in 0..1 (0.5,0.5 =
    centre). This is the compositional lever the model controls via look_shift /
    subject_screen_pos — without it every shot stares dead-centre. To put the subject on the
    right/up, we rotate the camera left/up by the corresponding fraction of the FOV, which
    shifts the target the opposite way in frame. Returns the new look point."""
    u, v = screen[0], screen[1]
    if abs(u - 0.5) < 1e-6 and abs(v - 0.5) < 1e-6:
        return look
    view = sub(look, pos)
    dist = length(view)
    if dist < 1e-9:
        return look
    vdir = normalize(view)
    right = normalize(cross(vdir, up))
    hfov = 2.0 * math.atan(SENSOR_W_MM / (2.0 * max(fov_mm, 1.0)))
    vfov = 2.0 * math.atan(SENSOR_H_MM / (2.0 * max(fov_mm, 1.0)))
    # subject-right (u>0.5) → aim target left of the subject so it falls on the right; likewise
    # subject-low (v>0.5) → aim up. (Verified via Rodrigues about the up / right axes.)
    yaw = (u - 0.5) * hfov
    pitch = (v - 0.5) * vfov
    vdir = rotate_about_axis(vdir, up, yaw)
    vdir = rotate_about_axis(vdir, right, pitch)
    return add(pos, scale(normalize(vdir), dist))


# Horizontal standpoint directions in a Z-up world (unit, pointing FROM subject TO camera).
_ZUP_DIR = {
    Standpoint.FRONT: (0.0, -1.0, 0.0),
    Standpoint.BACK: (0.0, 1.0, 0.0),
    Standpoint.LEFT: (-1.0, 0.0, 0.0),
    Standpoint.RIGHT: (1.0, 0.0, 0.0),
    Standpoint.THREE_QUARTER: (0.7071, -0.7071, 0.0),
    Standpoint.EYE: (0.0, -1.0, 0.0),
    Standpoint.FRONT_HIGH: (0.0, -1.0, 0.0),
    Standpoint.FRONT_LOW: (0.0, -1.0, 0.0),
    Standpoint.TOP: (0.0, 0.0, 0.0),  # straight down; handled specially
}


def _standpoint_dir(sp: Standpoint, up_axis: UpAxis) -> Vec3:
    """Horizontal direction from subject to camera (Z-up); remapped for Y-up."""
    d = _ZUP_DIR.get(sp, (0.7071, -0.7071, 0.0))
    if up_axis == UpAxis.Y:
        # swap the Z (horizontal-depth) and Y (up) roles: (x, y, z)_zup -> (x, z, y)_yup
        return (d[0], d[2], d[1])
    return d


# ------------------------------------------------------------------ the resolver

def _subject_center_and_base(target: NodeInfo, up_axis: UpAxis) -> Tuple[Vec3, float]:
    if target.bbox is not None:
        center = target.bbox.center
        up_idx = 2 if up_axis == UpAxis.Z else 1
        base = target.bbox.lo[up_idx]
        return center, base
    if target.pivot is not None:
        up_idx = 2 if up_axis == UpAxis.Z else 1
        return target.pivot, target.pivot[up_idx]
    return (0.0, 0.0, 0.0), 0.0


def resolve_camera(
    anchor: Anchor,
    target: NodeInfo,
    up_axis: UpAxis = UpAxis.Z,
    meters_to_units: float = 1.0,
) -> CameraState:
    """Resolve a single anchor into a concrete camera pose from the subject's geometry."""
    up = _up_vec(up_axis)
    up_idx = 2 if up_axis == UpAxis.Z else 1
    center, base = _subject_center_and_base(target, up_axis)

    dist = max(anchor.distance_m, 0.1) * meters_to_units
    height = anchor.height_m * meters_to_units

    if anchor.standpoint == Standpoint.TOP:
        pos = list(center)
        pos[up_idx] = base + max(height, dist)
        return CameraState(pos=tuple(pos), look_at=center, fov_mm=35.0, up=up)  # type: ignore[arg-type]

    hdir = _standpoint_dir(anchor.standpoint, up_axis)
    pos = add(center, scale(hdir, dist))
    # place at the requested height above the subject base, regardless of hdir's vertical
    pos = list(pos)  # type: ignore[assignment]
    vertical = base + height
    if anchor.standpoint == Standpoint.FRONT_HIGH:
        vertical = base + height + 0.5 * dist
    elif anchor.standpoint == Standpoint.FRONT_LOW:
        vertical = base + max(0.1 * meters_to_units, height - 0.4 * dist)
    pos[up_idx] = vertical
    return CameraState(pos=tuple(pos), look_at=center, fov_mm=35.0, up=up)  # type: ignore[arg-type]


# ------------------------------------------------------------------ path sampling

def _ease_t(t: float, ease) -> float:
    """Normalized time 0..1 -> eased 0..1."""
    from .models import Ease
    if ease == Ease.LINEAR:
        return t
    if ease == Ease.IN:
        return t * t
    if ease == Ease.OUT:
        return 1.0 - (1.0 - t) * (1.0 - t)
    # IN_OUT (smoothstep)
    return t * t * (3.0 - 2.0 * t)


def sample_path(
    start: CameraState,
    path: PathSpec,
    move: CameraMove,
    target: NodeInfo,
    duration_s: float,
    up_axis: UpAxis = UpAxis.Z,
    meters_to_units: float = 1.0,
    n: int = 2,
) -> List[Tuple[float, CameraState]]:
    """Produce (t_s, CameraState) keyframes for a move. Deterministic; unit-tested.

    ``n`` is the number of keyframes (>=2 for moving shots; orbits use more internally for
    a smooth arc but we emit start/mid/end to keep the curve editable in Max)."""
    up = _up_vec(up_axis)
    center = _subject_center_and_base(target, up_axis)[0]
    end = start

    if move in (CameraMove.STATIC, CameraMove.ESTABLISH):
        if move == CameraMove.STATIC:
            return [(0.0, start), (duration_s, start)]
        # establish: hold wide, then gentle push IN (negative = toward subject)
        pushed = _dolly(start, center, -0.15 * length(sub(start.pos, center)))
        return [(0.0, start), (duration_s * 0.4, start), (duration_s, pushed)]

    if move == CameraMove.ORBIT or move == CameraMove.PRODUCT_360:
        deg = path.degrees or (360.0 if move == CameraMove.PRODUCT_360 else 60.0)
        return _orbit_keys(start, center, up, deg, duration_s, samples=max(n, 5))

    if move in (CameraMove.PUSH_IN, CameraMove.PULL_OUT):
        d = (path.distance_m or 1.0) * meters_to_units
        sign = -1.0 if move == CameraMove.PUSH_IN else 1.0
        end = _dolly(start, center, sign * d)
        return [(0.0, start), (duration_s, end)]

    if move in (CameraMove.CRANE_UP, CameraMove.CRANE_DOWN, CameraMove.CRANE_REVEAL):
        d = (path.distance_m or 1.5) * meters_to_units
        sign = 1.0 if move != CameraMove.CRANE_DOWN else -1.0
        moved = CameraState(add(start.pos, scale(up, sign * d)), start.look_at, start.fov_mm, up)
        if move == CameraMove.CRANE_REVEAL:
            # up-and-over: also push slightly toward subject as it rises (negative = in)
            moved = _dolly(moved, center, -0.2 * length(sub(start.pos, center)))
        return [(0.0, start), (duration_s, moved)]

    if move == CameraMove.TRACK:
        d = (path.distance_m or 1.0) * meters_to_units
        view = normalize(sub(start.look_at, start.pos))
        right = normalize(cross(view, up))
        moved = CameraState(add(start.pos, scale(right, d)), add(start.look_at, scale(right, d)), start.fov_mm, up)
        return [(0.0, start), (duration_s, moved)]

    if move == CameraMove.DOLLY_ZOOM:
        d = (path.distance_m or 1.0) * meters_to_units
        d0 = length(sub(start.pos, center))
        end_pos = _dolly(start, center, -d).pos
        d1 = length(sub(end_pos, center))
        # keep subject size: fov scales with distance ratio
        end_fov = start.fov_mm * (d1 / d0 if d0 else 1.0)
        end = CameraState(end_pos, start.look_at, end_fov, up)
        return [(0.0, start), (duration_s, end)]

    if move in (CameraMove.TILT, CameraMove.PAN):
        axis = up if move == CameraMove.PAN else normalize(cross(normalize(sub(start.look_at, start.pos)), up))
        ang = math.radians(path.degrees or 20.0)
        view = sub(start.look_at, start.pos)
        new_look = add(start.pos, rotate_about_axis(view, axis, ang))
        end = CameraState(start.pos, new_look, start.fov_mm, up)
        return [(0.0, start), (duration_s, end)]

    # BEZIER / fallback: start -> end via provided control points resolved elsewhere
    return [(0.0, start), (duration_s, start)]


def _dolly(cam: CameraState, center: Vec3, distance: float) -> CameraState:
    """Move the camera along the subject axis. Positive = PULL OUT (away from subject),
    negative = PUSH IN (toward subject)."""
    outward = normalize(sub(cam.pos, center))   # points from subject to camera
    new_pos = add(cam.pos, scale(outward, distance))
    return CameraState(new_pos, cam.look_at, cam.fov_mm, cam.up)


def _orbit_keys(
    start: CameraState, center: Vec3, up: Vec3, degrees: float, duration_s: float, samples: int
) -> List[Tuple[float, CameraState]]:
    keys: List[Tuple[float, CameraState]] = []
    radial = sub(start.pos, center)
    total = math.radians(degrees)
    for i in range(samples):
        f = i / (samples - 1)
        ang = total * f
        p = add(center, rotate_about_axis(radial, up, ang))
        keys.append((duration_s * f, CameraState(p, center, start.fov_mm, up)))
    return keys
