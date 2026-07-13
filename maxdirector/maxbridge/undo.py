"""Undo wrapper — ONE undo record per plan so a single Ctrl+Z reverts the whole apply.

Uses explicit ``theHold`` begin/accept/cancel rather than raw ``pymxs.undo`` (which swallows
exceptions and can silently commit a half-done apply — MaxOptimizer's documented reason). On
success we Accept one named entry; on any exception we Cancel EXACTLY this hold (never a blind
``max undo``, which could roll back the user's *previous* action). The backup is the real
guarantee; this keeps the undo stack clean.
"""

from __future__ import annotations

from contextlib import contextmanager


@contextmanager
def one_undo(label: str = "MaxDirector apply"):
    import pymxs
    rt = pymxs.runtime
    rt.theHold.Begin()
    try:
        yield
    except Exception:
        # roll back exactly this hold — LIFO-legal, does not touch earlier user actions
        try:
            rt.theHold.Cancel()
        except Exception:
            pass
        raise
    else:
        try:
            rt.theHold.Accept(label)
        except Exception:
            # if Accept fails, cancel rather than leave an open hold
            try:
                rt.theHold.Cancel()
            except Exception:
                pass
            raise
