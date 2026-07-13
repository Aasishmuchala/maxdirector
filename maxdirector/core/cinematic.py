"""The cinematic knowledge pack — the Director's creative vocabulary (adapted from
cinematic-ui into real-3D terms). Loaded progressively into the prompt to keep it lean.

Ships with compact built-in defaults so the plugin works before the fuller
``data/cinematic/*.json`` packs are generated; ``load`` overlays those when present.
"""

from __future__ import annotations

import json
import os
from typing import Dict, Optional

# move -> guidance the model reasons with (the real-3D analog of camera-shots-50)
MOVES: Dict[str, dict] = {
    "static": {"best_for": "detail, product, portrait holds", "ease": "linear"},
    "push_in": {"best_for": "building intimacy, revealing a subject", "film": "Goodfellas"},
    "pull_out": {"best_for": "context reveal, loneliness/scale", "film": "The Shining"},
    "orbit": {"best_for": "hero object, showing form in the round", "film": "Matrix"},
    "crane_up": {"best_for": "leaving a space, transcendence", "film": "many finales"},
    "crane_down": {"best_for": "descending into a scene", "film": "Touch of Evil"},
    "crane_reveal": {"best_for": "establishing reveal over foreground", "film": "Gone with the Wind"},
    "track": {"best_for": "walking a viewer through a space", "film": "Oldboy"},
    "dolly_zoom": {"best_for": "unease, a realisation beat", "film": "Vertigo"},
    "establish": {"best_for": "opening a sequence, wide then in", "film": "2001"},
    "product_360": {"best_for": "full turntable of an object", "film": "product film"},
    "tilt": {"best_for": "revealing height, top-to-bottom", "film": "The Shining hallway"},
    "pan": {"best_for": "connecting two subjects laterally", "film": "Grand Budapest"},
    "bezier": {"best_for": "a bespoke fly-through", "film": "architectural reel"},
}

DIRECTORS: Dict[str, str] = {
    "villeneuve": "vast scale, slow deliberate moves, symmetry, long lenses, atmosphere/fog",
    "deakins": "motivated naturalistic light, restrained elegant moves, negative space",
    "kubrick": "one-point symmetry, wide lenses, slow zooms, centred framing",
    "wong_kar_wai": "warm saturated palette, intimate handheld, slow shutter smear",
    "fincher": "precise, cold, controlled dollies, desaturated teal, deep shadow",
    "malick": "golden-hour, wandering handheld, sky and nature, wide lenses",
}


def load(data_dir: Optional[str] = None) -> "CinematicPack":
    moves = dict(MOVES)
    directors = dict(DIRECTORS)
    if data_dir:
        moves.update(_load_json(os.path.join(data_dir, "camera_moves.json")))
        directors.update(_load_json(os.path.join(data_dir, "directors.json")))
    return CinematicPack(moves, directors)


def _load_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


class CinematicPack:
    def __init__(self, moves: dict, directors: dict):
        self.moves = moves
        self.directors = directors

    def prompt_block(self, director_style: Optional[str] = None) -> str:
        lines = ["CAMERA MOVES (choose per shot; each resolves to a real 3D path):"]
        for k, v in self.moves.items():
            lines.append(f"  - {k}: {v.get('best_for', '')}")
        if director_style:
            key = director_style.strip().lower().replace(" ", "_")
            tend = self.directors.get(key)
            if tend:
                lines.append(f"DIRECTOR STYLE — {director_style}: {tend}")
        else:
            lines.append("DIRECTOR STYLES available: " + ", ".join(self.directors))
        return "\n".join(lines)
