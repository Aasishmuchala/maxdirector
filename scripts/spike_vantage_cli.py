"""P0-T4 SPIKE — Chaos Vantage batch CLI. Prove the sequential shot-by-shot render works.

Two parts:
  1. In Max: export a 2-key camera's animation range as a .vrscene/.vantage (see
     maxbridge.vantage.export_shot_scene — run that from the dock or a small mxs).
  2. Here: render a 5-frame range via vantage_console.exe on that scene file.

    python scripts/spike_vantage_cli.py <scene.vantage> [console_exe]

PASS = 5 frames land in ./renders/. Confirms the batch mechanism + whether a headless
license is required (watch the console output).
"""

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from maxdirector.core.render.backend import RenderJob  # noqa: E402
from maxdirector.core.render.vantage import vantage_commands  # noqa: E402


def main():
    if len(sys.argv) < 2:
        print("usage: spike_vantage_cli.py <scene.vantage> [vantage_console.exe]")
        return 2
    scene = sys.argv[1]
    exe = sys.argv[2] if len(sys.argv) > 2 else r"C:\Program Files\Chaos\Vantage\vantage_console.exe"
    os.makedirs("renders", exist_ok=True)
    job = RenderJob(shot_id="spike", camera_name="", frame_start=0, frame_end=4,
                    width=1280, height=720, fmt="png", output="renders/spike.####.png")
    cmd = vantage_commands([job], {"spike": scene}, console_exe=exe)[0]
    print("running:", " ".join(cmd))
    rc = subprocess.run(cmd).returncode
    frames = [f for f in os.listdir("renders") if f.startswith("spike")]
    print(f"exit={rc}; frames written: {len(frames)}")
    print("Checkpoint-0 Vantage:", "GO" if rc == 0 and frames else "CHECK (see output/licence)")
    return 0 if rc == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
