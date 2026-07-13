"""Scout capture — place the scout cameras in Max, render thumbnails, populate the visual
digest. pymxs only. This is what makes DIRECT/COMPILE multimodal: the model sees the scene.
"""

from __future__ import annotations

import os
import tempfile

from ..core.models import Digest
from ..core.resolve import meters_to_units
from ..core.scout import scout_poses
from .authoring import _look_at_tm, _set_fov


def _rt():
    import pymxs
    return pymxs.runtime


def _scout_dir() -> str:
    d = os.path.join(tempfile.gettempdir(), "MaxDirector", "scouts")
    os.makedirs(d, exist_ok=True)
    return d


def capture_scouts(digest: Digest, width: int = 512, height: int = 320) -> Digest:
    """Fill ``digest.scouts`` with rendered thumbnails. Temp cameras are created, rendered,
    and deleted so the user's scene is left untouched. Degrades gracefully: a scout whose
    render fails just gets an empty thumb_path (the director drops it from the image set)."""
    rt = _rt()
    if digest.scene_bounds is None:
        return digest
    views = scout_poses(digest.scene_bounds, digest.up_axis, meters_to_units(digest.units))
    out_dir = _scout_dir()
    for sv in views:
        cam = None
        try:
            maker = getattr(rt, "FreeCamera", None) or getattr(rt, "Freecamera", None)
            cam = maker() if maker else rt.VRayPhysicalCamera()
            cam.name = f"__MD_scout_{sv.id}"
            cam.transform = _look_at_tm(rt, sv.pose.pos, sv.pose.look_at, sv.pose.up)
            _set_fov(rt, cam, sv.pose.fov_mm)
            path = os.path.join(out_dir, f"scout_{sv.id}.png")
            img = rt.render(camera=cam, outputwidth=width, outputheight=height,
                            outputFile=path, vfb=False, quiet=True)
            try:
                rt.close(img)
            except Exception:
                pass
            sv.thumb_path = path if os.path.exists(path) else ""
        except Exception:
            sv.thumb_path = ""
        finally:
            if cam is not None:
                try:
                    rt.delete(cam)
                except Exception:
                    pass
    digest.scouts = views
    return digest
