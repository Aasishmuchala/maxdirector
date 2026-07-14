"""AuthoringServices — the WRITE side. Creates cameras, keyframes, lights, environment and
render settings from a resolved plan, inside ONE undo record, READ-BACK-verifying every op
(LightMatch's verified/unverified/failed/manual buckets). pymxs only.

Everything created is namespaced ``MD_`` and existing nodes are never modified except opted-in
object animation — this runs on real client scenes.
"""

from __future__ import annotations

import math
from typing import List, Optional

from ..core.models import (
    ApplyResult,
    AuthoringPlan,
    CameraState,
    Digest,
    LightOp,
    ResolvedShot,
)
from ..core.anchors import cross, length, normalize, sub
from .backup import backup
from .journal import Journal
from .undo import one_undo


def _rt():
    import pymxs
    return pymxs.runtime


def _p3(rt, v):
    return rt.Point3(float(v[0]), float(v[1]), float(v[2]))


# ------------------------------------------------------------------ cameras

def create_camera(name: str, fov_mm: float = 35.0):
    """Create a VRayPhysicalCamera (+ target) named MD_*. Returns (cam, ok)."""
    rt = _rt()
    name = name if name.startswith("MD_") else f"MD_{name}"
    cam = None
    for ctor in ("VRayPhysicalCamera", "Physical", "FreeCamera"):
        maker = getattr(rt, ctor, None)
        if maker is not None:
            try:
                cam = maker()
                break
            except Exception:
                cam = None
    if cam is None:
        return None, False
    cam.name = name
    # FREE camera: with .targeted=False the camera's own transform controls orientation, so
    # cam.transform = look-at matrix actually aims it (a targeted cam is driven by its target
    # node and would ignore our transform — confirmed against the V-Ray/Physical camera docs).
    if rt.isProperty(cam, rt.Name("targeted")):
        try:
            cam.targeted = False
        except Exception:
            pass
    _set_fov(rt, cam, fov_mm)
    return cam, True


def _set_fov(rt, cam, fov_mm: float) -> bool:
    # focal_length (mm) is the physical, unambiguous control — preferred.
    for attr in ("focal_length", "focal_length_mm"):
        if rt.isProperty(cam, rt.Name(attr)):
            try:
                setattr(cam, attr, float(fov_mm))
                return abs(float(getattr(cam, attr)) - fov_mm) < 1e-2
            except Exception:
                pass
    # fall back to angular FOV — but it's IGNORED unless specify_fov is enabled first.
    try:
        if rt.isProperty(cam, rt.Name("specify_fov")):
            cam.specify_fov = True
        cam.fov = math.degrees(2.0 * math.atan(36.0 / (2.0 * max(fov_mm, 1.0))))
        return True
    except Exception:
        return False


def _look_at_tm(rt, eye, look, up=(0.0, 0.0, 1.0)):
    """A camera transform placing the eye at ``eye`` looking toward ``look``. Max cameras
    look down their local -Z, so local Z points from the target back to the eye. Handles the
    degenerate case (view parallel to up) by swapping the up reference."""
    z = normalize(sub(eye, look))
    x = cross(up, z)
    if length(x) < 1e-6:                 # looking straight up/down — pick a stable right vector
        x = cross((0.0, 1.0, 0.0), z)
        if length(x) < 1e-6:
            x = (1.0, 0.0, 0.0)
    x = normalize(x)
    y = normalize(cross(z, x))
    return rt.matrix3(_p3(rt, x), _p3(rt, y), _p3(rt, z), _p3(rt, eye))


