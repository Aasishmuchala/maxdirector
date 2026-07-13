"""MaxDirector CV sidecar — a localhost HTTP service (stdlib only) fronting the CV models.

Runs in its OWN Python + CUDA venv (never Max's 3.11). The plugin's ``core.cv_client`` talks
to it. Works in STUB mode with zero heavy deps installed, so you can wire the pipeline end to
end before downloading GeoCalib / Depth Anything / MegaSaM. Start it with:

    python -m cv_sidecar.server            # 127.0.0.1:8765

Routes (all POST, JSON in/out): /health /similarity /calibrate /aesthetic /reference_match
/framing_delta /video_motion. See cv_sidecar/README.md for the real-model install.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import backends

HOST, PORT = "127.0.0.1", 8765

_sim = backends.Similarity()
_cal = backends.Calibration()
_aes = backends.Aesthetic()
_depth = backends.Depth()
_refm = backends.ReferenceMatch(depth=_depth)
_motion = backends.Motion()
_refine = backends.FramingRefine()


def _route(path: str, body: dict) -> dict:
    if path == "/health":
        return {"ok": True, "stub_mode": _cal.model is None}
    if path == "/similarity":
        return _sim.compare(body["ref"], body.get("views", []))
    if path == "/calibrate":
        return _cal.calibrate(body["ref"])
    if path == "/aesthetic":
        return {"score": _aes.score(body["png"])}
    if path == "/reference_match":
        return {"score": _refm.score(body["png"], body["ref"])}
    if path == "/framing_delta":
        return _refine.delta(body["ref"], body["current"])
    if path == "/video_motion":
        return _motion.signature(body["source"])
    return {"error": f"unknown route {path}"}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw or b"{}")
            result = _route(self.path, body)
            code = 200
        except Exception as e:  # noqa: BLE001
            result = {"error": str(e)}
            code = 500
        payload = json.dumps(result).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):  # keep the console quiet
        pass


def main():
    print(f"MaxDirector CV sidecar on http://{HOST}:{PORT} (stub_mode={_cal.model is None})")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
