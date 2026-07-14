# MaxDirector — Launch Runbook

The path from "code on GitHub" to "working in my Max." Do the steps in order; each ends with
a check. Run `python scripts/preflight.py` anytime to see exactly what's not ready.

---

## 0 · Prove the bet FIRST (30 min, no Max, no GPU) — the GO/NO-GO

Before installing anything, confirm the LLM actually places good cameras when it sees the scene.

1. In any DCC, render 4–6 wide views of a real Sthyra scene (room corners + a plan view). Save
   them as `views/scout0.png … scout5.png` (png/jpg/webp all fine).
2. `python scripts/experiment_placement.py --images ./views --key oc_YOURKEY --prompt "cinematic golden-hour 3-shot reveal of the living room"`
3. Read the shots it prints: sensible vantages? sensible moves? believable framing for *those*
   images? **If yes → GO** (continue below). **If no → stop** and we rethink placement before
   spending time on the Max integration.

---

## 1 · Install into 3ds Max 2026 (15 min)

```powershell
# a) get the code
git clone https://github.com/Aasishmuchala/maxdirector C:\Users\you\maxdirector
setx MAXDIRECTOR C:\Users\you\maxdirector

# b) the one runtime dep, into Max's Python user-site
"C:\Program Files\Autodesk\3ds Max 2026\Python\python.exe" -m pip install ^
  --target "%APPDATA%\Python\Python311\site-packages" requests

# c) register the toolbar action
copy C:\Users\you\maxdirector\maxdirector\startup\maxdirector_startup.py ^
  "%LOCALAPPDATA%\Autodesk\3dsMax\2026 - 64bit\ENU\scripts\startup\"
```

Restart Max → Customize → Customize User Interface → category **MaxDirector** → drag the action
onto a toolbar. Click it, paste your `oc_` key in the dock (stored at
`%LOCALAPPDATA%/MaxDirector/config.json`, never committed).

**Check:** inside Max's MAXScript listener run
`python.ExecuteFile "C:\Users\you\maxdirector\scripts\preflight.py"` — every blocking row ✓.

---

## 2 · P0 spikes — prove the plumbing (~1 hr)

```powershell
# gateway routing (any machine)
python scripts\spike_provider_ping.py oc_YOURKEY          # opus-4.8 must PING OK

# headless V-Ray create/read-back
"C:\Program Files\Autodesk\3ds Max 2026\3dsmaxbatch.exe" -mxs "scripts\run_spike_create.ms"
#   → prints SMOKE_OK

# Vantage batch (after exporting one shot's .vantage from the dock)
python scripts\spike_vantage_cli.py C:\path\to\shot.vantage   # 5 frames land in .\renders\
```

**Checkpoint 0:** all three green.

---

## 3 · First live MVP smoke (the moment of truth)

Open a real scene → dock → type a brief → **Direct → Compile → Apply → Render (V-Ray)**.

Expect the untested bridge to surface a few issues on first contact. The most likely ones are
already pre-hardened (free camera + `targeted=False`, `focal_length`, integer keyframes,
`vrayExportVRScene startFrame/endFrame`, backup kwargs). If something still breaks, it's almost
certainly a property/method name specific to your V-Ray 7 build — grab the exact error from the
listener and it's a one-line fix in `maxbridge/`.

**Checkpoint 1 = launch-ready:** a brief produces approved, keyframed, read-back-verified
cameras and a rendered V-Ray sequence on a real scene.

---

## Later (not blocking launch)
- Wire the CV sidecar (GeoCalib first) for reference-image match — `cv_sidecar/requirements-sidecar.txt`.
- Confirm Vantage headless licensing; V-Ray sequence is the guaranteed fallback.
- Scout coverage tuning, compound/bezier moves.

## If something's wrong
`python scripts/preflight.py [oc_key]` — off-Max checks deps/key/gateway/sidecar; inside Max it
also checks pymxs + V-Ray. Every failing row prints its fix.