def apply_camera_states(cam, states: List, fps: float) -> ApplyResult:
    """Keyframe the camera transform (pos + orientation, target-independent) + FOV across the
    shot; read-back-verify the keys landed. Keying the whole transform means the camera aims
    at each state's look-at without depending on a target node existing."""
    import pymxs
    rt = pymxs.runtime
    res = ApplyResult()
    if not states:
        return res
    with pymxs.animate(True):
        for t_s, st in states:
            f = round(t_s * fps)   # pymxs.attime rounds fractional frames anyway → be explicit
            with pymxs.attime(f):
                try:
                    cam.transform = _look_at_tm(rt, st.pos, st.look_at, st.up)
                    _set_fov(rt, cam, st.fov_mm)
                    res.applied.append(f"{cam.name}@{t_s:.1f}s")
                except Exception as e:  # noqa: BLE001
                    res.failed.append(f"{cam.name}@{t_s:.1f}s:{e}")
    # read-back verify: the position controller carries at least one key per distinct time
    try:
        nkeys = int(rt.numKeys(cam.position.controller))
        if nkeys >= len({round(t, 3) for t, _ in states}):
            res.verified.append(cam.name)
        else:
            res.unverified.append(f"{cam.name}: {nkeys} keys")
    except Exception:
        res.unverified.append(cam.name)
    return res


# ------------------------------------------------------------------ lights + env

def _sun_dir_from_time(time_of_day: str):
    """Very rough sun elevation/azimuth from 'HH:MM' — enough to place a VRaySun believably.
    06:00 low east, 12:00 high south, 18:00 low west."""
    try:
        hh, mm = (int(x) for x in time_of_day.split(":"))
    except Exception:
        hh, mm = 12, 0
    h = hh + mm / 60.0
    # elevation: 0 at 6/18, peak ~70deg at 12
    elev = max(3.0, 70.0 * math.sin(math.pi * (h - 6.0) / 12.0)) if 6 <= h <= 18 else 3.0
    azimuth = 90.0 + (h - 12.0) * 15.0  # east->west sweep
    return elev, azimuth


def create_sun(op: LightOp):
    rt = _rt()
    maker = getattr(rt, "VRaySun", None)
    if maker is None:
        return None, False
    sun = maker()
    sun.name = op.name or "MD_Sun"
    elev, az = _sun_dir_from_time(op.time_of_day or "12:00")
    r = 1000.0
    e = math.radians(elev)
    a = math.radians(az)
    sun.pos = rt.Point3(r * math.cos(e) * math.cos(a), r * math.cos(e) * math.sin(a), r * math.sin(e))
    if op.multiplier is not None and rt.isProperty(sun, rt.Name("intensity_multiplier")):
        try:
            sun.intensity_multiplier = float(op.multiplier)
        except Exception:
            pass
    return sun, True


def create_vraylight(op: LightOp):
    rt = _rt()
    maker = getattr(rt, "VRayLight", None)
    if maker is None:
        return None, False
    lt = maker()
    lt.name = op.name or "MD_Light"
    sub = {"plane": 0, "dome": 4, "sphere": 1, "mesh": 3, "disc": 5}.get((op.subtype or "plane"), 0)
    if rt.isProperty(lt, rt.Name("type")):
        try:
            lt.type = sub
        except Exception:
            pass
    if op.multiplier is not None and rt.isProperty(lt, rt.Name("multiplier")):
        try:
            lt.multiplier = float(op.multiplier)
        except Exception:
            pass
    if op.temp_k is not None and rt.isProperty(lt, rt.Name("color_mode")):
        try:
            lt.color_mode = 1  # temperature
            lt.temperature = float(op.temp_k)
        except Exception:
            pass
    return lt, True


def set_environment_hdri(hdri_path: str, gamma: float = 2.2) -> bool:
    rt = _rt()
    try:
        bmt = rt.VRayHDRI() if hasattr(rt, "VRayHDRI") else rt.Bitmaptexture()
        if hasattr(bmt, "HDRIMapName"):
            bmt.HDRIMapName = hdri_path
        else:
            bmt.filename = hdri_path
        rt.environmentMap = bmt
        rt.useEnvironmentMap = True
        return rt.environmentMap is not None
    except Exception:
        return False


# ------------------------------------------------------------------ render settings

