"""Authoring-Plan schema (stage ⑤) — the technical plan, parsed + validated + clamped.

Anchor-based (no world coordinates). Every class/track/format is checked against the
verified pack; every referenced node against the digest; every existing-node animation op
against the guards. Illegal params are rejected or clamped HERE, before the bridge resolves
anchors to transforms — so nothing that reaches the scene is out of range or points at a
node that doesn't exist.
"""

from __future__ import annotations

from typing import List, Tuple

from . import guards
from .models import (
    Anchor,
    AnimOp,
    AuthoringPlan,
    CameraSpec,
    EnvSpec,
    Ease,
    Keyframe,
    LightOp,
    PathSpec,
    PlanShot,
    RenderBackend,
    RenderShot,
    RenderSpec,
    ScoutAnchor,
    Standpoint,
    Digest,
)
from .packs import VerifiedPack, default_vray_pack

PLAN_SCHEMA_HINT = {
    "shots": [{
        "id": "s1",
        "camera": {"name": "MD_Cam_01", "class": "VRayPhysicalCamera", "create": True, "fov_mm": 24},
        "_placement": "PREFER scout_anchor — start from a scout view you SAW and nudge; use anchor only if a named object is clearly the subject",
        "scout_anchor": {"from_scout": 0, "dolly_m": 1.5, "truck_m": 0.5, "pedestal_m": -0.2,
                         "look_shift": [0.5, 0.45], "fov_mm": 24},
        "anchor": {"relative_to": "<node name>", "standpoint": "three-quarter",
                   "distance_m": 2.5, "height_m": 1.5, "subject_screen_pos": [0.5, 0.45]},
        "path": {"kind": "orbit", "around": "<node or omit>", "degrees": 30, "distance_m": 0},
        "keyframes": [{"t_s": 0, "ease": "in_out", "fov_mm": 24}, {"t_s": 6, "ease": "out", "fov_mm": 30}],
        "duration_s": 6,
    }],
    "lights": [{"op": "create", "class": "VRaySun", "time_of_day": "17:30"}],
    "environment": {"hdri_asset": "polyhaven:kloofendal_48d", "gamma": 2.2},
    "animation": [{"op": "keyframe", "node": "<safe node>", "track": "rotation",
                   "safe_required": True, "keys": [{"t_s": 0, "value": [0, 0, 0]}]}],
    "render": {"backend": "vray", "size": [3840, 2160], "fps": 24, "format": "exr",
               "shots": [{"id": "s1", "frames": [0, 144], "output": "renders/s1.####.exr"}]},
    "status": "ready", "assumptions": [],
}


def _standpoint(v: str) -> Standpoint:
    try:
        return Standpoint(v)
    except ValueError:
        return Standpoint.THREE_QUARTER


def _anchor(d: dict, pack: VerifiedPack) -> Anchor:
    sp = _anchor_screen(d.get("subject_screen_pos"))
    return Anchor(
        relative_to=str(d.get("relative_to", "")),
        standpoint=_standpoint(str(d.get("standpoint", "three-quarter"))),
        distance_m=pack.clamp_distance(_num(d.get("distance_m"), 3.0)),
        height_m=_num(d.get("height_m"), 1.5),
        subject_screen_pos=sp,
    )


def _anchor_screen(v) -> tuple:
    if isinstance(v, (list, tuple)) and len(v) >= 2:
        return (_num(v[0], 0.5), _num(v[1], 0.5), 0.0)
    return (0.5, 0.5, 0.0)


def _scout_anchor(d: dict, pack: VerifiedPack) -> ScoutAnchor:
    fov = d.get("fov_mm")
    return ScoutAnchor(
        from_scout=int(_num(d.get("from_scout"), 0)),
        dolly_m=_num(d.get("dolly_m"), 0.0),
        truck_m=_num(d.get("truck_m"), 0.0),
        pedestal_m=_num(d.get("pedestal_m"), 0.0),
        look_shift=_anchor_screen(d.get("look_shift")),
        fov_mm=pack.clamp_fov(_num(fov, 35.0)) if fov is not None else None,
    )


