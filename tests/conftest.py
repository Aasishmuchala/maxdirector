"""Shared fixtures — a tiny synthetic scene digest used across the pure tests."""

import pytest

from maxdirector.core.models import BBox, Category, CameraInfo, Digest, NodeInfo, UpAxis


@pytest.fixture
def living_room() -> Digest:
    sofa = NodeInfo(handle=1, name="sofa_grp", klass="Editable_Poly",
                    category=Category.GEOMETRY, bbox=BBox((-1.0, -0.5, 0.0), (1.0, 0.5, 0.8)))
    table = NodeInfo(handle=2, name="coffee_table", klass="Editable_Poly",
                     category=Category.GEOMETRY, bbox=BBox((-0.6, 1.0, 0.0), (0.6, 1.8, 0.4)))
    wall = NodeInfo(handle=3, name="wall_north", klass="Editable_Poly",
                    category=Category.GEOMETRY, bbox=BBox((-4.0, 3.0, 0.0), (4.0, 3.2, 3.0)))
    rig = NodeInfo(handle=4, name="character_01", klass="Editable_Poly",
                   category=Category.GEOMETRY, bbox=BBox((2.0, 2.0, 0.0), (2.6, 2.4, 1.8)),
                   is_skinned=True)
    door = NodeInfo(handle=5, name="door_01", klass="Editable_Poly",
                    category=Category.GEOMETRY, bbox=BBox((3.0, 3.0, 0.0), (3.9, 3.1, 2.1)))
    return Digest(
        units="meters", up_axis=UpAxis.Z,
        scene_bounds=BBox((-4.0, -1.0, 0.0), (4.0, 3.2, 3.0)),
        renderer="V_Ray_6_Hotfix", is_vray=True, frame_rate=24.0,
        nodes=[sofa, table, wall, rig, door],
        cameras=[], lights=[], suns=[], environment_map=None, gamma=2.2,
    )
