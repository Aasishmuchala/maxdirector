# MaxDirector — Specification (v2)

**Owner:** Aasish Muchala · **Type:** internal Sthyra pipeline tool (not sold) ·
**Target:** 3ds Max 2026 (Py 3.11, PySide6) + V-Ray 7 + Chaos Vantage 3.x · **Reliability
goal:** ~95% on real scenes, human-approved.

## 1. Summary
A native plugin that reads the entire open project and, driven by an LLM through the Omega
gateway and grounded by a local CV layer, proposes and (on approval) builds the cameras,
animation, lighting, and render setup as a cinematic multi-shot sequence; matches a reference
image/video; fills missing skies/assets; and renders via V-Ray or a Vantage shot-by-shot batch.

## 2. Locked decisions
| Decision | Choice |
|---|---|
| Trust model | propose → preview → **approve** → apply (3 gates: storyboard, assets, plan) |
| Camera schema | **semantic anchors** resolved by the bridge from real geometry — never world coords |
| Quality gate | deterministic **geometric critic** + **best-of-N** scoring (composition + CV) |
| LLM wire | Omega `/v1/messages` (opus-4.8) or `/v1/chat/completions` (gpt-5.5); **no tools** (schema-in-prompt) |
| CV stack | **commercial-safe default** (GeoCalib, Depth Anything V2-Small, MegaSaM-swapped, MUSIQ); NC toggle for non-paid |
| Object animation | additive keys on **guard-safe** nodes only; rigs refused unless opted in |
| Render | V-Ray sequence OR **Vantage** `vantage_console` sequential batch |
| Safety | backup-first · one undo/plan · read-back verify · `MD_` namespace · additive-only |
| Packaging | startup-script install on the owner's machine (no distribution/licensing) |

## 3. Architecture
Hexagon: `core/` (pure, pymxs-free, test-enforced) ↔ `maxbridge/` (only pymxs) ↔ `ui/`
(PySide6). CV models run in a separate `cv_sidecar` process (torch+CUDA), never Max's Python;
the plugin talks to it over localhost and degrades to LLM-only "guided" mode if it's absent.

## 4. The pipeline
UNDERSTAND → BRIEF → (REFERENCE gate) → DIRECT (LLM #1, storyboard) → RESOLVE GAPS → COMPILE
(LLM #2, anchor plan) → GROUND+CRITIC+best-of-N → PREVIEW → APPLY → RENDER. Two LLM calls
(creative vs technical) give better output, natural approval gates, and cheap per-shot re-rolls.

## 5. Data model (see `core/models.py`)
`Digest` (scene), `Brief`, `Storyboard`/`StoryboardShot`/`AssetGap`, `AuthoringPlan`/`PlanShot`
/`Anchor`/`PathSpec`/`Keyframe`/`LightOp`/`EnvSpec`/`AnimOp`/`RenderSpec`, `ResolvedShot`/
`CameraState`, `CriticFinding`, `ScoreResult`, `ApplyResult`. All JSON-round-trippable across
the LLM and sidecar boundaries.

## 6. Reliability model (why ~95%)
Reliability tracks determinism. Deterministic (digest, anchor→transform, keyframing, apply/
verify, render, critic) → ~95%. Bounded LLM choices (which shot/move) → ~90%. Ill-posed 2D→3D
(reference placement, video move) → made ~85–90% by **analysis-by-synthesis**: we own the scene,
so we render candidate views and optimize against a score (GeoCalib transferable attributes +
CMA-ES render-and-compare + best-of-N), rather than asking the LLM to eyeball 3D. Subjective
taste caps ~90% even for a human DP → covered by best-of-N + the approval gate.

## 7. Feature reliability (target)
| Feature | Target | Basis |
|---|---|---|
| Understand / camera moves / apply-verify / V-Ray render | 95% | deterministic |
| Storyboard structure | 90% | bounded LLM |
| Sky research + auto-apply | 95% | Poly Haven API + deterministic dome |
| Reference lighting (LightMatch) | 90% | shipped engine |
| Reference-image compositional match | ~90% | GeoCalib + render-and-compare + nudge |
| Vantage batch | ~85% | verified CLI, spike-gated |
| Video move (technique transfer) | ~85% | MegaSaM/RAFT normalized retarget |
| Guarded object animation | 90% | additive keys + guard catalog |

## 8. Non-goals
Selling/distribution, license server, multi-version matrix, exact pose reconstruction from a
different room, literal video-trajectory copy, auto-placing net-new Cosmos furniture, closing
the subjective-taste gap without a human.

## 9. Success criteria
- P0 spikes pass (model routing, headless create, Vantage CLI, sidecar) → Checkpoint 0.
- Live MVP: a brief yields keyframed, critic-clean, read-back-verified cameras + a V-Ray
  sequence on a real Sthyra scene → Checkpoint 1.
- Both render backends deliver; reference-image match lands a matched, well-lit camera; the
  similarity gate rejects an unrelated reference.
