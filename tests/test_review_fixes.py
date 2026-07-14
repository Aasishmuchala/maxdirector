"""Regression tests for the fixes from the 3-reviewer workflow. Each locks in a real bug."""

import sys
import types
from dataclasses import replace
from unittest.mock import MagicMock

import pytest

from maxdirector.core.anchors import reaim
from maxdirector.core.director import _media_type, _scout_legend
from maxdirector.core.omega import OmegaError
from maxdirector.core.plan_schema import parse_plan
from maxdirector.core.provider import complete
from maxdirector.core.resolve import resolve_plan
from maxdirector.core.scout import scout_poses


# --- #2 look_shift / subject_screen_pos actually re-aim the camera ---

def test_reaim_centered_is_noop():
    assert reaim((0, -3, 1.5), (0, 0, 1.5), (0, 0, 1), 35.0, (0.5, 0.5, 0.0)) == (0, 0, 1.5)


def test_reaim_subject_right_aims_left_of_subject():
    look = (0.0, 0.0, 1.5)
    l = reaim((0.0, -3.0, 1.5), look, (0, 0, 1), 35.0, (0.8, 0.5, 0.0))
    assert l[0] < look[0]          # aim moved left so the subject falls on the right


def test_reaim_flows_through_resolve(living_room):
    d = replace(living_room, scouts=scout_poses(living_room.scene_bounds))
    base = parse_plan({"shots": [{"id": "s1", "camera": {"fov_mm": 35},
        "scout_anchor": {"from_scout": 0, "look_shift": [0.5, 0.5]}, "path": {"kind": "static"}}]}, d)[0]
    shifted = parse_plan({"shots": [{"id": "s1", "camera": {"fov_mm": 35},
        "scout_anchor": {"from_scout": 0, "look_shift": [0.85, 0.5]}, "path": {"kind": "static"}}]}, d)[0]
    look_base = resolve_plan(base, d)[0].states[0][1].look_at
    look_shift = resolve_plan(shifted, d)[0].states[0][1].look_at
    assert look_base != look_shift  # the compositional intent changes the aim (was dead before)


# --- #4 MD_ prefix applied in the pure layer ---

def test_md_prefix_added_to_bare_camera_name(living_room):
    plan, _ = parse_plan({"shots": [{"id": "s1", "camera": {"name": "hero"},
                                     "anchor": {"relative_to": "sofa_grp"}}]}, living_room)
    assert plan.shots[0].camera.name == "MD_hero"


def test_md_prefix_not_doubled(living_room):
    plan, _ = parse_plan({"shots": [{"id": "s1", "camera": {"name": "MD_Cam_01"},
                                     "anchor": {"relative_to": "sofa_grp"}}]}, living_room)
    assert plan.shots[0].camera.name == "MD_Cam_01"


# --- #3 media-type sniffing ---

def test_media_type_sniffs_jpeg_and_png():
    assert _media_type(b"\xff\xd8\xff\xe0blah") == "image/jpeg"
    assert _media_type(b"\x89PNG\r\n\x1a\nblah") == "image/png"


def test_scout_legend_has_intrinsics(living_room):
    d = replace(living_room, scouts=scout_poses(living_room.scene_bounds))
    legend = _scout_legend(d)
    assert "mm" in legend and "eye" in legend   # pose intrinsics, not just id:label


# --- #12 gpt path refuses to silently drop scout images ---

def test_openai_path_refuses_images():
    msgs = [{"role": "user", "content": [{"type": "text", "text": "hi"},
                                         {"type": "image", "source": {"data": "x"}}]}]
    with pytest.raises(OmegaError):
        complete("k", "sys", msgs, model="gpt-5.5")


# --- #6 backup uses pymxs kwargs (fake-pymxs bridge test) ---

def test_backup_uses_pymxs_kwargs(monkeypatch, tmp_path):
    fake = types.ModuleType("pymxs")
    rt = MagicMock()
    rt.maxFilePath = str(tmp_path) + "/"
    rt.maxFileName = "scene.max"

    def _save(dest, **kw):
        open(dest, "w").close()
        return True
    rt.saveMaxFile.side_effect = _save
    fake.runtime = rt
    monkeypatch.setitem(sys.modules, "pymxs", fake)

    from maxdirector.maxbridge import backup as bmod
    bmod.backup()
    _, kwargs = rt.saveMaxFile.call_args
    assert kwargs.get("useNewFile") is False
    assert kwargs.get("quiet") is True
    assert kwargs.get("clearNeedSaveFlag") is False


# --- #1 the guaranteed crash on the vision-first path is gone ---

def test_controller_compile_and_check_survives_scout_anchor(living_room, monkeypatch):
    from maxdirector.core import director as dmod
    from maxdirector.maxbridge.controller import Controller  # pure top-level imports; ok off-Max

    d = replace(living_room, scouts=scout_poses(living_room.scene_bounds))
    plan, _ = parse_plan({"shots": [{"id": "s1", "camera": {"fov_mm": 24},
        "scout_anchor": {"from_scout": 0}, "path": {"kind": "static"}}]}, d)
    assert plan.shots[0].anchor is None  # the exact condition that used to crash

    monkeypatch.setattr(dmod, "compile_plan", lambda *a, **k: (plan, [], "raw"))
    c = Controller.__new__(Controller)
    c.cfg = type("Cfg", (), {"api_key": "k", "model": "claude-opus-4-8"})()
    c.cv = None
    out_plan, resolved, findings, errors, raw = c.compile_and_check(d, None)
    assert out_plan is not None and resolved   # no AttributeError; the primary path works


# --- grounded bridge fixes (from V-Ray/pymxs docs) — fake-pymxs ---

def _fake_pymxs(monkeypatch):
    import contextlib
    fake = types.ModuleType("pymxs")
    rt = MagicMock()
    rt.isProperty.return_value = True
    fake.runtime = rt
    fake.animate = lambda *a, **k: contextlib.nullcontext()
    fake.attime = lambda *a, **k: contextlib.nullcontext()
    monkeypatch.setitem(sys.modules, "pymxs", fake)
    return fake, rt


def test_create_camera_is_free_camera_and_sets_focal_length(monkeypatch):
    _, rt = _fake_pymxs(monkeypatch)
    from maxdirector.maxbridge.authoring import create_camera
    cam, ok = create_camera("hero", 28.0)
    assert ok
    assert cam.targeted is False            # free camera → cam.transform controls orientation
    assert cam.focal_length == 28.0


def test_vantage_export_includes_frame_range(monkeypatch, tmp_path):
    _, rt = _fake_pymxs(monkeypatch)
    rt.vrayExportVRScene.side_effect = lambda path, **kw: open(path, "w").close()
    from maxdirector.maxbridge.vantage import export_shot_scene
    out = export_shot_scene("MD_Cam_01", 0, 48, str(tmp_path))
    assert out is not None
    _, kwargs = rt.vrayExportVRScene.call_args
    assert kwargs.get("startFrame") == 0 and kwargs.get("endFrame") == 48  # else NO animation
