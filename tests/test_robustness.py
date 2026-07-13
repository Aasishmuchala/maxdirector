"""Defensive-parsing tests — the LLM (schema-in-prompt, no tools) can hand back malformed
values. Parsing must degrade gracefully (record an error, keep the good shots), never crash."""

from maxdirector.core.plan_schema import parse_plan


def test_malformed_fov_does_not_crash(living_room):
    plan, errors = parse_plan({"shots": [
        {"id": "bad", "camera": {"fov_mm": "wide-ish"}, "anchor": {"relative_to": "sofa_grp"}},
        {"id": "good", "camera": {"fov_mm": 24}, "anchor": {"relative_to": "sofa_grp"}},
    ]}, living_room)
    ids = [s.id for s in plan.shots]
    assert "good" in ids                 # the good shot survived
    # the bad one either parsed with a default fov or was recorded as an error — never a crash
    assert "bad" in ids or any("bad" in e for e in errors)


def test_malformed_size_defaults(living_room):
    plan, _ = parse_plan({"shots": [], "render": {"size": "huge"}}, living_room)
    assert plan.render.size == (1920, 1080)


def test_garbage_shot_entries_skipped(living_room):
    plan, _ = parse_plan({"shots": ["nonsense", 42, None,
                                    {"id": "ok", "anchor": {"relative_to": "sofa_grp"}}]}, living_room)
    assert [s.id for s in plan.shots] == ["ok"]


def test_completely_empty_object(living_room):
    plan, errors = parse_plan({}, living_room)
    assert plan.shots == [] and plan.render.backend.value == "vray"
