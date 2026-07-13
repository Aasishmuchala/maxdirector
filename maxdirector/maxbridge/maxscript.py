"""MaxScript hot-path helpers — cross the pymxs↔MaxScript boundary once for the loops that
would be ~10x slower in a Python per-node loop (MaxOptimizer's documented rule).

Currently: scripted-controller detection (pymxs cannot reliably READ a node's sub-controller,
but MAXScript resolves it), in one pass. Extend with a bulk bbox/flag reader if the digest of
very large scenes gets slow.
"""

from __future__ import annotations

_SCRIPTED_FN = r"""
fn mdScriptedHandles = (
    local out = #()
    for n in objects do (
        local hit = false
        try (
            local ctrls = #(n.transform.controller, n.position.controller,
                            n.rotation.controller, n.scale.controller)
            for c in ctrls do (
                if c != undefined and matchpattern ((classof c) as string) pattern:"*Script*" do hit = true
            )
        ) catch ()
        if hit do append out (getHandleByAnim n)
    )
    out
)
"""

_COMPILED = False


def _rt():
    import pymxs
    return pymxs.runtime


def ensure_compiled() -> None:
    global _COMPILED
    if not _COMPILED:
        _rt().execute(_SCRIPTED_FN)
        _COMPILED = True


def scripted_handles() -> set:
    ensure_compiled()
    try:
        return {int(h) for h in _rt().mdScriptedHandles()}
    except Exception:
        return set()
