"""Settings + the oc_ key, stored at %LOCALAPPDATA%/MaxDirector/config.json.

The key is never committed to the repo (see .gitignore) and never sent anywhere but the
Omega gateway. Pure-ish (stdlib only) so the controller can import it off-Max too.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass


def _config_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "MaxDirector")
    os.makedirs(d, exist_ok=True)
    return d


CONFIG_PATH = os.path.join(_config_dir(), "config.json")


@dataclass
class Config:
    api_key: str = ""                       # oc_ gateway key
    model: str = "claude-opus-4-8"          # or "gpt-5.5" once the routing spike confirms it
    sidecar_url: str = "http://127.0.0.1:8765"
    use_cv_sidecar: bool = True
    commercial_safe_cv: bool = True         # default: outputs feed paid work
    vantage_console: str = r"C:\Program Files\Chaos\Vantage\vantage_console.exe"
    best_of_n: int = 3

    def save(self) -> None:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=1)


def load() -> Config:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
        cfg = Config()
        for k, v in d.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
        return cfg
    except (OSError, ValueError):
        return Config()
