# MaxDirector — Implementation Plan (v2, MVP-first)

Spec: [../SPEC.md](../SPEC.md). Internal tool; no productization. Reliability goal ~95% via
semantic anchors + geometric critic + best-of-N + a CV sidecar (analysis-by-synthesis).

## Dependency graph
```
P0 spikes (model routing · headless V-Ray create · Vantage CLI · CV-sidecar handshake)
 → P1 MVP: digest → storyboard → anchor moves → resolve → critic+best-of-N → preview → apply → V-Ray
 → P2 reference-image match (GeoCalib + DA-V2 + render-and-compare) + LightMatch lighting
 → P3 Vantage batch  → P4 asset research  → P5 video move + guarded object animation
```

## Status of the build
- **Pure core (P0/T1 + pure logic of P1–P5): DONE, 48 tests green off-Max.** anchors, schemas,
  critic, scoring, resolve, director, assets, reference, render planning, provider, guards.
- **Bridge / sidecar / UI / data / spikes: source complete.** Runs on the Max 2026 + GPU box;
  sidecar verified in stub mode on macOS.
- **Remaining = verification on your box:** run the P0 spikes → Checkpoint 0; live MVP smoke →
  Checkpoint 1; then P2–P5 live-verify per phase.

## Phases (acceptance · verification)
- **P0** T1 pure core ✅ · T2 `spike_provider_ping.py` (opus+gpt-5.5) · T3 `spike_headless_create`
  (VRayPhysicalCamera+VRaySun read-back) · T4 `spike_vantage_cli` (5-frame batch) · T5
  `spike_sidecar` (roundtrip ✅ stub). **Checkpoint 0.**
- **P1 MVP** digest → direct → compile → resolve → critic+best-of-N → preview → apply (backup+
  one-undo+verify) → V-Ray sequence. AC: a brief builds keyframed, critic-clean, verified
  cameras + renders on a real scene. **Checkpoint 1.**
- **P2** reference-image: similarity gate (reject non-matching) → GeoCalib seed → render-and-
  compare converge → LightMatch lighting. **Checkpoint 2.**
- **P3** Vantage batch (per-shot export + `vantage_console` sequential queue). **Checkpoint 3.**
- **P4** asset research (Poly Haven auto · Cosmos guided · Higgsfield GLB). **Checkpoint 4.**
- **P5** video move (MegaSaM/RAFT normalized retarget) + guarded object animation. **Checkpoint 5.**

## CV sidecar bring-up (raises P2/P5 quality from stub)
Install `cv_sidecar/requirements-sidecar.txt` in a CUDA venv; wire the real models at the
`NotImplementedError` seams in `cv_sidecar/backends.py` (GeoCalib, DA-V2-Small, OpenCLIP,
MUSIQ/NIMA, MegaSaM/RAFT + CMA-ES). Set `MAXDIRECTOR_CV_REAL=1` to forbid stubs in production.
