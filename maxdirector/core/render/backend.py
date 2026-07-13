"""Per-shot render jobs — PURE. Derives frame ranges from shot durations x fps when the
plan didn't specify them, and normalises output paths. Both V-Ray and Vantage consume these.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from ..models import AuthoringPlan, RenderSpec


@dataclass
class RenderJob:
    shot_id: str
    camera_name: str
    frame_start: int
    frame_end: int
    width: int
    height: int
    fmt: str
    output: str

    @property
    def frame_count(self) -> int:
        return self.frame_end - self.frame_start + 1


def plan_jobs(plan: AuthoringPlan, out_dir: str = "renders") -> List[RenderJob]:
    """One job per shot. If the render spec listed explicit frame ranges, use them; else
    derive from each shot's duration x fps, laid out back-to-back on a single timeline."""
    rs: RenderSpec = plan.render
    w, h = rs.size
    explicit = {s.id: s for s in rs.shots}
    jobs: List[RenderJob] = []
    cursor = 0
    for shot in plan.shots:
        cam = shot.camera.name
        if shot.id in explicit and explicit[shot.id].frames:
            a, b = explicit[shot.id].frames
            out = explicit[shot.id].output or f"{out_dir}/{shot.id}.####.{rs.fmt}"
        else:
            a = cursor
            b = cursor + max(1, round(shot.duration_s * rs.fps)) - 1
            out = f"{out_dir}/{shot.id}.####.{rs.fmt}"
        cursor = b + 1
        jobs.append(RenderJob(shot_id=shot.id, camera_name=cam, frame_start=a, frame_end=b,
                              width=w, height=h, fmt=rs.fmt, output=out))
    return jobs
