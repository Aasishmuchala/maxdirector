"""P0-T3 SPIKE — headless V-Ray create/read-back. Prove MaxDirector can create a
VRayPhysicalCamera + VRaySun and read them back, in a 3dsmaxbatch session on Max 2026.

Run:  "C:\\Program Files\\Autodesk\\3ds Max 2026\\3dsmaxbatch.exe" -mxs "python.ExecuteFile \"<repo>\\scripts\\spike_headless_create.py\""
  (or use scripts/run_spike_create.ms). Prints SMOKE_OK on success; document V-Ray's batch
  license behaviour from the console output.
"""

from pymxs import runtime as rt  # type: ignore


def main():
    # ensure V-Ray is the renderer (name-agnostic: just try to make the objects)
    cam = getattr(rt, "VRayPhysicalCamera", None) or getattr(rt, "Physical", None)
    sun = getattr(rt, "VRaySun", None)
    assert cam is not None, "no VRayPhysicalCamera/Physical ctor — is V-Ray loaded?"
    assert sun is not None, "no VRaySun ctor — is V-Ray loaded?"
    c = cam(); c.name = "MD_SpikeCam"
    s = sun(); s.name = "MD_SpikeSun"
    # keyframe two positions to prove animation works headless
    import pymxs
    with pymxs.animate(True):
        with pymxs.attime(0):
            c.pos = rt.Point3(0, -300, 150)
        with pymxs.attime(48):
            c.pos = rt.Point3(200, -200, 150)
    assert rt.getNodeByName("MD_SpikeCam") is not None, "camera not found on read-back"
    assert rt.getNodeByName("MD_SpikeSun") is not None, "sun not found on read-back"
    nkeys = int(rt.numKeys(rt.getNodeByName("MD_SpikeCam").position.controller))
    assert nkeys >= 2, f"expected >=2 position keys, got {nkeys}"
    print(f"SMOKE_OK  camera+sun created, {nkeys} keys read back")


main()
