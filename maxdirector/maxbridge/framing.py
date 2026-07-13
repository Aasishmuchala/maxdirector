"""Viewport playblast / capture for the CV compare + best-of-N loops. pymxs only.

Fast, low-res frames (not full renders) so the framing-convergence loop and the best-of-N
scorer can run in seconds. The captured PNG path is handed to the CV sidecar.
"""

from __future__ import annotations

import os
import tempfile


def _rt():
    import pymxs
    return pymxs.runtime


def _out_dir() -> str:
    d = os.path.join(tempfile.gettempdir(), "MaxDirector", "playblasts")
    os.makedirs(d, exist_ok=True)
    return d


def capture(cam, width: int = 640, height: int = 360, frame: float = 0.0, tag: str = "pb") -> str:
    """Render a small preview from ``cam`` at ``frame`` to a PNG; return its path.

    Uses ``render()`` at low res so it works headless; swap for a Nitrous viewport grab if a
    live editor session wants it faster. Never touches the scene's real render output path.
    """
    rt = _rt()
    path = os.path.join(_out_dir(), f"{tag}.png")
    try:
        prev = rt.sliderTime
        rt.sliderTime = frame
        # render straight to file (outputFile writes it; no bitmap save() dance needed)
        img = rt.render(camera=cam, outputwidth=width, outputheight=height,
                        outputFile=path, vfb=False, quiet=True)
        try:
            rt.close(img)
        except Exception:
            pass
        rt.sliderTime = prev
        return path if os.path.exists(path) else ""
    except Exception:
        return ""
