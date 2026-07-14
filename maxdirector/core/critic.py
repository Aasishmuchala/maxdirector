"""Geometric plan critic — PURE. The gate schema validation can't give you.

A plan can be perfectly *legal* (every param in range) and still be *bad*: camera inside a
wall, subject out of frame, path clipping through geometry, degenerate look-at. This critic
runs on the RESOLVED camera states (after the bridge computes transforms) against the
digest's real bounding boxes, and returns findings the pipeline can auto-repair or surface
before the preview. Coarse (bbox-level) by design — it catches the embarrassing failures
cheaply; the playblast + best-of-N scoring catch the subtle ones.
"""

from __future__ import annotations

import math
from typing import List

from .anchors import dot, length, normalize, sub
from .models import (
    BBox,
    CameraState,
    CriticFinding,
    Digest,
    ResolvedShot,
    Severity,
)

SENSOR_MM = 36.0  # full-frame horizontal sensor; fov_mm -> angle


def _hfov_rad(fov_mm: float) -> float:
    fov_mm = max(fov_mm, 1.0)
    return 2.0 * math.atan(SENSOR_MM / (2.0 * fov_mm))


def _subject_in_frustum(cam: CameraState, subject_center) -> bool:
    view = normalize(sub(cam.look_at, cam.pos))
    to_subj = sub(subject_center, cam.pos)
    d = length(to_subj)
    if d < 1e-6:
        return False
    to_subj_n = normalize(to_subj)
    ang = math.acos(max(-1.0, min(1.0, dot(view, to_subj_n))))
    return ang <= _hfov_rad(cam.fov_mm) * 0.6  # a little slack beyond half-angle


def _inside_any(p, boxes: List[BBox], pad: float) -> bool:
    return any(b.contains(p, pad=pad) for b in boxes)


def _subject_behind(cam: CameraState, center) -> bool:
    """True if the declared subject is behind the camera — always broken, never intentional."""
    view = normalize(sub(cam.look_at, cam.pos))
    to = sub(center, cam.pos)
    if length(to) < 1e-9:
        return False
    return dot(view, normalize(to)) < 0.0


def _nearest_node_size(center, digest: Digest) -> float:
    """Diagonal of the geometry node nearest the framing point — a proxy for subject size so
    the framing check works on scout shots (whose 'subject' is a look point, not an object)."""
    best_d, best = 1e30, 0.0
    for n in digest.nodes:
        if n.bbox is None:
            continue
        c = n.bbox.center
        d = sum((c[i] - center[i]) ** 2 for i in range(3))
        if d < best_d:
            best_d, best = d, n.bbox.diagonal
    return best


def _frame_fraction(cam: CameraState, center, subject_size: float):
    """Subject angular size as a fraction of the horizontal FOV (None if unknown)."""
    dist = length(sub(center, cam.pos))
    if dist < 1e-6 or subject_size <= 0:
        return None
    ang = 2.0 * math.atan((subject_size * 0.5) / dist)
    return ang / _hfov_rad(cam.fov_mm)


def _lerp(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def critique_shot(shot: ResolvedShot, digest: Digest, subject_center=None) -> List[CriticFinding]:
    findings: List[CriticFinding] = []
    boxes = [n.bbox for n in digest.nodes if n.bbox is not None]
    bounds = digest.scene_bounds
    diag = bounds.diagonal if bounds else 0.0
    # Exact containment: an anchor-placed camera sits distance_m from the subject centre,
    # well outside its bbox, so pad=0 gives no false "inside" while still catching a camera
    # that genuinely lands within a wall/object. (Shrinking by the diagonal collapses thin
    # walls to an empty range — the bug this replaces.)
    solid_pad = 0.0

    for t_s, cam in shot.states:
        # degenerate look-at
        if length(sub(cam.look_at, cam.pos)) < 1e-4:
            findings.append(CriticFinding(shot.id, "degenerate_lookat", Severity.BLOCK,
                                          "camera position equals its target"))
        # camera in the void (far outside the scene)
        if bounds is not None and not bounds.contains(cam.pos, pad=2.0 * diag):
            findings.append(CriticFinding(shot.id, "camera_in_void", Severity.BLOCK,
                                          f"camera at t={t_s:.1f}s is far outside the scene bounds"))
        # camera inside solid geometry
        if _inside_any(cam.pos, boxes, pad=solid_pad):
            findings.append(CriticFinding(shot.id, "camera_inside_solid", Severity.BLOCK,
                                          f"camera at t={t_s:.1f}s is inside an object"))
        # subject framing (the identity-defining gate — a good camera still fails here if the
        # hero subject is behind the lens or not in the frame)
        if subject_center is not None:
            if _subject_behind(cam, subject_center):
                findings.append(CriticFinding(shot.id, "subject_behind_camera", Severity.BLOCK,
                                              f"the subject is behind the camera at t={t_s:.1f}s"))
            elif not _subject_in_frustum(cam, subject_center):
                findings.append(CriticFinding(shot.id, "subject_out_of_frame", Severity.WARN,
                                              f"subject not within the frame at t={t_s:.1f}s"))

    # subject SIZE on the hero (first) frame — a speck or an overflow reads as a bad shot even
    # when geometry is legal. Size proxied from the nearest node so scout shots are covered too.
    if subject_center is not None and shot.states:
        size = _nearest_node_size(subject_center, digest)
        frac = _frame_fraction(shot.states[0][1], subject_center, size)
        if frac is not None:
            if frac < 0.12:
                findings.append(CriticFinding(shot.id, "subject_too_small", Severity.WARN,
                                              "subject reads as a speck — move closer or use a longer lens"))
            elif frac > 1.35:
                findings.append(CriticFinding(shot.id, "subject_too_close", Severity.WARN,
                                              "subject overflows the frame — pull back or widen"))

    # path collision: sample between consecutive keyframes
    for (t0, a), (t1, b) in zip(shot.states, shot.states[1:]):
        for k in range(1, 8):
            p = _lerp(a.pos, b.pos, k / 8.0)
            if _inside_any(p, boxes, pad=solid_pad):
                findings.append(CriticFinding(shot.id, "path_collision", Severity.WARN,
                                              f"camera path passes through geometry near t={t0:.1f}-{t1:.1f}s"))
                break
    return _dedupe(findings)


def _dedupe(findings: List[CriticFinding]) -> List[CriticFinding]:
    seen = set()
    out = []
    for f in findings:
        key = (f.shot_id, f.code)
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out


def has_blockers(findings: List[CriticFinding]) -> bool:
    return any(f.severity == Severity.BLOCK for f in findings)
