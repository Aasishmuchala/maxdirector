"""Reference-driven direction — the PURE decision + mapping logic.

The heavy CV runs in the sidecar (GeoCalib calibration, depth, render-and-compare). This
module holds the parts that must be deterministic and tested:
  * the HARD similarity gate (reject a reference that isn't the same kind of space);
  * mapping a GeoCalib calibration into an anchor SEED (focal→FOV, pitch→standpoint/height);
  * turning a normalized video-motion signature into a camera-moves selection.
"""

from __future__ import annotations

import math
from typing import Optional, Tuple

from .models import Anchor, CameraMove, Standpoint

SIMILARITY_THRESHOLD = 0.6


def decide_similarity(verdict: dict, threshold: float = SIMILARITY_THRESHOLD) -> Tuple[bool, str]:
    """verdict = {match: bool, confidence: 0..1, reason: str} from the multimodal pass.
    Reject (don't proceed) unless it's clearly the same kind of space."""
    match = bool(verdict.get("match"))
    conf = float(verdict.get("confidence", 0.0) or 0.0)
    reason = str(verdict.get("reason", ""))
    if match and conf >= threshold:
        return True, f"accepted ({conf:.0%}): {reason}"
    return False, f"rejected — reference isn't similar enough to the scene ({conf:.0%}): {reason}"


def fov_mm_from_vfov(vfov_deg: float, sensor_h_mm: float = 24.0) -> float:
    """GeoCalib gives a vertical field of view; convert to a full-frame-equivalent focal mm."""
    vfov = math.radians(max(1.0, min(179.0, vfov_deg)))
    return sensor_h_mm / (2.0 * math.tan(vfov / 2.0))


def anchor_seed_from_calibration(
    calib: dict, subject_node: str, distance_m: float = 3.0
) -> Tuple[Anchor, float]:
    """Map a reference calibration to an anchor SEED + a lens (fov_mm). The render-and-compare
    loop refines from here. calib = {vfov_deg, pitch_deg, roll_deg, horizon_y (0..1)}."""
    vfov = float(calib.get("vfov_deg", 40.0) or 40.0)
    pitch = float(calib.get("pitch_deg", 0.0) or 0.0)   # + = looking up, - = looking down
    fov_mm = fov_mm_from_vfov(vfov)

    if pitch > 12:
        standpoint = Standpoint.FRONT_LOW      # camera low, looking up
        height = 0.6
    elif pitch < -12:
        standpoint = Standpoint.FRONT_HIGH     # camera high, looking down
        height = 2.4
    else:
        standpoint = Standpoint.EYE
        height = 1.5

    screen = calib.get("subject_screen_pos") or [0.5, 0.45]
    anchor = Anchor(relative_to=subject_node, standpoint=standpoint, distance_m=distance_m,
                    height_m=height, subject_screen_pos=(float(screen[0]), float(screen[1]), 0.0))
    return anchor, round(fov_mm, 2)


def move_from_motion(signature: dict) -> Tuple[CameraMove, dict]:
    """Map a normalized video-motion signature to a moves-pack selection + params.
    signature = {type, dolly_frac, arc_deg, height_delta_frac, zoom_ratio, duration_s}."""
    t = str(signature.get("type", "")).lower()
    params: dict = {}
    if "orbit" in t or signature.get("arc_deg"):
        params["degrees"] = float(signature.get("arc_deg", 45.0))
        return CameraMove.ORBIT, params
    if "zoom" in t and signature.get("dolly_frac"):
        return CameraMove.DOLLY_ZOOM, {"distance_m": abs(float(signature.get("dolly_frac", 0.3))) * 4}
    dz = float(signature.get("dolly_frac", 0.0) or 0.0)
    if dz < -0.05:
        return CameraMove.PUSH_IN, {"distance_m": abs(dz) * 4}
    if dz > 0.05:
        return CameraMove.PULL_OUT, {"distance_m": dz * 4}
    if abs(float(signature.get("height_delta_frac", 0.0) or 0.0)) > 0.05:
        hd = float(signature["height_delta_frac"])
        return (CameraMove.CRANE_UP if hd > 0 else CameraMove.CRANE_DOWN), {"distance_m": abs(hd) * 4}
    return CameraMove.TRACK, {"distance_m": 1.5}
