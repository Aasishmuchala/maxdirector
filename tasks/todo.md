# MaxDirector — Task List

Legend: [x] done & tested · [~] source complete, needs on-box verification · [ ] not started

## Pure core (P0/T1 + pure logic) — 48 tests green off-Max
- [x] models, anchors (+resolver), guards, provider, omega
- [x] storyboard + plan_schema validators (illegal node/class/guard refusal, clamping)
- [x] critic (void/solid/frustum/collision/degenerate) + best-of-N scoring
- [x] resolve (plan → keyframed camera states), digest_format, cinematic, director
- [x] assets (Poly Haven client + gap detection), reference (similarity gate, calibration map, motion map)
- [x] render planning (jobs + Vantage command builder), cv_client
- [x] end-to-end MVP pipeline test + no-pymxs/no-torch enforcement test

## Bridge (runs on Max box) — source complete
- [~] digest.collect_digest (census + geometry inventory + guard flags)
- [~] authoring (create camera/keyframe/lights/env/render + read-back verify, one undo, MD_ namespace)
- [~] safety trio: backup / undo / journal · renderer_query · maxscript hot-path
- [~] framing (playblast), vray_render (sequence), vantage (export + sequential batch), asset_import
- [~] config (oc_ key store), controller (pipeline orchestrator)

## CV sidecar — stub verified, real models pending
- [x] server (stdlib HTTP) + client roundtrip (stub) — `scripts/spike_sidecar.py`
- [ ] wire real models: GeoCalib, Depth Anything V2-Small, OpenCLIP, MUSIQ/NIMA, MegaSaM/RAFT, CMA-ES

## UI / install — source complete
- [~] PySide6 dock (brief, storyboard/plan tree, gaps, critic, apply, render queue; worker thread)
- [~] bootstrap (deps check) + startup macro · data packs (cinematic + vray7)

## Spikes to run on your box → Checkpoint 0
- [ ] T2 `python scripts/spike_provider_ping.py <oc_key>`  (opus-4.8 + gpt-5.5)
- [ ] T3 `3dsmaxbatch ... run_spike_create.ms`             (VRay camera+sun read-back → SMOKE_OK)
- [ ] T4 `python scripts/spike_vantage_cli.py <scene.vantage>`  (5-frame Vantage batch)
- [x] T5 `python scripts/spike_sidecar.py`                 (sidecar roundtrip — GO)

## Then
- [ ] Checkpoint 1: live MVP smoke in Max on a real Sthyra scene (direct→apply→V-Ray render)
- [ ] P2–P5 live verification per phase
