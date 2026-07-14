# MaxDirector

An LLM cinematographer inside **3ds Max 2026 + V-Ray 7**. Type a brief (or hand it a
reference image / video), and — driven by **Opus 4.8 or GPT-5.5 through the Omega gateway**,
grounded by a **local computer-vision layer** — it art-directs and builds the **cameras,
animation, lighting, and render setup** as a cinematic multi-shot sequence, fills missing
skies/assets from the internet, and renders through **V-Ray or Chaos Vantage** (Vantage as an
unattended shot-by-shot batch). Internal tool for the Sthyra pipeline; not a product.

Target: **~95% reliability on real scenes**, always human-approved.

## How the Director works (LLM plans · CV grounds · plugin executes · you approve)

```
① UNDERSTAND  scene → digest + SCOUT VIEWS (auto-placed cameras rendered to thumbnails)
② BRIEF       intent + director/mood/duration/aspect/backend; optional reference image/video
③ DIRECT ►LLM digest + SCOUT IMAGES + cinematic pack → STORYBOARD (each shot picks a scout) [approve]
④ GAPS        sky → Poly Haven (auto) · furniture → Cosmos (guided) · bespoke → GLB  [approve]
⑤ COMPILE►LLM storyboard + scout images → PLAN via SCOUT ANCHORS ("from scout N, nudge") 
⑤·5 GROUND    bridge resolves anchors → transforms from KNOWN scout poses; geometric CRITIC;
              best-of-N scoring (composition + CV aesthetic/reference)
⑥ BUILD       preview → [approve] → apply (backup + one undo + read-back verify) → render
```

**Vision-first placement** is the load-bearing design choice: the model reasons over rendered
scout images (with known camera poses) and places a camera by nudging from a view it can *see*
— not by guessing 3D from bounding boxes and often-meaningless node names (`Box001`,
`Editable_Poly_47`). It never emits world coordinates ("camera in the void" fix) and never
browses — the plugin does all scene I/O, web fetches, and rendering.

**Validate the core bet first** (off-Max, no GPU): `python scripts/experiment_placement.py
--images ./views --key oc_… --prompt "…"` feeds a few rendered scene views to the real gateway
and prints the shots the model chose — so you can judge whether placement is actually good
before building anything further.

## Architecture (hexagon)

```
maxdirector/core/       PURE python, ZERO pymxs/torch — the planning brain (unit-tested off-Max)
maxdirector/maxbridge/  the ONLY pymxs importer — digest, authoring, render, vantage, safety
maxdirector/ui/         PySide6 dock
cv_sidecar/             separate torch+CUDA HTTP service (GeoCalib/DA-V2/MegaSaM/MUSIQ) — STUBbable
maxdirector/data/       cinematic knowledge pack + verified V-Ray-7 technical pack
scripts/                P0 spikes (model routing, headless create, Vantage CLI, sidecar)
tests/                  pytest — runs on any OS, no Max
```

`core` is enforced pymxs-free by a test, so the whole Director runs and is tested on macOS.

## Launch

Follow **[docs/RUNBOOK.md](docs/RUNBOOK.md)** — prove the bet → install → spikes → first live
smoke. Run **`python scripts/preflight.py [oc_key]`** anytime to see exactly what's not ready
(deps, key, live gateway ping, CV sidecar; inside Max it also checks pymxs + V-Ray).

## Install (on the Max 2026 box)

1. Clone to e.g. `C:\Users\you\maxdirector`; set env var `MAXDIRECTOR` to that path.
2. Into Max's Python user-site: `python -m pip install --target "%APPDATA%\Python\Python311\site-packages" requests`
3. Copy `maxdirector/startup/maxdirector_startup.py` into
   `%LOCALAPPDATA%/Autodesk/3dsMax/2026 - 64bit/ENU/scripts/startup/`.
4. Restart Max → Customize → drag the **MaxDirector** action onto a toolbar.
5. Paste your `oc_` key in the dock (stored at `%LOCALAPPDATA%/MaxDirector/config.json`).

### CV sidecar (optional but recommended — the path to 95%)

Runs in its **own** Python+CUDA venv (never Max's). Works in **stub mode** with zero heavy
deps so the pipeline runs immediately; install `cv_sidecar/requirements-sidecar.txt` for the
real models. Start: `python -m cv_sidecar.server`. Commercial-safe stack by default
(GeoCalib + Depth Anything V2-Small + MegaSaM-swapped + MUSIQ) so outputs stay clean for paid
renders; non-commercial models are an opt-in toggle for non-paid experiments.

## Develop / test (any OS, no Max)

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
python -m pytest            # 48 pure tests, green on macOS/Linux/Windows
python scripts/spike_sidecar.py   # sidecar<->client roundtrip (stub mode)
```

## Status

- **Pure core: complete + tested** (48 tests) — anchors, schemas, critic, best-of-N, resolve,
  director, assets, reference, render planning; the full MVP pipeline proven end-to-end off-Max.
- **Bridge / sidecar / UI / data / spikes: complete source**, runs on the Max 2026 + GPU box.
  Sidecar verified in stub mode on macOS.
- **Next (on your box):** run the P0 spikes (`scripts/spike_*`) → Checkpoint 0, then the live
  in-Max MVP smoke on a real Sthyra scene → Checkpoint 1.

Spec: [SPEC.md](SPEC.md) · Plan + checklist: [tasks/plan.md](tasks/plan.md) · [tasks/todo.md](tasks/todo.md)
