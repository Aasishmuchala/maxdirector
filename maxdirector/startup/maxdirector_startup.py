"""3ds Max startup hook — copy this file into
  %LOCALAPPDATA%/Autodesk/3dsMax/2026 - 64bit/ENU/scripts/startup/
and set MAXDIRECTOR_REPO below (or the MAXDIRECTOR env var) to the repo path.
Registers a "MaxDirector" macroscript under category "MaxDirector" — bind it to a toolbar
button / hotkey via Customize → Customize User Interface. (LightMatch install pattern.)
"""

import os
import sys

MAXDIRECTOR_REPO = os.environ.get("MAXDIRECTOR", r"C:\Users\aasis\maxdirector")


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
    _prep_path()
    from pymxs import runtime as rt  # type: ignore
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
except Exception as e:  # never break Max startup
    print(f"[maxdirector] startup registration failed: {e}")
