"""Verified technical vocabulary — the legal V-Ray-7 classes/props the validator enforces.

Kept separate from the *creative* knowledge pack (``core.cinematic``). This is the "never
emit a param the host can't take" guard: the LLM's plan is checked against these sets before
anything touches the scene. Defaults are the V-Ray-7 baseline; ``load_pack`` can override
from ``data/packs/*.json`` (generated from a single source of truth, LightMatch-style, so
the prompt vocab and the validator can never drift).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Set, Tuple


@dataclass
class VerifiedPack:
    camera_classes: Set[str] = field(default_factory=lambda: {"VRayPhysicalCamera", "Physical"})
    light_classes: Set[str] = field(default_factory=lambda: {"VRayLight"})
    sun_classes: Set[str] = field(default_factory=lambda: {"VRaySun"})
    light_subtypes: Set[str] = field(default_factory=lambda: {"plane", "sphere", "dome", "disc", "mesh"})
    tracks: Set[str] = field(default_factory=lambda: {"position", "rotation", "scale"})
    render_formats: Set[str] = field(default_factory=lambda: {"exr", "png", "jpg", "tif"})
    fov_mm_range: Tuple[float, float] = (8.0, 300.0)
    distance_m_range: Tuple[float, float] = (0.2, 200.0)
    intensity_range: Tuple[float, float] = (0.0, 1000.0)
    temp_k_range: Tuple[float, float] = (1000.0, 20000.0)

    def clamp_fov(self, mm: float) -> float:
        lo, hi = self.fov_mm_range
        return max(lo, min(hi, mm))

    def clamp_distance(self, m: float) -> float:
        lo, hi = self.distance_m_range
        return max(lo, min(hi, m))


def default_vray_pack() -> VerifiedPack:
    return VerifiedPack()


def load_pack(path: str) -> VerifiedPack:
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    base = VerifiedPack()
    for k, v in d.items():
        if hasattr(base, k):
            setattr(base, k, set(v) if isinstance(getattr(base, k), set) else tuple(v) if isinstance(getattr(base, k), tuple) else v)
    return base
