"""THE experiment that settles the core bet: can the LLM place cinematographically-good
cameras when it SEES the scene? Runs OFF Max — no 3ds Max, no GPU needed. You just need your
oc_ key and a handful of rendered views of a real scene (or even phone photos of a room).

    python scripts/experiment_placement.py --images ./views --key oc_xxx \
        --prompt "cinematic golden-hour 3-shot reveal of the living room"

It builds a digest whose scouts point at your images (ids in filename order), runs the real
multimodal DIRECT then COMPILE against the gateway, and prints what the model chose: which
scout each shot starts from, the move, the framing, and the scout_anchor nudges. Read it and
judge — did it pick sensible vantages and moves for THOSE images? That answer decides whether
the whole approach is worth the rest of the build. (Placeholder poses; we're validating the
DIRECTORIAL choices here, not the metric resolve.)
"""

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from maxdirector.core import director  # noqa: E402
from maxdirector.core.models import BBox, Brief, Category, Digest, NodeInfo, UpAxis  # noqa: E402
from maxdirector.core.scout import scout_poses  # noqa: E402


def _find_images(image_dir: str):
    seen, imgs = set(), []
    for ext in ("png", "jpg", "jpeg", "webp", "PNG", "JPG", "JPEG"):
        for p in glob.glob(os.path.join(image_dir, f"*.{ext}")):
            if p.lower() not in seen:
                seen.add(p.lower())
                imgs.append(p)
    return sorted(imgs)


def _digest_from_images(image_dir: str) -> Digest:
    imgs = _find_images(image_dir)
    if not imgs:
        raise SystemExit(f"no images (png/jpg/jpeg/webp) found in {image_dir}")
    bounds = BBox((-4.0, -3.0, 0.0), (4.0, 3.0, 3.0))          # placeholder room for scout poses
    d = Digest(units="meters", up_axis=UpAxis.Z, scene_bounds=bounds, renderer="V-Ray", is_vray=True,
               nodes=[NodeInfo(handle=1, name="scene", klass="mesh", category=Category.GEOMETRY, bbox=bounds)])
    # generate exactly as many scout poses as we have images (never truncate / never leave blanks)
    from maxdirector.core.models import CameraState, ScoutView
    base = scout_poses(bounds)
    scouts = []
    for i, path in enumerate(imgs):
        pose = base[i].pose if i < len(base) else base[-1].pose
        sv = ScoutView(id=i, label=os.path.splitext(os.path.basename(path))[0], pose=pose, thumb_path=path)
        scouts.append(sv)
    d.scouts = scouts
    print("loaded scout images:")
    for sv in scouts:
        print(f"  id={sv.id}  {os.path.basename(sv.thumb_path)}")
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True, help="folder of scene view thumbnails (ids in name order)")
    ap.add_argument("--key", default=os.environ.get("OC_KEY", ""), help="oc_ gateway key")
    ap.add_argument("--prompt", default="a cinematic 3-shot reveal of this space")
    ap.add_argument("--model", default="claude-opus-4-8")
    args = ap.parse_args()
    if not args.key:
        raise SystemExit("no key — pass --key or set OC_KEY")

    digest = _digest_from_images(args.images)
    print(f"scouts: {[f'{s.id}:{s.label}' for s in digest.scouts]}\n")

    brief = Brief(prompt=args.prompt)
    print("=== DIRECT (multimodal storyboard) ===")
    sb, notes, raw = director.direct(args.key, digest, brief, model=args.model)
    for n in notes:
        print("note:", n)
    if sb is None:
        print("no storyboard.\nraw:", raw[:600]); return 1
    for s in sb.shots:
        print(f"  [{s.id}] scout={s.from_scout} move={s.camera_move.value:12} :: {s.intent}  | framing: {s.framing}")

    print("\n=== COMPILE (vision-first authoring plan) ===")
    plan, errors, raw2 = director.compile_plan(args.key, digest, sb, model=args.model)
    for e in errors:
        print("issue:", e)
    if plan is None:
        print("no plan.\nraw:", raw2[:600]); return 1
    for sh in plan.shots:
        sa = sh.scout_anchor
        where = (f"scout {sa.from_scout} +dolly{sa.dolly_m} +truck{sa.truck_m} +ped{sa.pedestal_m}"
                 if sa else f"object {sh.anchor.relative_to if sh.anchor else '?'}")
        print(f"  [{sh.id}] {sh.camera.name} {sh.camera.fov_mm}mm  path={sh.path.kind}  <- {where}")
    print("\nRead the choices above: sensible vantages + moves for these images? That's the bet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
