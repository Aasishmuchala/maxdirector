"""Best-of-N scoring — PURE selection logic + a deterministic composition score.

Quality that schema-validation and the critic can't give: of N candidate framings for a
shot, which looks best? We score each candidate on three axes and pick the max:

  * composition  — deterministic rules (rule-of-thirds, headroom, horizon) computed here;
  * aesthetic    — MUSIQ/NIMA on the rendered playblast, supplied by the CV sidecar;
  * reference    — similarity to a reference image, supplied by the CV sidecar.

The ML axes are OPTIONAL: without a sidecar (no GPU), selection falls back to composition
alone — still better than first-guess. The sidecar implements the ``Scorer`` protocol; this
module never imports torch.
"""

from __future__ import annotations

from typing import List, Optional, Protocol, Sequence

from .models import ScoreResult, Vec3


class Scorer(Protocol):
    """Implemented by the CV sidecar client. Given a rendered playblast (PNG path) returns
    0..1 scores. Pure code depends only on this protocol, never on torch."""

    def aesthetic(self, png_path: str) -> Optional[float]: ...
    def reference_match(self, png_path: str, ref_png_path: str) -> Optional[float]: ...


# ------------------------------------------------------------ deterministic composition

def _thirds_score(pos_xy: Sequence[float]) -> float:
    """1.0 when the subject sits on a rule-of-thirds line/intersection, decaying to ~0 at
    dead-centre or the edges. pos_xy are 0..1 screen coords."""
    thirds = (1.0 / 3.0, 2.0 / 3.0)
    dx = min(abs(pos_xy[0] - t) for t in thirds)
    dy = min(abs(pos_xy[1] - t) for t in thirds)
    # closeness to the nearest third on each axis (max distance to a third is ~1/3)
    sx = max(0.0, 1.0 - dx / (1.0 / 3.0))
    sy = max(0.0, 1.0 - dy / (1.0 / 3.0))
    return 0.5 * sx + 0.5 * sy


def _headroom_score(subject_top_y: float) -> float:
    """Penalise a subject whose head is jammed at the very top or floating too low.
    subject_top_y is the 0..1 screen y of the subject's top (0 = top of frame)."""
    # ideal top margin ~0.08..0.18
    if subject_top_y < 0.03:
        return 0.2
    if subject_top_y > 0.4:
        return 0.5
    return 1.0


def composition_score(subject_screen_pos: Vec3, subject_top_y: Optional[float] = None) -> float:
    s = _thirds_score(subject_screen_pos)
    if subject_top_y is not None:
        s = 0.7 * s + 0.3 * _headroom_score(subject_top_y)
    return round(s, 4)


# ------------------------------------------------------------ best-of-N selection

def score_candidate(
    shot_id: str,
    index: int,
    subject_screen_pos: Vec3,
    playblast_png: Optional[str] = None,
    scorer: Optional[Scorer] = None,
    ref_png: Optional[str] = None,
    subject_top_y: Optional[float] = None,
) -> ScoreResult:
    comp = composition_score(subject_screen_pos, subject_top_y)
    aesth = None
    refm = None
    if scorer is not None and playblast_png is not None:
        aesth = scorer.aesthetic(playblast_png)
        if ref_png is not None:
            refm = scorer.reference_match(playblast_png, ref_png)
    return ScoreResult(shot_id=shot_id, candidate_index=index, composition=comp,
                       aesthetic=aesth, reference_match=refm)


def pick_best(results: List[ScoreResult]) -> Optional[ScoreResult]:
    """Highest total; ties broken by composition then lowest index (stable)."""
    if not results:
        return None
    return max(results, key=lambda r: (r.total, r.composition, -r.candidate_index))
