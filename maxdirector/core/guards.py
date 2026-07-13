"""Animation-safety guards — PURE predicate over NodeInfo.

Object animation is the riskiest feature: MaxDirector must NEVER silently rewrite a rig.
This module decides whether an existing node may be auto-animated. The flags it reads are
populated by the bridge (skin/bone/instance/xref/scripted-controller detection ported from
MaxOptimizer's scene_query). A flagged node is refused with a human-readable reason unless
the user explicitly opts it in.
"""

from __future__ import annotations

from typing import Optional, Tuple

from .models import NodeInfo


def anim_reason(node: NodeInfo) -> Optional[str]:
    """Return the reason a node is NOT animation-safe, or None if it is safe."""
    if node.is_skinned:
        return "skinned mesh (part of a character rig)"
    if node.is_bone:
        return "bone / rig node"
    if node.is_instanced:
        return "instanced geometry (would move all copies)"
    if node.is_xref:
        return "XRef object (owned by another file)"
    if node.has_scripted_ctrl:
        return "driven by a script controller"
    return None


def is_anim_safe(node: NodeInfo) -> bool:
    return anim_reason(node) is None


def check_anim(node: NodeInfo, opted_in: bool = False) -> Tuple[bool, str]:
    """(allowed, message). Safe nodes always pass; flagged nodes pass only if opted_in."""
    reason = anim_reason(node)
    if reason is None:
        return True, "safe"
    if opted_in:
        return True, f"opted-in despite: {reason}"
    return False, f"refused — {reason} (manual review; opt in explicitly to override)"
