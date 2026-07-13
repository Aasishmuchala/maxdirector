"""Which renderer is active — detected by CLASS, robustly (V-Ray class names change per
hotfix; MaxOptimizer's lesson). We only need to know it's V-Ray CPU vs GPU and expose safe
property writes; MaxDirector authors mostly renderer-agnostic objects (cameras/lights)."""

from __future__ import annotations


def _rt():
    import pymxs
    return pymxs.runtime


def renderer_name() -> str:
    rt = _rt()
    try:
        return str(rt.classOf(rt.renderers.current))
    except Exception:
        return "unknown"


def is_vray() -> bool:
    return "vray" in renderer_name().lower()


def is_vray_gpu() -> bool:
    return "gpu" in renderer_name().lower() or "rt" in renderer_name().lower()


def discover_prop(prop: str):
    """Return the actual property Name on the current renderer that matches ``prop`` (GPU/CPU
    property names differ) — mirrors LightMatch's engine-aware discovery. None if absent."""
    rt = _rt()
    try:
        for p in rt.getPropNames(rt.renderers.current):
            if str(p).lower() == prop.lower():
                return p
    except Exception:
        pass
    return None