def parse_plan(
    obj: dict, digest: Digest, pack: VerifiedPack = None, opted_in_nodes: set = None
) -> Tuple[AuthoringPlan, List[str]]:
    """Parse + validate + clamp. Returns (plan, errors). Errors are hard problems the user
    must see (illegal node/class); soft repairs are folded silently via clamping."""
    pack = pack or default_vray_pack()
    opted_in_nodes = opted_in_nodes or set()
    errors: List[str] = []
    plan = AuthoringPlan()
    names = {n.name for n in digest.nodes}
    scout_ids = {sv.id for sv in digest.scouts}

    for i, s in enumerate(obj.get("shots", []) or []):
        if not isinstance(s, dict):
            continue
        try:
            cam = s.get("camera", {}) or {}
            klass = str(cam.get("class", "VRayPhysicalCamera"))
            if klass not in pack.camera_classes:
                errors.append(f"shot {s.get('id', i)}: camera class {klass!r} not in pack")
                klass = "VRayPhysicalCamera"

            # PRIMARY: vision-first scout anchor. SECONDARY: object-relative anchor.
            sa_raw = s.get("scout_anchor")
            scout_anchor = None
            anchor = None
            fov_default = 35.0
            if isinstance(sa_raw, dict) and sa_raw.get("from_scout") is not None:
                scout_anchor = _scout_anchor(sa_raw, pack)
                if scout_ids and scout_anchor.from_scout not in scout_ids:
                    errors.append(f"shot {s.get('id', i)}: from_scout {scout_anchor.from_scout} not a scout id")
                if scout_anchor.fov_mm is not None:
                    fov_default = scout_anchor.fov_mm
            else:
                anchor = _anchor(s.get("anchor", {}) or {}, pack)
                if anchor.relative_to and anchor.relative_to not in names:
                    errors.append(f"shot {s.get('id', i)}: anchor subject {anchor.relative_to!r} not in scene")

            path = s.get("path", {}) or {}
            around = path.get("around")
            if around and around not in names:
                errors.append(f"shot {s.get('id', i)}: path.around {around!r} not in scene")
                around = None
            plan.shots.append(PlanShot(
                id=str(s.get("id", f"s{i+1}")),
                camera=CameraSpec(
                    name=str(cam.get("name", f"MD_Cam_{i+1:02d}")),
                    klass=klass,
                    create=bool(cam.get("create", True)),
                    fov_mm=pack.clamp_fov(_num(cam.get("fov_mm"), fov_default)),
                ),
                anchor=anchor,
                scout_anchor=scout_anchor,
                path=PathSpec(
                    kind=str(path.get("kind", "static")),
                    around=around,
                    degrees=_num(path.get("degrees"), 0.0),
                    distance_m=pack.clamp_distance(_num(path.get("distance_m"), 0.0)) if path.get("distance_m") else 0.0,
                ),
                keyframes=_keyframes(s.get("keyframes", []) or [], pack),
                duration_s=_num(s.get("duration_s"), 4.0),
            ))
        except Exception as e:  # a single malformed shot must not sink the whole plan
            errors.append(f"shot #{i} ({s.get('id', '?')}) could not be parsed: {e}")

    for lo in obj.get("lights", []) or []:
        if not isinstance(lo, dict):
            continue
        klass = str(lo.get("class", "VRayLight"))
        if klass not in (pack.light_classes | pack.sun_classes):
            errors.append(f"light class {klass!r} not in pack")
            continue
        plan.lights.append(LightOp(
            op=str(lo.get("op", "create")), klass=klass, name=lo.get("name"),
            subtype=lo.get("subtype"), time_of_day=lo.get("time_of_day"),
            target_node=lo.get("target_node"),
            multiplier=_clampf(lo.get("multiplier"), pack.intensity_range),
            temp_k=_clampf(lo.get("temp_k"), pack.temp_k_range),
        ))

    env = obj.get("environment", {}) or {}
    plan.environment = EnvSpec(hdri_asset=env.get("hdri_asset"), gamma=float(env.get("gamma", 2.2) or 2.2))

    for ao in obj.get("animation", []) or []:
        if not isinstance(ao, dict):
            continue
        node = str(ao.get("node", ""))
        track = str(ao.get("track", "position"))
        if node not in names:
            errors.append(f"animation node {node!r} not in scene — skipped")
            continue
        if track not in pack.tracks:
            errors.append(f"animation track {track!r} not legal — skipped")
            continue
        ninfo = digest.node_by_name(node)
        allowed, msg = guards.check_anim(ninfo, opted_in=node in opted_in_nodes) if ninfo else (False, "unknown node")
        if not allowed:
            errors.append(f"animation on {node!r} {msg}")
            continue
        plan.animation.append(AnimOp(
            op=str(ao.get("op", "keyframe")), node=node, track=track,
            safe_required=bool(ao.get("safe_required", True)),
            keys=[k for k in (ao.get("keys") or []) if isinstance(k, dict)],
        ))

    plan.render = _render(obj.get("render", {}) or {}, pack)
    plan.status = str(obj.get("status", "ready"))
    plan.assumptions = [str(a) for a in (obj.get("assumptions") or [])]
    return plan, errors


def _keyframes(raw, pack: VerifiedPack) -> List[Keyframe]:
    out = []
    for k in raw:
        if not isinstance(k, dict):
            continue
        try:
            ease = Ease(str(k.get("ease", "in_out")))
        except ValueError:
            ease = Ease.IN_OUT
        fov = k.get("fov_mm")
        out.append(Keyframe(
            t_s=_num(k.get("t_s"), 0.0), ease=ease,
            fov_mm=pack.clamp_fov(_num(fov, 35.0)) if fov is not None else None,
        ))
    return out


def _render(d: dict, pack: VerifiedPack) -> RenderSpec:
    try:
        backend = RenderBackend(str(d.get("backend", "vray")))
    except ValueError:
        backend = RenderBackend.VRAY
    fmt = str(d.get("format", "exr"))
    if fmt not in pack.render_formats:
        fmt = "exr"
    size = d.get("size", [1920, 1080])
    if not (isinstance(size, (list, tuple)) and len(size) >= 2):
        size = [1920, 1080]
    shots = []
    for rs in d.get("shots", []) or []:
        if isinstance(rs, dict) and "frames" in rs:
            fr = rs["frames"]
            shots.append(RenderShot(id=str(rs.get("id", "")), frames=(int(fr[0]), int(fr[1])),
                                    output=str(rs.get("output", ""))))
    return RenderSpec(backend=backend, size=(int(size[0]), int(size[1])),
                      fps=int(d.get("fps", 24) or 24), fmt=fmt, shots=shots)


def _clampf(v, rng):
    if v is None:
        return None
    n = _num(v, None)
    return None if n is None else max(rng[0], min(rng[1], n))


def _num(v, default):
    """Tolerant float parse — the LLM may hand us '24', 24, or nonsense. Never raises."""
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default