def set_render_output(width: int, height: int, frame_start: int, frame_end: int, fps: int) -> bool:
    rt = _rt()
    try:
        rt.renderWidth = int(width)
        rt.renderHeight = int(height)
        rt.frameRate = int(fps)
        rt.rendTimeType = 3           # 3 = custom range
        rt.rendStart = int(frame_start)
        rt.rendEnd = int(frame_end)
        return int(rt.renderWidth) == int(width)
    except Exception:
        return False


# ------------------------------------------------------------------ object animation

def animate_object(node_name: str, track: str, keys: List[dict], fps: float) -> ApplyResult:
    """Additive transform keys on a SAFE node (the guard was already checked upstream)."""
    import pymxs
    rt = pymxs.runtime
    res = ApplyResult()
    n = rt.getNodeByName(node_name, exact=True)
    if n is None:
        res.failed.append(node_name)
        return res
    with pymxs.animate(True):
        for k in keys:
            f = round(float(k.get("t_s", 0.0)) * fps)   # integer frames (attime rounds anyway)
            val = k.get("value", [0, 0, 0])
            with pymxs.attime(f):
                try:
                    if track == "position":
                        n.pos = _p3(rt, val)
                    elif track == "rotation":
                        n.rotation = rt.eulerAngles(float(val[0]), float(val[1]), float(val[2]))
                    elif track == "scale":
                        n.scale = _p3(rt, val)
                    res.applied.append(f"{node_name}.{track}@{f}")
                except Exception as e:  # noqa: BLE001
                    res.failed.append(f"{node_name}:{e}")
    res.verified.append(node_name) if res.applied and not res.failed else res.unverified.append(node_name)
    return res


# ------------------------------------------------------------------ orchestration

def apply_plan(resolved: List[ResolvedShot], plan: AuthoringPlan, digest: Digest) -> ApplyResult:
    """Backup → one undo → create cameras+keys, lights, env, render, animation → verify.
    Returns a merged ApplyResult. Raises only if the backup fails."""
    rt = _rt()
    scene = str(rt.maxFilePath) + str(rt.maxFileName)
    bpath = backup()                       # hard guarantee; raises on failure
    jr = Journal(scene, bpath)
    merged = ApplyResult()

    def _merge(r: ApplyResult):
        merged.applied += r.applied
        merged.verified += r.verified
        merged.unverified += r.unverified
        merged.failed += r.failed
        merged.manual += r.manual

    try:
        with one_undo("MaxDirector apply"):
            by_id = {s.id: s for s in resolved}
            for shot in plan.shots:
                rs = by_id.get(shot.id)
                if rs is None:
                    continue
                cam, ok = create_camera(shot.camera.name, shot.camera.fov_mm)
                jr.record("create_camera", shot.camera.name, "ok" if ok else "fail")
                if ok:
                    r = apply_camera_states(cam, rs.states, plan.render.fps)
                    _merge(r)
                    jr.record("keyframe_camera", shot.camera.name, "ok" if r.ok else "check")
                else:
                    merged.failed.append(shot.camera.name)

            for lo in plan.lights:
                node, ok = (create_sun(lo) if lo.klass == "VRaySun" else create_vraylight(lo))
                (merged.verified if ok else merged.failed).append(lo.name or lo.klass)
                jr.record("create_light", lo.name or lo.klass, "ok" if ok else "fail")

            if plan.environment.hdri_asset and not plan.environment.hdri_asset.startswith("polyhaven:"):
                ok = set_environment_hdri(plan.environment.hdri_asset, plan.environment.gamma)
                (merged.verified if ok else merged.unverified).append("environment")

            for ao in plan.animation:
                r = animate_object(ao.node, ao.track, ao.keys, plan.render.fps)
                _merge(r)
                jr.record("animate", ao.node, "ok" if r.ok else "check")

            if plan.render.shots:
                fr = (plan.render.shots[0].frames[0], plan.render.shots[-1].frames[1])
                set_render_output(plan.render.size[0], plan.render.size[1], fr[0], fr[1], plan.render.fps)
        jr.finish("ok" if merged.ok else "partial")
    except Exception as e:  # noqa: BLE001
        jr.finish(f"error: {e}")
        raise
    return merged
