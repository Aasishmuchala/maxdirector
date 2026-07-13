"""P0-T5 SPIKE — CV sidecar handshake. Start the sidecar and round-trip every route via the
client. Passes in STUB mode (no torch) so you can prove the wiring before downloading models.

    python scripts/spike_sidecar.py
"""

import os
import sys
import threading
import time
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cv_sidecar import server  # noqa: E402
from maxdirector.core.cv_client import CVClient  # noqa: E402


def main():
    httpd = ThreadingHTTPServer((server.HOST, server.PORT), server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    time.sleep(0.4)
    cv = CVClient(f"http://{server.HOST}:{server.PORT}")
    checks = {
        "health": cv.available,
        "calibrate": cv.calibrate("ref.png") is not None,
        "similarity": cv.similarity("ref.png", ["v.png"]) is not None,
        "aesthetic": cv.aesthetic("c.png") is not None,
        "video_motion": cv.video_motion("clip.mp4") is not None,
        "framing_delta": cv.framing_delta("ref.png", "cur.png") is not None,
    }
    httpd.shutdown()
    for k, v in checks.items():
        print(f"  {k:14} {'OK' if v else 'FAIL'}")
    ok = all(checks.values())
    print("Checkpoint-0 sidecar:", "GO" if ok else "BLOCKED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
