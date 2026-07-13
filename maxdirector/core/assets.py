"""Asset-gap detection + internet research — the plugin fetches, the model supplies keywords.

Gap DETECTION is deterministic (digest + storyboard intent). RESEARCH hits the Poly Haven
public API for skies (fully automatable); furniture/props are surfaced as Cosmos suggestions
(no public API) and bespoke items go to the Higgsfield GLB path. The network call is injected
(``fetch_json``) so ranking/parsing is unit-tested without the network, and nothing downloads
without explicit user approval (enforced by the UI/controller, not here).
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from .models import AssetGap, Category, Digest, Storyboard

POLYHAVEN_API = "https://api.polyhaven.com"

_EXTERIOR_MOVES = {"establish", "crane_reveal", "pull_out"}


def detect_gaps(storyboard: Storyboard, digest: Digest) -> List[AssetGap]:
    """Augment the model's foreseen gaps with deterministic ones it may have missed."""
    gaps: List[AssetGap] = list(storyboard.asset_gaps)
    seen = {(g.shot_id, g.kind) for g in gaps}

    has_env = bool(digest.environment_map)
    for s in storyboard.shots:
        # an establishing/exterior/reveal beat with no environment → needs a sky
        if not has_env and s.camera_move.value in _EXTERIOR_MOVES and (s.id, "sky") not in seen:
            gaps.append(AssetGap(
                shot_id=s.id, kind="sky",
                reason="establishing/reveal shot but the scene has no environment/HDRI",
                keywords=_sky_keywords(s.mood or storyboard.grade_mood),
            ))
            seen.add((s.id, "sky"))
    return gaps


def _sky_keywords(mood: str) -> List[str]:
    m = (mood or "").lower()
    kws = ["sky"]
    for token, kw in (("golden", "sunset"), ("dawn", "sunrise"), ("overcast", "overcast"),
                      ("night", "night"), ("clear", "clear"), ("dramatic", "partly cloudy")):
        if token in m:
            kws.append(kw)
    if len(kws) == 1:
        kws.append("partly cloudy")
    return kws


# ------------------------------------------------------------------ Poly Haven (skies)

def _default_fetch(url: str) -> dict:
    import requests  # lazy so the pure suite need not hit the network
    return requests.get(url, timeout=20).json()


def search_hdris(
    keywords: List[str],
    fetch_json: Callable[[str], dict] = _default_fetch,
    limit: int = 5,
) -> List[dict]:
    """Return ranked HDRI candidates from Poly Haven. Each: {id,name,categories,tags,score}."""
    data = fetch_json(f"{POLYHAVEN_API}/assets?t=hdris")
    if not isinstance(data, dict):
        return []
    kw = {k.lower() for k in keywords}
    scored = []
    for aid, meta in data.items():
        if not isinstance(meta, dict):
            continue
        tags = {str(t).lower() for t in meta.get("tags", [])}
        cats = {str(c).lower() for c in meta.get("categories", [])}
        overlap = len(kw & (tags | cats))
        name_hit = any(k in str(meta.get("name", "")).lower() for k in kw)
        score = overlap + (1 if name_hit else 0) + min(meta.get("download_count", 0), 100000) / 1e6
        if overlap or name_hit:
            scored.append({"id": aid, "name": meta.get("name", aid),
                           "categories": sorted(cats), "tags": sorted(tags),
                           "score": round(score, 4)})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]


def hdri_file_urls(asset_id: str, resolution: str = "4k", fetch_json: Callable[[str], dict] = _default_fetch) -> Dict[str, str]:
    """Resolve download URLs (hdr/exr) for an HDRI at a resolution, via /files/{id}."""
    data = fetch_json(f"{POLYHAVEN_API}/files/{asset_id}")
    out: Dict[str, str] = {}
    if not isinstance(data, dict):
        return out
    hdri = data.get("hdri", {})
    for fmt in ("hdr", "exr"):
        node = hdri.get(resolution, {}).get(fmt)
        if isinstance(node, dict) and node.get("url"):
            out[fmt] = node["url"]
    return out
