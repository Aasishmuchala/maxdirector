"""Scout views — the visual digest. PURE geometry.

We auto-place a handful of scout cameras that cover the scene, render fast thumbnails
(bridge), and show those IMAGES to the multimodal model. The model then designs shots by
picking the scout view closest to what it wants and nudging — reasoning over pixels it can
actually see, with KNOWN camera poses, instead of guessing 3D from bounding boxes and messy
node names. This is the load-bearing fix for placement quality.

``scout_poses`` computes the camera poses (deterministic, tested). ``resolve_scout_camera``
turns a model's 'from scout N, nudge' into a real pose. Both are unit-tested off-Max.
"""

from __future__ import annotations

from typing import List, Optional

from .anchors import add, cross, length, normalize, scale, sub
from .models import BBox, Category, CameraState, NodeInfo, ScoutAnchor, ScoutView, UpAxis, Vec3


def _up(up_axis: UpAxis) -> Vec3:
    return (0.0, 0.0, 1.0) if up_axis == UpAxis.Z else (0.0, 1.0, 0.0)


def _dominant_feature(nodes, up_i: int, bounds: BBox) -> Optional[NodeInfo]:
    """The geometry node with the largest VERTICAL extent — usually the hero wall / window /
    tall feature (the floor has huge horizontal but tiny vertical extent, so it loses). Used
    to compose a couple of scouts on something worth framing, not just room-centre."""
    best, best_h = None, 0.0
    span = bounds.size[up_i] or 1.0
    for n in nodes or []:
        if n.category != Category.GEOMETRY or n.bbox is None:
            continue
        h = n.bbox.size[up_i]
        # ignore floor-like slabs (very flat) and things spanning the whole room height (walls
        # are fine, but a node == full room height is likely a boundary wall; still ok)
        if h > best_h and h < span * 1.2:
            best, best_h = n, h
    return best


def scout_poses(
    bounds: BBox,
    up_axis: UpAxis = UpAxis.Z,
    meters_to_units: float = 1.0,
    eye_m: float = 1.6,
    nodes: Optional[List[NodeInfo]] = None,
) -> List[ScoutView]:
    """Covers a room with VARIETY the model can reason over: 4 wide eye-level corners (to read
    the space), 1 elevated 3/4, 1 plan, plus up to 2 deliverable-like 35mm views composed on
    the dominant vertical feature (low-hero + high). Z-up default; Y-up swaps axes."""
    c = bounds.center
    lo, hi = bounds.lo, bounds.hi
    diag = bounds.diagonal
    up = _up(up_axis)
    up_i = 2 if up_axis == UpAxis.Z else 1
    floor = lo[up_i]
    eye = floor + eye_m * meters_to_units

    def _at_height(p, h):
        q = list(p)
        q[up_i] = h
        return tuple(q)

    ax = [i for i in range(3) if i != up_i]
    corners_xy = [
        (lo[ax[0]], lo[ax[1]]), (hi[ax[0]], lo[ax[1]]),
        (hi[ax[0]], hi[ax[1]]), (lo[ax[0]], hi[ax[1]]),
    ]
    views: List[ScoutView] = []
    look = _at_height(c, eye)
    for i, (u, v) in enumerate(corners_xy):
        p = [0.0, 0.0, 0.0]
        p[ax[0]], p[ax[1]] = u, v
        p[up_i] = eye
        pos = add(tuple(p), scale(sub(look, tuple(p)), 0.08))  # inset off the wall
        views.append(ScoutView(i, f"corner_{i}", CameraState(pos, look, fov_mm=24.0, up=up)))

    p0 = list(views[0].pose.pos)
    p0[up_i] = floor + eye + 0.4 * diag
    views.append(ScoutView(4, "high_3q", CameraState(tuple(p0), c, fov_mm=28.0, up=up)))

    top = list(c)
    top[up_i] = hi[up_i] + 0.6 * diag
    plan_up = (0.0, 1.0, 0.0) if up_axis == UpAxis.Z else (0.0, 0.0, 1.0)
    views.append(ScoutView(5, "plan", CameraState(tuple(top), c, fov_mm=18.0, up=plan_up)))

    # feature-directed, deliverable-like 35mm views composed on the dominant vertical feature
    feature = _dominant_feature(nodes, up_i, bounds)
    if feature is not None:
        fc = feature.bbox.center
        toward = sub(c, fc)                      # stand between the feature and room centre
        d = length(toward)
        dir_ = normalize(toward) if d > 1e-6 else normalize(sub(c, lo))
        standoff = max(0.35 * diag, feature.bbox.diagonal)
        for j, (label, h_m) in enumerate((("feature_low", 1.1), ("feature_high", 2.3))):
            pos = add(fc, scale(dir_, standoff))
            pos = _at_height(pos, floor + h_m * meters_to_units)
            views.append(ScoutView(6 + j, label, CameraState(pos, fc, fov_mm=35.0, up=up)))
    return views


def resolve_scout_camera(
    sa: ScoutAnchor, scout: ScoutView, up_axis: UpAxis = UpAxis.Z, meters_to_units: float = 1.0
) -> CameraState:
    """Nudge from a scout's known pose along its own camera axes. Deterministic."""
    up = _up(up_axis)
    P, L = scout.pose.pos, scout.pose.look_at
    view = normalize(sub(L, P))
    right = normalize(cross(view, up))
    upv = normalize(cross(right, view))
    m = meters_to_units
    pos = add(P, add(scale(view, sa.dolly_m * m), add(scale(right, sa.truck_m * m), scale(upv, sa.pedestal_m * m))))
    fov = sa.fov_mm if sa.fov_mm is not None else scout.pose.fov_mm
    return CameraState(pos=pos, look_at=L, fov_mm=fov, up=up)
