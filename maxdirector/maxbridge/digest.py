"""collect_digest() — the 'understand the project' reader. pymxs only.

Extends LightMatch's ``collect_census`` (cameras/lights/suns/env/gamma) with a geometry
inventory (named nodes + world bbox + category + poly count) and the animation-safety guard
flags (skin/bone/instance/xref/scripted/group). Every read is guarded so one odd node can't
sink the digest. Returns the PURE ``core.models.Digest`` the rest of the pipeline consumes.
"""

from __future__ import annotations

from typing import Optional

from ..core.models import (
    BBox,
    CameraInfo,
    Category,
    Digest,
    LightInfo,
    NodeInfo,
    UpAxis,
    Vec3,
)
from . import maxscript
from .renderer_query import renderer_name, is_vray


def _rt():
    import pymxs
    return pymxs.runtime


def _try(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _world_bbox(rt, n) -> Optional[BBox]:
    try:
        pts = rt.nodeGetBoundingBox(n, rt.matrix3(1))  # identity = world space
        lo = (float(pts[0].x), float(pts[0].y), float(pts[0].z))
        hi = (float(pts[1].x), float(pts[1].y), float(pts[1].z))
        return BBox(lo=lo, hi=hi)
    except Exception:
        return None


def _pivot(rt, n) -> Optional[Vec3]:
    try:
        p = n.pos
        return (float(p.x), float(p.y), float(p.z))
    except Exception:
        return None


def _category(rt, n) -> Category:
    sc = str(_try(lambda: rt.superClassOf(n), "")).lower()
    cls = str(_try(lambda: rt.classOf(n), "")).lower()
    if "vraysun" in cls:
        return Category.SUN
    if sc == "light":
        return Category.LIGHT
    if sc == "camera":
        return Category.CAMERA
    if sc == "geometryclass":
        return Category.GEOMETRY
    if sc == "helper":
        return Category.HELPER
    return Category.OTHER


def _has_modifier(rt, n, *names) -> bool:
    try:
        for m in n.modifiers:
            if str(rt.classOf(m)) in names:
                return True
    except Exception:
        pass
    return False


def _is_instanced(rt, n) -> bool:
    try:
        bo = n.baseObject
        deps = rt.refs.dependentNodes(bo)
        return int(deps.count) > 1
    except Exception:
        return False


def collect_digest() -> Digest:
    rt = _rt()
    scripted = maxscript.scripted_handles()
    d = Digest(
        units=str(_try(lambda: rt.units.SystemType, "") or "").lower() or "generic",
        up_axis=UpAxis.Z,
        renderer=renderer_name(),
        is_vray=is_vray(),
        frame_rate=float(_try(lambda: rt.frameRate, 30.0) or 30.0),
    )

    lo = [1e30, 1e30, 1e30]
    hi = [-1e30, -1e30, -1e30]
    for n in _try(lambda: list(rt.objects), []) or []:
        cat = _category(rt, n)
        if cat == Category.CAMERA:
            d.cameras.append(CameraInfo(
                name=str(_try(lambda: n.name, "?")), klass=str(_try(lambda: rt.classOf(n), "?")),
                fov_mm=_try(lambda: float(n.fov)), exposure_on=_try(lambda: bool(n.exposure)),
            ))
            continue
        if cat in (Category.LIGHT, Category.SUN):
            info = LightInfo(name=str(_try(lambda: n.name, "?")), klass=str(_try(lambda: rt.classOf(n), "?")),
                             on=_try(lambda: bool(n.on)), multiplier=_try(lambda: float(n.multiplier)))
            (d.suns if cat == Category.SUN else d.lights).append(info)
            continue

        bbox = _world_bbox(rt, n)
        if bbox is not None:
            for i in range(3):
                lo[i] = min(lo[i], bbox.lo[i])
                hi[i] = max(hi[i], bbox.hi[i])
        handle = int(_try(lambda: rt.getHandleByAnim(n), 0) or 0)
        node = NodeInfo(
            handle=handle,
            name=str(_try(lambda: n.name, "?")),
            klass=str(_try(lambda: rt.classOf(n), "?")),
            category=cat,
            bbox=bbox,
            pivot=_pivot(rt, n),
            poly_count=int(_try(lambda: rt.getPolygonCount(n)[0], 0) or 0),
            is_skinned=_has_modifier(rt, n, "Skin", "Physique"),
            is_bone=bool(_try(lambda: rt.isKindOf(n, rt.BoneGeometry), False)) or "bone" in str(_try(lambda: rt.classOf(n), "")).lower(),
            is_instanced=_is_instanced(rt, n),
            is_xref=bool(_try(lambda: rt.isKindOf(n, rt.XRefObject), False)) if hasattr(rt, "XRefObject") else False,
            has_scripted_ctrl=handle in scripted,
            is_group_member=bool(_try(lambda: rt.isGroupMember(n), False)),
        )
        d.nodes.append(node)

    if hi[0] > lo[0]:
        d.scene_bounds = BBox(lo=tuple(lo), hi=tuple(hi))  # type: ignore[arg-type]

    # environment / exposure / gamma (LightMatch census)
    env = _try(lambda: rt.environmentMap)
    if env is not None:
        d.environment_map = str(_try(lambda: env.filename, "") or _try(lambda: env.HDRIMapName, "") or "set")
    ec = _try(lambda: rt.SceneExposureControl.exposureControl)
    if ec is not None:
        ec_cls = str(_try(lambda: rt.classOf(ec), ""))
        d.exposure_control_active = bool(ec_cls) and ec_cls not in ("undefined", "NoExposureControl")
    d.gamma = float(_try(lambda: rt.displayGamma, 2.2) or 2.2) if _try(lambda: bool(rt.gammaCorrectionEnabled), False) else 1.0
    return d
