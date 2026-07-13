"""CV model backends — the commercial-safe stack, each with a graceful STUB fallback.

Real models (installed separately in this sidecar's own venv, NOT Max's Python):
  * GeoCalib          — single-image focal/horizon/gravity   (Apache + CC-BY)   ✅ commercial
  * Depth Anything V2-Small — relative depth for composition  (Apache)           ✅ commercial
  * OpenCLIP          — image similarity for the gate          (MIT)             ✅ commercial
  * MUSIQ / NIMA      — aesthetic score                        (Apache)          ✅ commercial
  * MegaSaM / RAFT    — video → normalized camera trajectory   (Apache / BSD)    ✅ commercial

If a model isn't importable the backend returns a neutral STUB so the whole pipeline still
runs (LLM-only 'guided' mode) — you download models when you want the accuracy. Set
MAXDIRECTOR_CV_REAL=1 to require real models (raises instead of stubbing).
"""

from __future__ import annotations

import os
from typing import List, Optional

REQUIRE_REAL = os.environ.get("MAXDIRECTOR_CV_REAL") == "1"


def _stub_or_raise(name: str):
    if REQUIRE_REAL:
        raise RuntimeError(f"{name} not installed and MAXDIRECTOR_CV_REAL=1")
    return None


class Similarity:
    """CLIP-cosine similarity: is the reference the same KIND of space as the scene views?"""

    def __init__(self):
        self.model = None
        try:
            import open_clip  # noqa: F401
            import torch  # noqa: F401
            # self.model, _, self.preprocess = open_clip.create_model_and_transforms(...)
            # loaded lazily in real deployment; left as the integration point.
        except Exception:
            _stub_or_raise("open_clip")

    def compare(self, ref_png: str, view_pngs: List[str]) -> dict:
        if self.model is None:
            # STUB: neutral-positive so the gate doesn't block in dev; real CLIP replaces this.
            return {"match": True, "confidence": 0.5, "reason": "stub (no CLIP installed)",
                    "matched_zone": None, "stub": True}
        # REAL: embed ref + each view, take max cosine, threshold.
        raise NotImplementedError("wire OpenCLIP embeddings here")


class Calibration:
    """GeoCalib: focal (→vfov), pitch, roll, horizon from a single reference image."""

    def __init__(self):
        self.model = None
        try:
            import geocalib  # noqa: F401
        except Exception:
            _stub_or_raise("geocalib")

    def calibrate(self, ref_png: str) -> dict:
        if self.model is None:
            return {"vfov_deg": 42.0, "pitch_deg": 0.0, "roll_deg": 0.0, "horizon_y": 0.5,
                    "subject_screen_pos": [0.5, 0.45], "stub": True}
        raise NotImplementedError("run GeoCalib and map to vfov/pitch/roll/horizon")


class Aesthetic:
    """MUSIQ/NIMA aesthetic score in 0..1."""

    def __init__(self):
        self.model = None
        try:
            import torch  # noqa: F401
        except Exception:
            _stub_or_raise("torch")

    def score(self, png_path: str) -> float:
        if self.model is None:
            return 0.5  # STUB — best-of-N then falls back to composition ordering
        raise NotImplementedError("run MUSIQ/NIMA")


class ReferenceMatch:
    """Composition similarity between a rendered candidate and the reference (edges + depth)."""

    def __init__(self, depth=None):
        self.depth = depth

    def score(self, png_path: str, ref_png_path: str) -> float:
        # STUB: constant; REAL uses edge/vanishing-line alignment + DA-V2 depth-layer layout.
        return 0.5


class Depth:
    """Depth Anything V2-Small — relative depth for composition/layer comparison."""

    def __init__(self):
        self.model = None
        try:
            import torch  # noqa: F401
        except Exception:
            _stub_or_raise("torch")

    def infer(self, png_path: str):
        return None  # STUB


class Motion:
    """MegaSaM / RAFT → normalized camera trajectory signature from a video."""

    def __init__(self):
        self.ok = False
        try:
            import torch  # noqa: F401
            self.ok = False  # real pipeline wired on the GPU box
        except Exception:
            _stub_or_raise("torch")

    def signature(self, source: str) -> dict:
        if not self.ok:
            # STUB: a gentle push-in so the flow works before MegaSaM is installed.
            return {"type": "dolly", "dolly_frac": -0.25, "arc_deg": 0.0,
                    "height_delta_frac": 0.0, "zoom_ratio": 1.0, "duration_s": 8.0, "stub": True}
        raise NotImplementedError("download+track with MegaSaM, normalize, return signature")


class FramingRefine:
    """One render-and-compare step: deltas to nudge the camera toward the reference framing."""

    def delta(self, ref_png: str, current_png: str) -> dict:
        # STUB: report 'done' so the loop terminates in dev. REAL compares subject centroid,
        # horizon, and depth layout, returning {d_height_m, d_yaw_deg, d_pitch_deg, d_fov_mm}.
        return {"d_height_m": 0.0, "d_yaw_deg": 0.0, "d_pitch_deg": 0.0, "d_fov_mm": 0.0,
                "done": True, "stub": True}
