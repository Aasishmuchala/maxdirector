"""V-Ray render backend — execute a sequence render per shot, in order. pymxs only.

The pure ``core.render.plan_jobs`` produced the RenderJobs; this runs them: set the active
camera + output + range, then ``render()`` the range. Sequential, with a progress callback.
"""

from __future__ import annotations

import os
from typing import Callable, List, Optional

from ..core.render.backend import RenderJob


def _rt():
    import pymxs
    return pymxs.runtime


def render_sequence(jobs: List[RenderJob], on_progress: Optional[Callable[[str, str], None]] = None) -> dict:
    """Render each shot's frame range to its output path, one after another. Returns a
    {shot_id: status} map. Never raises for a single shot failure — records and continues."""
    rt = _rt()
    results: dict = {}
    for job in jobs:
        if on_progress:
            on_progress(job.shot_id, "rendering")
        cam = rt.getNodeByName(job.camera_name, exact=True)
        try:
            os.makedirs(os.path.dirname(job.output) or ".", exist_ok=True)
            rt.rendTimeType = 3
            rt.rendStart = job.frame_start
            rt.rendEnd = job.frame_end
            rt.render(camera=cam, outputwidth=job.width, outputheight=job.height,
                      outputFile=job.output, fromFrame=job.frame_start, toFrame=job.frame_end,
                      vfb=False, quiet=True)
            results[job.shot_id] = "ok"
            if on_progress:
                on_progress(job.shot_id, "done")
        except Exception as e:  # noqa: BLE001
            results[job.shot_id] = f"error: {e}"
            if on_progress:
                on_progress(job.shot_id, f"error: {e}")
    return results
