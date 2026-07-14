"""MaxDirector preflight — one command that tells you EXACTLY what's not ready.

Run it two ways:
  * off-Max (any machine + key):   python scripts/preflight.py [oc_key]
        checks: python, requests, repo import, oc_ key, LIVE gateway ping, CV sidecar.
  * inside 3ds Max (MAXScript listener or startup):
        python.ExecuteFile "<repo>/scripts/preflight.py"
        additionally checks: pymxs, V-Ray camera/sun ctors, active renderer.

Prints a ✓/✗ checklist with the exact fix for each miss, and exits non-zero if any
BLOCKING check fails — so an install problem is diagnosed in seconds, not after a cryptic
dock error. Covers launch blockers #2 (gateway) and #3 (install).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _add_usersite():
    """Mirror bootstrap._ensure_usersite_on_path — Max's embedded Python doesn't add user-site,
    so without this preflight false-negatives on 'requests installed' after a correct install."""
    for env in ("APPDATA", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if base:
            for p in (os.path.join(base, "Python", "Python311", "site-packages"),):
                rp = os.path.realpath(p)
                for cand in (p, rp):
                    if cand and os.path.isdir(cand) and cand not in sys.path:
                        sys.path.insert(0, cand)


_add_usersite()
_rows = []


def check(name, ok, blocking=True, fix=""):
    _rows.append((name, bool(ok), blocking, fix))
    return bool(ok)


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("OC_KEY", "")

    # --- environment ---
    check("Python >= 3.9", sys.version_info >= (3, 9), fix="Max 2026 ships 3.11; install it")
    try:
        import requests  # noqa: F401
        check("requests installed", True)
    except Exception:
        check("requests installed", False,
              fix='pip install --target "%APPDATA%\\Python\\Python311\\site-packages" requests')

    try:
        import maxdirector  # noqa: F401
        from maxdirector.core import provider
        from maxdirector.core.cv_client import CVClient
        from maxdirector.maxbridge import config as cfg_mod
        check("maxdirector importable", True)
    except Exception as e:
        check("maxdirector importable", False, fix=f"set MAXDIRECTOR to the repo path ({e})")
        return _report()

    # --- key + LIVE gateway (blocker #2) ---
    cfg = cfg_mod.load()
    key = key or cfg.api_key
    check("oc_ key present", bool(key), fix="paste your oc_ key in the dock, or pass it as argv[1]")
    if key:
        try:
            provider.ping(key, "claude-opus-4-8")
            check("gateway reachable (opus-4.8)", True)
        except Exception as e:
            check("gateway reachable (opus-4.8)", False, fix=f"check key/network: {e}")
    else:
        check("gateway reachable (opus-4.8)", False, fix="needs a key first")

    # --- CV sidecar (optional; degrades to LLM-only) ---
    try:
        available = CVClient(cfg.sidecar_url).available
    except Exception:
        available = False
    check("CV sidecar (optional)", available, blocking=False,
          fix="python -m cv_sidecar.server  (only needed for best-of-N / reference match)")

    # --- in-Max only ---
    try:
        import pymxs
        rt = pymxs.runtime
        check("running inside 3ds Max (pymxs)", True, blocking=False)
        has_cam = any(getattr(rt, c, None) for c in ("VRayPhysicalCamera", "Physical", "FreeCamera"))
        has_sun = getattr(rt, "VRaySun", None) is not None
        check("V-Ray camera ctor available", has_cam, fix="load V-Ray as the renderer")
        check("VRaySun available", has_sun, blocking=False, fix="load V-Ray")
        try:
            check(f"active renderer: {rt.classOf(rt.renderers.current)}", True, blocking=False)
        except Exception:
            pass
    except Exception:
        check("running inside 3ds Max (pymxs)", False, blocking=False,
              fix="this section only runs inside Max — run there for the full check")

    return _report()


def _report():
    print("\nMaxDirector preflight")
    print("=" * 52)
    blocked = 0
    for name, ok, blocking, fix in _rows:
        mark = "✓" if ok else ("✗" if blocking else "–")
        print(f"  {mark} {name}")
        if not ok:
            if blocking:
                blocked += 1
            if fix:
                print(f"      → {fix}")
    print("=" * 52)
    if blocked:
        print(f"NOT READY — {blocked} blocking check(s) failed above.")
        return 1
    print("READY — all blocking checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
