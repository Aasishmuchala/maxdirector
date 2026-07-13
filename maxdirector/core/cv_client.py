"""CV sidecar client — talks to the local torch+CUDA service over localhost. PURE (requests
only; no torch here). Implements the ``scoring.Scorer`` protocol and the reference/motion
calls. Every method degrades to None on any error, so a missing/broken sidecar simply drops
the plugin to the LLM-only 'guided' mode instead of crashing.
"""

from __future__ import annotations

from typing import Callable, List, Optional

DEFAULT_URL = "http://127.0.0.1:8765"


def _default_post(url: str, payload: dict, timeout: int = 60) -> dict:
    import requests
    return requests.post(url, json=payload, timeout=timeout).json()


class CVClient:
    """Client for the commercial-safe CV stack (GeoCalib, Depth Anything V2-Small, MegaSaM,
    MUSIQ/NIMA) running in ``cv_sidecar``. ``available`` is False when the service is down."""

    def __init__(self, base_url: str = DEFAULT_URL, post: Callable[..., dict] = _default_post):
        self._base = base_url.rstrip("/")
        self._post = post

    def _call(self, route: str, payload: dict, timeout: int = 60) -> Optional[dict]:
        try:
            return self._post(f"{self._base}{route}", payload, timeout)
        except Exception:
            return None

    @property
    def available(self) -> bool:
        r = self._call("/health", {}, timeout=3)
        return bool(r and r.get("ok"))

    # -- similarity gate + calibration (reference IMAGE) --

    def similarity(self, ref_png: str, view_pngs: List[str]) -> Optional[dict]:
        """{match, confidence, reason, matched_zone} — is the reference the same kind of space?"""
        return self._call("/similarity", {"ref": ref_png, "views": view_pngs})

    def calibrate(self, ref_png: str) -> Optional[dict]:
        """GeoCalib on the reference: {vfov_deg, pitch_deg, roll_deg, horizon_y, subject_screen_pos}."""
        return self._call("/calibrate", {"ref": ref_png})

    # -- best-of-N scoring (scoring.Scorer protocol) --

    def aesthetic(self, png_path: str) -> Optional[float]:
        r = self._call("/aesthetic", {"png": png_path})
        return None if r is None else float(r.get("score", 0.0))

    def reference_match(self, png_path: str, ref_png_path: str) -> Optional[float]:
        r = self._call("/reference_match", {"png": png_path, "ref": ref_png_path})
        return None if r is None else float(r.get("score", 0.0))

    # -- render-and-compare framing refine --

    def framing_delta(self, ref_png: str, current_png: str) -> Optional[dict]:
        """{d_height_m, d_yaw_deg, d_pitch_deg, d_fov_mm, done} — CMA-ES/analysis step."""
        return self._call("/framing_delta", {"ref": ref_png, "current": current_png})

    # -- video → normalized motion signature --

    def video_motion(self, video_path_or_url: str) -> Optional[dict]:
        """{type, dolly_frac, arc_deg, height_delta_frac, zoom_ratio, duration_s} via MegaSaM/RAFT."""
        return self._call("/video_motion", {"source": video_path_or_url}, timeout=600)
