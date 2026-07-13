"""Chaos Vantage batch — PURE command building. The headline "finish all sequences one by
one": one ``vantage_console.exe`` invocation per shot, run SEQUENTIALLY by the bridge.

Verified CLI shape (Chaos "Command Line Options"): ``-scenefile -outputFile -outputWidth
-outputHeight -frames``. Per-shot camera selection is handled by exporting one ``.vantage``
(or ``.vrscene``) per shot with that shot's camera active — so no per-camera flag is needed,
the robust fallback documented in the plan.
"""

from __future__ import annotations

from typing import Dict, List

from .backend import RenderJob


def vantage_commands(
    jobs: List[RenderJob],
    scene_files: Dict[str, str],
    console_exe: str = r"C:\Program Files\Chaos\Vantage\vantage_console.exe",
) -> List[List[str]]:
    """One argv per shot, in order. ``scene_files`` maps shot_id -> that shot's exported
    .vantage/.vrscene path (each already has its camera active)."""
    cmds: List[List[str]] = []
    for job in jobs:
        scene = scene_files.get(job.shot_id)
        if not scene:
            continue
        cmds.append([
            console_exe,
            f"-scenefile={scene}",
            f"-outputFile={job.output}",
            f"-outputWidth={job.width}",
            f"-outputHeight={job.height}",
            f"-frames={job.frame_start}-{job.frame_end}",
        ])
    return cmds
