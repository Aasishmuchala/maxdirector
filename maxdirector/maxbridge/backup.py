"""Backup service — the hard safety guarantee before any apply session.

Ported from MaxOptimizer's Safety v2: ``saveMaxFile <abs> useNewFile:false quiet:true`` makes
a true backup copy WITHOUT changing the current file association. A failed backup aborts the
whole apply — MaxDirector never writes into a real client scene without a net.

Runs inside 3ds Max only. Off-Max it's mocked by tests via ``core.interfaces``-style fakes.
"""

from __future__ import annotations

import os
import time


def _rt():
    import pymxs  # present only inside 3ds Max
    return pymxs.runtime


def backup_path_for(scene_path: str) -> str:
    """Sibling ``<name>.maxdirector-backup.<ts>.max`` next to the scene (or in temp if untitled)."""
    if scene_path and os.path.isdir(os.path.dirname(scene_path)):
        base, _ = os.path.splitext(scene_path)
    else:
        base = os.path.join(os.environ.get("TEMP", "."), "untitled")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return f"{base}.maxdirector-backup.{stamp}.max"


def backup() -> str:
    """Save a backup copy and return its absolute path. Raises on failure."""
    rt = _rt()
    scene = str(rt.maxFilePath) + str(rt.maxFileName)
    dest = backup_path_for(scene)
    # pymxs maps Python kwargs to MAXScript keyword args — the interleaved rt.Name(...) /
    # value positional trick is a MAXScript-source idiom that pymxs would treat as extra
    # positionals and reject, aborting every apply. Use real kwargs.
    ok = rt.saveMaxFile(dest, useNewFile=False, quiet=True, clearNeedSaveFlag=False)
    if not ok or not os.path.exists(dest):
        raise RuntimeError(f"MaxDirector: backup failed to {dest} — apply aborted for safety.")
    return dest
