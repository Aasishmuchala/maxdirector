"""3ds Max startup hook — copy this file into
  %LOCALAPPDATA%/Autodesk/3dsMax/2026 - 64bit/ENU/scripts/startup/
and set MAXDIRECTOR_REPO below (or the MAXDIRECTOR env var) to the repo path.
Registers a "MaxDirector" macroscript under category "MaxDirector" — bind it to a toolbar
button / hotkey via Customize → Customize User Interface. (LightMatch install pattern.)
"""

import os
import sys


def _repo_path():
    """Resolve the clone folder: MAXDIRECTOR env var, else the path saved in config.json at
    install (env vars set by `setx` don't reach an already-running Max, so config is the
    reliable source). Returns '' if neither is set."""
    env = os.environ.get("MAXDIRECTOR", "").strip()
    if env and os.path.isdir(env):
        return env
    try:
        import json
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        cfg = os.path.join(base, "MaxDirector", "config.json")
        with open(cfg, "r", encoding="utf-8") as f:
            p = json.load(f).get("repo_path", "")
        if p and os.path.isdir(p):
            return p
    except Exception:
        pass
    return env


MAXDIRECTOR_REPO = _repo_path()


def _prep_path():
    if MAXDIRECTOR_REPO not in sys.path:
        sys.path.insert(0, MAXDIRECTOR_REPO)
    try:
        import site
        usp = site.getusersitepackages()
        if usp and usp not in sys.path and os.path.isdir(usp):
            sys.path.insert(0, usp)
    except Exception:
        pass


def _register():
    from pymxs import runtime as rt  # type: ignore
    if not MAXDIRECTOR_REPO:
        rt.messageBox(
            "MaxDirector: set the MAXDIRECTOR environment variable to your clone folder "
            "(or run scripts/install.bat), then restart Max.", title="MaxDirector")
        return
    _prep_path()
    rt.macros.new(
        "MaxDirector", "MaxDirector",
        "Open MaxDirector — direct cameras, animation, lighting & render from a brief",
        "MaxDirector",
        'python.Execute "import sys, os; '
        "[sys.path.insert(0, p) for p in ["
        "os.path.join(os.environ.get('APPDATA', ''), 'Python', 'Python311', 'site-packages')"
        '] if p and os.path.isdir(p)]; '
        'import maxdirector.bootstrap as _mdb; _mdb.launch()"',
    )


try:
    _register()
except Exception as e:  # never break Max startup — but SAY so (silent no-op is the trap)
    print(f"[maxdirector] startup registration failed: {e}")
    try:
        from pymxs import runtime as rt  # type: ignore
        rt.messageBox(f"MaxDirector failed to register: {e}", title="MaxDirector")
    except Exception:
        pass
