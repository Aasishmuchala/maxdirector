"""Apply journal — a JSON breadcrumb of every apply session for crash recovery.

Written before/during apply so a mid-apply crash is diagnosable and recoverable from the
backup. Stored under %LOCALAPPDATA%/MaxDirector/journal/.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict


def _journal_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "MaxDirector", "journal")
    os.makedirs(d, exist_ok=True)
    return d


class Journal:
    def __init__(self, scene_path: str, backup_path: str):
        stamp = time.strftime("%Y%m%d-%H%M%S")
        self.path = os.path.join(_journal_dir(), f"apply-{stamp}.json")
        self.data: Dict[str, Any] = {
            "scene": scene_path, "backup": backup_path, "started": stamp, "ops": [],
        }
        self._flush()

    def record(self, op: str, target: str, status: str, detail: str = "") -> None:
        self.data["ops"].append({"op": op, "target": target, "status": status, "detail": detail})
        self._flush()

    def finish(self, status: str) -> None:
        self.data["finished"] = status
        self._flush()

    def _flush(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=1)
        except OSError:
            pass
