"""Launch entry point — checks deps BEFORE importing the UI, so a missing package shows a
clear message box in Max instead of a raw ImportError. The startup macro calls
``maxdirector.bootstrap.launch()``. Imports nothing heavy at module top level.

Core runtime needs only ``requests`` (Omega + Poly Haven). numpy/Pillow are NOT required in
Max — the CV models live in the separate sidecar venv. (Ported from LightMatch's bootstrap.)
"""

from __future__ import annotations

import importlib
import os
import sys

REQUIRED = ("requests",)


def _ensure_usersite_on_path() -> None:
    candidates = []
    try:
        import site
        candidates.append(site.getusersitepackages())
    except Exception:
        pass
    for env_var in ("APPDATA", "LOCALAPPDATA"):
        base = os.environ.get(env_var)
        if base:
            candidates.append(os.path.join(base, "Python", "Python311", "site-packages"))
    for path in candidates:
        for cand in (path, os.path.realpath(path) if path else None):
            if cand and cand not in sys.path and os.path.isdir(cand):
                sys.path.insert(0, cand)


def _missing() -> list:
    _ensure_usersite_on_path()
    out = []
    for mod in REQUIRED:
        try:
            importlib.import_module(mod)
        except Exception:
            out.append(mod)
    return out


def launch():
    missing = _missing()
    if missing:
        msg = ("MaxDirector needs these Python packages in 3ds Max's Python:\n    "
               + ", ".join(missing)
               + "\n\nInstall (from a normal command prompt):\n"
               '    python -m pip install --target "%APPDATA%\\Python\\Python311\\site-packages" requests\n\n'
               "Then reopen MaxDirector.")
        try:
            from pymxs import runtime as rt  # type: ignore
            rt.messageBox(msg, title="MaxDirector — missing dependencies")
        except Exception:
            print("[MaxDirector] " + msg)
        return None
    from .ui.dock import show_dock
    return show_dock()
