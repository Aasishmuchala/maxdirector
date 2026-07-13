from maxdirector.core.guards import check_anim, is_anim_safe
from maxdirector.core.models import NodeInfo, ScoreResult
from maxdirector.core.scoring import composition_score, pick_best, score_candidate


def test_thirds_beats_centre():
    on_third = composition_score((1 / 3, 1 / 3, 0.0))
    centre = composition_score((0.5, 0.5, 0.0))
    assert on_third > centre


def test_pick_best_prefers_higher_total():
    a = ScoreResult("s1", 0, composition=0.4)
    b = ScoreResult("s1", 1, composition=0.9)
    assert pick_best([a, b]).candidate_index == 1


def test_pick_best_uses_aesthetic_when_present():
    a = ScoreResult("s1", 0, composition=0.9, aesthetic=0.1)
    b = ScoreResult("s1", 1, composition=0.5, aesthetic=0.9)
    # totals: a=(0.9+0.1)/2=0.5, b=(0.5+0.9)/2=0.7 -> b wins
    assert pick_best([a, b]).candidate_index == 1


def test_score_candidate_without_sidecar_is_composition_only():
    r = score_candidate("s1", 0, subject_screen_pos=(1 / 3, 1 / 3, 0.0))
    assert r.aesthetic is None and r.reference_match is None
    assert r.total == r.composition


def test_guard_refuses_skinned():
    n = NodeInfo(handle=1, name="char", klass="Poly", is_skinned=True)
    assert not is_anim_safe(n)
    allowed, msg = check_anim(n)
    assert not allowed and "skinned" in msg


def test_guard_allows_plain_mesh():
    n = NodeInfo(handle=1, name="door", klass="Poly")
    allowed, msg = check_anim(n)
    assert allowed
