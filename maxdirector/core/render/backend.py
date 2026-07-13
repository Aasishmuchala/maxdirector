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
    """One job per shot, each rendered over its own LOCAL range [0 .. duration*fps-1].

    Each shot has its own camera and its own output file, and ``apply_camera_states`` keys
    every camera on a LOCAL timeline (t_s*fps, starting at 0). So jobs MUST use local ranges
    too — a global back-to-back cursor would render shots 2..N over frames where their camera
    has no keys, freezing every shot after the first. (Fix from the review.)"""
    rs: RenderSpec = plan.render
    w, h = rs.size
    explicit = {s.id: s for s in rs.shots}
    jobs: List[RenderJob] = []
    for shot in plan.shots:
        count = max(1, round(shot.duration_s * rs.fps))
        out = (explicit[shot.id].output if shot.id in explicit and explicit[shot.id].output
               else f"{out_dir}/{shot.id}.####.{rs.fmt}")
        jobs.append(RenderJob(shot_id=shot.id, camera_name=shot.camera.name,
                              frame_start=0, frame_end=count - 1,
                              width=w, height=h, fmt=rs.fmt, output=out))
    return jobs
