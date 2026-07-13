"""Asset import — bring approved assets into the scene. pymxs (+ requests for download).

Skies (Poly Haven) are fully automatable: download the HDR → set as the V-Ray dome/environment.
Cosmos furniture imports as a VRayProxy from the local package (net-new Cosmos discovery has no
public API — the UI guides that). Bespoke props arrive as a GLB (Higgsfield) and are scaled to
scene units. Nothing here runs without prior user approval (enforced upstream).
"""

from __future__ import annotations

import os
import tempfile
from typing import Optional

from .authoring import set_environment_hdri


def _rt():
    import pymxs
    return pymxs.runtime


def download(url: str, dest_dir: Optional[str] = None) -> Optional[str]:
    """Download a file to disk (approved by the user upstream). Returns local path."""
    import requests
    dest_dir = dest_dir or os.path.join(tempfile.gettempdir(), "MaxDirector", "assets")
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, os.path.basename(url.split("?")[0]) or "asset.bin")
    try:
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(1 << 16):
                    f.write(chunk)
        return path
    except Exception:
        return None


def import_hdri_as_sky(hdr_path: str, gamma: float = 2.2) -> bool:
    return set_environment_hdri(hdr_path, gamma)


def import_vrayproxy(vrmesh_path: str, pos=(0.0, 0.0, 0.0)) -> bool:
    """Load a Cosmos/other .vrmesh as a VRayProxy at ``pos``."""
    rt = _rt()
    try:
        proxy = rt.VRayProxy()
        proxy.filename = vrmesh_path
        proxy.pos = rt.Point3(*[float(x) for x in pos])
        proxy.name = "MD_" + os.path.splitext(os.path.basename(vrmesh_path))[0]
        return True
    except Exception:
        return False


def import_glb(glb_path: str, scale: float = 1.0, pos=(0.0, 0.0, 0.0)) -> bool:
    """Import a Higgsfield-generated GLB and scale to scene units (GLB is metres, Y-up)."""
    rt = _rt()
    try:
        before = set(rt.getHandleByAnim(o) for o in rt.objects)
        rt.importFile(glb_path, rt.Name("noPrompt"), using=rt.Name("glTFImporter"))
        for o in rt.objects:
            if rt.getHandleByAnim(o) not in before:
                o.scale = rt.Point3(scale, scale, scale)
                o.pos = rt.Point3(*[float(x) for x in pos])
                o.name = "MD_" + str(o.name)
        return True
    except Exception:
        return False
