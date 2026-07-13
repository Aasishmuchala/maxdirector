"""Shared, PURE data model for MaxDirector.

Zero pymxs, zero torch. These dataclasses are the vocabulary every layer speaks:
the digest (what the scene IS), the brief (what you WANT), the storyboard (the creative
plan), and the authoring plan (the technical plan, expressed in SEMANTIC ANCHORS — never
raw world coordinates). The bridge resolves anchors to transforms; the critic vets them.

Design rules:
* Everything here is JSON-round-trippable (``to_dict`` / ``from_dict`` on the containers
  that cross the LLM or sidecar boundary) so the same types flow through Omega and tests.
* Vectors are plain 3-tuples of float; we keep a tiny vec helper set in ``core.anchors``
  rather than a heavy math dep.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

Vec3 = Tuple[float, float, float]


# --------------------------------------------------------------------------- enums

class UpAxis(str, Enum):
    Z = "Z"  # 3ds Max default
    Y = "Y"


class Category(str, Enum):
    GEOMETRY = "geometry"
    CAMERA = "camera"
    LIGHT = "light"
    SUN = "sun"
    HELPER = "helper"
    OTHER = "other"


class CameraMove(str, Enum):
    """Real-3D camera-move grammar (the moves-pack keys). Each resolves to a path."""
    STATIC = "static"
    PUSH_IN = "push_in"        # dolly toward subject
    PULL_OUT = "pull_out"      # dolly away
    ORBIT = "orbit"            # arc around subject
    CRANE_UP = "crane_up"
    CRANE_DOWN = "crane_down"
    CRANE_REVEAL = "crane_reveal"  # up-and-over reveal
    TRACK = "track"            # lateral track / crab
    DOLLY_ZOOM = "dolly_zoom"  # Vertigo: dolly + counter-FOV
    TILT = "tilt"
    PAN = "pan"
    ESTABLISH = "establish"    # wide hold then slow push
    PRODUCT_360 = "product_360"
    BEZIER = "bezier"          # free fly-through through control points


class Ease(str, Enum):
    LINEAR = "linear"
    IN = "in"
    OUT = "out"
    IN_OUT = "in_out"


class Standpoint(str, Enum):
    """Where the camera stands relative to the subject (resolved to a direction)."""
    FRONT = "front"
    FRONT_HIGH = "front-high"
    FRONT_LOW = "front-low"
    BACK = "back"
    LEFT = "left"
    RIGHT = "right"
    THREE_QUARTER = "three-quarter"
    TOP = "top"
    EYE = "eye"


class RenderBackend(str, Enum):
    VRAY = "vray"
    VANTAGE = "vantage"


class Severity(str, Enum):
    INFO = "info"
    WARN = "warn"
    BLOCK = "block"


# ------------------------------------------------------------------------ geometry

@dataclass(frozen=True)
class BBox:
    lo: Vec3
    hi: Vec3

    @property
    def center(self) -> Vec3:
        return tuple((a + b) / 2.0 for a, b in zip(self.lo, self.hi))  # type: ignore[return-value]

    @property
    def size(self) -> Vec3:
        return tuple(b - a for a, b in zip(self.lo, self.hi))  # type: ignore[return-value]

    @property
    def diagonal(self) -> float:
        return sum(s * s for s in self.size) ** 0.5

    def contains(self, p: Vec3, pad: float = 0.0) -> bool:
        return all(self.lo[i] - pad <= p[i] <= self.hi[i] + pad for i in range(3))

    def to_dict(self) -> dict:
        return {"lo": list(self.lo), "hi": list(self.hi)}

    @staticmethod
    def from_dict(d: dict) -> "BBox":
        return BBox(tuple(d["lo"]), tuple(d["hi"]))  # type: ignore[arg-type]


# ------------------------------------------------------------------------ the digest

@dataclass
class NodeInfo:
    """A scene node, reduced to what the Director + critic + anchor resolver need."""
    handle: int
    name: str
    klass: str
    category: Category = Category.OTHER
    bbox: Optional[BBox] = None
    pivot: Optional[Vec3] = None
    poly_count: int = 0
    # animation-safety flags (guards): an existing node is only auto-animatable if none set
    is_skinned: bool = False
    is_bone: bool = False
    is_instanced: bool = False
    is_xref: bool = False
    has_scripted_ctrl: bool = False
    is_group_member: bool = False

    def to_dict(self) -> dict:
        return {
            "handle": self.handle, "name": self.name, "klass": self.klass,
            "category": self.category.value,
            "bbox": self.bbox.to_dict() if self.bbox else None,
            "pivot": list(self.pivot) if self.pivot else None,
            "poly_count": self.poly_count,
            "flags": {
                "skinned": self.is_skinned, "bone": self.is_bone,
                "instanced": self.is_instanced, "xref": self.is_xref,
                "scripted": self.has_scripted_ctrl, "grouped": self.is_group_member,
            },
        }


@dataclass
class CameraInfo:
    name: str
    klass: str
    fov_mm: Optional[float] = None
    exposure_on: Optional[bool] = None


@dataclass
class LightInfo:
    name: str
    klass: str
    vray_type: Optional[str] = None
    on: Optional[bool] = None
    multiplier: Optional[float] = None


@dataclass
class Digest:
    """The 'understand the project' snapshot — deterministic pymxs reads (95%)."""
    units: str = ""
    up_axis: UpAxis = UpAxis.Z
    scene_bounds: Optional[BBox] = None
    renderer: str = ""
    is_vray: bool = False
    nodes: List[NodeInfo] = field(default_factory=list)
    cameras: List[CameraInfo] = field(default_factory=list)
    lights: List[LightInfo] = field(default_factory=list)
    suns: List[LightInfo] = field(default_factory=list)
    environment_map: Optional[str] = None
    gamma: Optional[float] = None
    exposure_control_active: Optional[bool] = None
    frame_rate: float = 30.0
    warnings: List[str] = field(default_factory=list)

    # -- convenience lookups (used by anchor resolver + validator) --

    def node_by_name(self, name: str) -> Optional[NodeInfo]:
        for n in self.nodes:
            if n.name == name:
                return n
        return None

    def named_targets(self) -> List[str]:
        """Node names the LLM may reference as anchor subjects (geometry + groups)."""
        return [n.name for n in self.nodes if n.category in (Category.GEOMETRY, Category.HELPER)]

    def to_prompt_dict(self) -> dict:
        """Bounded, privacy-safe view for the LLM prompt — names/bounds/counts, no paths."""
        return {
            "units": self.units,
            "up_axis": self.up_axis.value,
            "scene_bounds": self.scene_bounds.to_dict() if self.scene_bounds else None,
            "renderer": self.renderer,
            "frame_rate": self.frame_rate,
            "objects": [
                {
                    "name": n.name, "category": n.category.value,
                    "size": [round(s, 3) for s in n.bbox.size] if n.bbox else None,
                    "center": [round(c, 3) for c in n.bbox.center] if n.bbox else None,
                    "anim_safe": not (
                        n.is_skinned or n.is_bone or n.is_instanced
                        or n.is_xref or n.has_scripted_ctrl
                    ),
                }
                for n in self.nodes if n.category in (Category.GEOMETRY, Category.HELPER)
            ][:200],
            "cameras": [c.name for c in self.cameras],
            "lights": [l.name for l in self.lights] + [s.name for s in self.suns],
            "environment_map": bool(self.environment_map),
            "gamma": self.gamma,
            "warnings": self.warnings,
        }


# -------------------------------------------------------------------------- the brief

@dataclass
class Brief:
    prompt: str = ""
    director_style: Optional[str] = None
    mood: Optional[str] = None
    duration_s: float = 12.0
    aspect: str = "16:9"
    fps: int = 24
    render_backend: RenderBackend = RenderBackend.VRAY
    ref_image_path: Optional[str] = None
    ref_video_url: Optional[str] = None

    def to_prompt_dict(self) -> dict:
        return {
            "prompt": self.prompt,
            "director_style": self.director_style,
            "mood": self.mood,
            "duration_s": self.duration_s,
            "aspect": self.aspect,
            "fps": self.fps,
            "render_backend": self.render_backend.value,
            "has_reference_image": bool(self.ref_image_path),
            "has_reference_video": bool(self.ref_video_url),
        }


# ------------------------------------------------------------------- storyboard (③)

@dataclass
class AssetGap:
    shot_id: str
    kind: str          # "sky" | "foreground" | "prop" | "entourage" | "wipe_element"
    reason: str
    keywords: List[str] = field(default_factory=list)


@dataclass
class StoryboardShot:
    id: str
    beat: str
    intent: str
    camera_move: CameraMove
    subject_node: Optional[str] = None
    framing: str = ""
    mood: str = ""
    duration_s: float = 4.0
    transition_in: str = "cut"


@dataclass
class Storyboard:
    shots: List[StoryboardShot] = field(default_factory=list)
    director_style: str = ""
    grade_mood: str = ""
    aspect: str = "16:9"
    fps: int = 24
    asset_gaps: List[AssetGap] = field(default_factory=list)


# -------------------------------------------------------------- authoring plan (⑤)

@dataclass
class Anchor:
    """Semantic camera placement — resolved to a world transform by the BRIDGE, never by
    the LLM. This is the fix for 'camera in the void': the model plans relative to real
    geometry; ``maxbridge.anchors_resolve`` does the metric math from actual bbox/pivots."""
    relative_to: str                       # a node name from the digest
    standpoint: Standpoint = Standpoint.THREE_QUARTER
    distance_m: float = 3.0                # metres; scaled to scene units at resolve time
    height_m: float = 1.5                  # camera height above subject base
    subject_screen_pos: Vec3 = (0.5, 0.5, 0.0)  # where the subject sits in frame (x,y in 0..1)


@dataclass
class PathSpec:
    kind: str = "static"                   # matches CameraMove values that need a path
    around: Optional[str] = None           # node name to orbit/reveal around
    degrees: float = 0.0                   # orbit/arc sweep
    distance_m: float = 0.0                # dolly/track distance
    control_points: List[Anchor] = field(default_factory=list)  # bezier


@dataclass
class Keyframe:
    t_s: float
    ease: Ease = Ease.IN_OUT
    fov_mm: Optional[float] = None
    # Resolved world state is filled in by the bridge; the LLM never sets these:
    pos: Optional[Vec3] = None
    look_at: Optional[Vec3] = None


@dataclass
class CameraSpec:
    name: str
    klass: str = "VRayPhysicalCamera"
    create: bool = True
    fov_mm: float = 35.0


@dataclass
class PlanShot:
    id: str
    camera: CameraSpec
    anchor: Anchor
    path: PathSpec = field(default_factory=PathSpec)
    keyframes: List[Keyframe] = field(default_factory=list)
    duration_s: float = 4.0


@dataclass
class LightOp:
    op: str                                # "create"
    klass: str                             # "VRaySun" | "VRayLight"
    name: Optional[str] = None
    subtype: Optional[str] = None          # plane|sphere|dome
    time_of_day: Optional[str] = None      # "17:30" -> sun elevation/azimuth
    target_node: Optional[str] = None
    multiplier: Optional[float] = None
    temp_k: Optional[float] = None


@dataclass
class EnvSpec:
    hdri_asset: Optional[str] = None       # e.g. "polyhaven:kloofendal_48d"
    gamma: float = 2.2


@dataclass
class AnimOp:
    op: str                                # "keyframe"
    node: str
    track: str                             # position|rotation|scale
    safe_required: bool = True
    keys: List[dict] = field(default_factory=list)   # [{t_s, value:[...]}]


@dataclass
class RenderShot:
    id: str
    frames: Tuple[int, int]
    output: str


@dataclass
class RenderSpec:
    backend: RenderBackend = RenderBackend.VRAY
    size: Tuple[int, int] = (1920, 1080)
    fps: int = 24
    fmt: str = "exr"
    shots: List[RenderShot] = field(default_factory=list)


@dataclass
class AuthoringPlan:
    shots: List[PlanShot] = field(default_factory=list)
    lights: List[LightOp] = field(default_factory=list)
    environment: EnvSpec = field(default_factory=EnvSpec)
    animation: List[AnimOp] = field(default_factory=list)
    render: RenderSpec = field(default_factory=RenderSpec)
    status: str = "ready"                  # ready | needs_clarification
    assumptions: List[str] = field(default_factory=list)


# ------------------------------------------------------------------ resolved + results

@dataclass
class CameraState:
    """A fully-resolved camera pose (bridge output; critic + apply input)."""
    pos: Vec3
    look_at: Vec3
    fov_mm: float
    up: Vec3 = (0.0, 0.0, 1.0)


@dataclass
class ResolvedShot:
    id: str
    camera_name: str
    states: List[Tuple[float, CameraState]]   # (t_s, state) keyframes


@dataclass
class CriticFinding:
    shot_id: str
    code: str
    severity: Severity
    message: str


@dataclass
class ApplyResult:
    applied: List[str] = field(default_factory=list)
    verified: List[str] = field(default_factory=list)
    unverified: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    manual: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failed and not self.unverified


@dataclass
class ScoreResult:
    shot_id: str
    candidate_index: int
    composition: float           # 0..1 deterministic rule score
    aesthetic: Optional[float] = None    # 0..1 from MUSIQ/NIMA (sidecar), if available
    reference_match: Optional[float] = None  # 0..1 vs reference image, if any

    @property
    def total(self) -> float:
        parts = [self.composition]
        if self.aesthetic is not None:
            parts.append(self.aesthetic)
        if self.reference_match is not None:
            parts.append(self.reference_match)
        return sum(parts) / len(parts)
