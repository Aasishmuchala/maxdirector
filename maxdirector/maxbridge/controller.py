"""Controller — the in-Max orchestrator the UI drives. Ties pure core to the bridge.

Runs the pipeline: UNDERSTAND → DIRECT → RESOLVE GAPS → COMPILE → GROUND+CRITIC(+best-of-N)
→ APPLY → RENDER. Holds the config/key and an optional CV-sidecar client. Long network work
is meant to be called from a worker thread by the UI (see ui/dock.py) so Max never freezes;
this class stays synchronous and pure-ish at its edges.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from ..core import director
from ..core.assets import detect_gaps, search_hdris
from ..core.critic import critique_shot, has_blockers
from ..core.cv_client import CVClient
from ..core.models import (
    ApplyResult,
    AssetGap,
    AuthoringPlan,
    Brief,
    CriticFinding,
    Digest,
    ResolvedShot,
    Storyboard,
)
from ..core.render.backend import plan_jobs
from ..core.resolve import resolve_plan
from . import config as _config


class Controller:
    def __init__(self, cfg: Optional[_config.Config] = None):
        self.cfg = cfg or _config.load()
        self.cv: Optional[CVClient] = None
        if self.cfg.use_cv_sidecar:
            self.cv = CVClient(self.cfg.sidecar_url)

    # ① UNDERSTAND  (+ capture scout thumbnails so DIRECT/COMPILE can SEE the scene)
    def understand(self, with_scouts: bool = True) -> Digest:
        from .digest import collect_digest
        digest = collect_digest()
        if with_scouts:
            try:
                from .scout import capture_scouts
                digest = capture_scouts(digest)
            except Exception as e:  # scouts are an enhancement; never block the pipeline
                digest.warnings.append(f"scout capture skipped: {e}")
        return digest

    # ③ DIRECT
    def direct(self, digest: Digest, brief: Brief) -> Tuple[Optional[Storyboard], List[str]]:
        sb, notes, _ = director.direct(self.cfg.api_key, digest, brief, model=self.cfg.model)
        return sb, notes

    # ④ RESOLVE GAPS (detect + research; download is a separate, approved step)
    def resolve_gaps(self, storyboard: Storyboard, digest: Digest) -> List[dict]:
        out = []
        for gap in detect_gaps(storyboard, digest):
            candidates = []
            if gap.kind == "sky":
                try:
                    candidates = search_hdris(gap.keywords or ["sky"])
                except Exception:
                    candidates = []
            out.append({"gap": gap, "candidates": candidates})
        return out

    # ⑤ COMPILE + ⑤·5 GROUND + CRITIC
    def compile_and_check(
        self, digest: Digest, storyboard: Storyboard, opted_in_nodes: Optional[set] = None
    ) -> Tuple[Optional[AuthoringPlan], List[ResolvedShot], List[CriticFinding], List[str]]:
        plan, errors, _ = director.compile_plan(
            self.cfg.api_key, digest, storyboard, model=self.cfg.model, opted_in_nodes=opted_in_nodes
        )
        if plan is None:
            return None, [], [], errors
        resolved = resolve_plan(plan, digest)
        findings: List[CriticFinding] = []
        by_id = {s.id: s for s in plan.shots}
        for rs in resolved:
            subj = by_id[rs.id].anchor.relative_to if rs.id in by_id else None
            subj_node = digest.node_by_name(subj) if subj else None
            center = subj_node.bbox.center if (subj_node and subj_node.bbox) else None
            findings += critique_shot(rs, digest, subject_center=center)
        return plan, resolved, findings, errors

    def blocked(self, findings: List[CriticFinding]) -> bool:
        return has_blockers(findings)

    # ⑥ preview (playblast + optional best-of-N via sidecar)
    def preview(self, resolved: List[ResolvedShot]) -> dict:
        from .framing import capture
        from .authoring import create_camera, apply_camera_states
        shots = {}
        for rs in resolved:
            cam, ok = create_camera(rs.camera_name + "_preview", rs.states[0][1].fov_mm if rs.states else 35.0)
            if ok:
                apply_camera_states(cam, rs.states, 24)
                shots[rs.id] = capture(cam, tag=rs.id)
        return shots

    # ⑥ APPLY
    def apply(self, resolved: List[ResolvedShot], plan: AuthoringPlan, digest: Digest) -> ApplyResult:
        from .authoring import apply_plan
        return apply_plan(resolved, plan, digest)

    # ⑥ RENDER
    def render(self, plan: AuthoringPlan, on_progress: Optional[Callable[[str, str], None]] = None) -> dict:
        jobs = plan_jobs(plan)
        if plan.render.backend.value == "vantage":
            from .vantage import run_batch
            return run_batch(jobs, self.cfg.vantage_console, on_progress=on_progress)
        from .vray_render import render_sequence
        return render_sequence(jobs, on_progress=on_progress)
