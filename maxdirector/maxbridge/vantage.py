"""Chaos Vantage backend — export one scene per shot, then run vantage_console SEQUENTIALLY
("finish all sequences one by one"). pymxs (export) + subprocess (batch).

Workflow (verified against Chaos docs):
  1. per shot, set that shot's camera active and export the animation-range .vrscene via the
     V-Ray→Vantage exporter (env/HDRI must be set in Max — Vantage live-link resets to Max's);
  2. build the CLI commands with ``core.render.vantage_commands``;
  3. run them one at a time; a shot failure halts the queue with a clear report (earlier
     outputs on disk are untouched).
Robust per-camera handling: one scene file per shot with that camera active — no CLI camera
flag needed.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from typing import Callable, Dict, List, Optional

from ..core.render.backend import RenderJob
from ..core.render.vantage import vantage_commands


def _rt():
    import pymxs
    return pymxs.runtime


def export_shot_scene(camera_name: str, frame_start: int, frame_end: int, out_dir: str) -> Optional[str]:
    """Export the animation range as a .vrscene with ``camera_name`` active. Returns path.

    Uses the V-Ray for 3ds Max Vantage exporter macro. If the exact macro name differs on
    your build, adjust here — the CLI batch downstream is unchanged.
    """
    rt = _rt()
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{camera_name}.vrscene")
    cam = rt.getNodeByName(camera_name, exact=True)
    try:
        if cam is not None:
            rt.viewport.setCamera(cam)
        rt.rendStart = frame_start
        rt.rendEnd = frame_end
        # startFrame/endFrame are MANDATORY — without them vrayExportVRScene writes NO
        # animation (Chaos docs). That omission would have exported frozen single-frame scenes.
        if hasattr(rt, "vrayExportVRScene"):
            rt.vrayExportVRScene(path, startFrame=frame_start, endFrame=frame_end)
        else:
            return None   # no exporter available on this build — caller halts the queue
        return path if os.path.exists(path) else None
    except Exception:
        return None


def run_batch(
    jobs: List[RenderJob],
    console_exe: str,
    export_dir: Optional[str] = None,
    on_progress: Optional[Callable[[str, str], None]] = None,
) -> Dict[str, str]:
    """Export each shot then render it via vantage_console, SEQUENTIALLY. Returns
    {shot_id: status}. Halts the queue on the first hard failure."""
    export_dir = export_dir or os.path.join(tempfile.gettempdir(), "MaxDirector", "vantage")
    scene_files: Dict[str, str] = {}
    for job in jobs:
        if on_progress:
            on_progress(job.shot_id, "exporting")
        scene = export_shot_scene(job.camera_name, job.frame_start, job.frame_end, export_dir)
        if not scene:
            if on_progress:
                on_progress(job.shot_id, "export failed")
            return {job.shot_id: "export failed"}
        scene_files[job.shot_id] = scene

    cmds = vantage_commands(jobs, scene_files, console_exe=console_exe)
    results: Dict[str, str] = {}
    for job, cmd in zip(jobs, cmds):
        if on_progress:
            on_progress(job.shot_id, "rendering (vantage)")
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60 * 60)
            if proc.returncode == 0:
                results[job.shot_id] = "ok"
                if on_progress:
                    on_progress(job.shot_id, "done")
            else:
                results[job.shot_id] = f"vantage exit {proc.returncode}"
                if on_progress:
                    on_progress(job.shot_id, results[job.shot_id])
                break  # halt the queue; earlier outputs are intact
        except Exception as e:  # noqa: BLE001
            results[job.shot_id] = f"error: {e}"
            break
    return results
