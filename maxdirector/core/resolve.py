"""Resolve an AuthoringPlan into concrete camera states — PURE (the MVP backbone).

Because the digest already carries every subject's real bbox/pivot, turning the anchor-based
plan into actual keyframed camera poses is deterministic and fully testable off-Max. The
bridge then just *applies* these states (create camera, set keys) and reads them back.
"""

from __future__ import annotations

from dataclasses import replace
from typing import List, Optional

from .anchors import resolve_camera, sample_path
from .models import (
    AuthoringPlan,
    CameraMove,
    CameraState,
    Digest,
    NodeInfo,
    ResolvedShot,
)

# Approximate metre→scene-unit factors by unit name. The AUTHORITATIVE factor comes from
# Max's system unit (bridge passes it in); this is the off-Max fallback for tests/preview.
_UNIT_TO_METERS = {
    "meters": 1.0, "metres": 1.0, "m": 1.0,
    "centimeters": 0.01, "centimetres": 0.01, "cm": 0.01,
    "millimeters": 0.001, "millimetres": 0.001, "mm": 0.001,
    "inches": 0.0254, "inch": 0.0254, "in": 0.0254,
    "feet": 0.3048, "foot": 0.3048, "ft": 0.3048,
}


def meters_to_units(units: str) -> float:
    """How many scene units make one metre (inverse of unit size in metres)."""
    per = _UNIT_TO_METERS.get((units or "").strip().lower())
    return 1.0 / per if per else 1.0


def _move_from_kind(kind: str) -> CameraMove:
    try:
        return CameraMove(kind)
    except ValueError:
        return CameraMove.STATIC


def _fallback_target(digest: Digest) -> NodeInfo:
    """When the anchor subject is missing, aim at the scene centre so we never crash."""
    from .models import BBox
    b = digest.scene_bounds or BBox((-1, -1, 0), (1, 1, 1))
    return NodeInfo(handle=-1, name="__scene__", klass="__scene__", bbox=b)


def resolve_plan(plan: AuthoringPlan, digest: Digest, scale: Optional[float] = None) -> List[ResolvedShot]:
    s = scale if scale is not None else meters_to_units(digest.units)
    out: List[ResolvedShot] = []
    for shot in plan.shots:
        target = digest.node_by_name(shot.anchor.relative_to) or _fallback_target(digest)
        start = resolve_camera(shot.anchor, target, digest.up_axis, s)
        start = replace(start, fov_mm=shot.camera.fov_mm)  # anchor doesn't set lens; the camera does
        move = _move_from_kind(shot.path.kind)
        around = (digest.node_by_name(shot.path.around) if shot.path.around else None) or target
        states = sample_path(start, shot.path, move, around, shot.duration_s, digest.up_axis, s)
        # apply any explicit keyframe FOV overrides onto the matching endpoints
        states = _apply_fov_overrides(states, shot)
        out.append(ResolvedShot(id=shot.id, camera_name=shot.camera.name, states=states))
    return out


def _apply_fov_overrides(states, shot) -> List:
    if not shot.keyframes:
        return states
    fovs = [(k.t_s, k.fov_mm) for k in shot.keyframes if k.fov_mm is not None]
    if not fovs:
        return states
    out = []
    for t_s, st in states:
        # nearest keyframe fov by time
        best = min(fovs, key=lambda kv: abs(kv[0] - t_s))
        out.append((t_s, CameraState(st.pos, st.look_at, best[1], st.up)))
    return out
