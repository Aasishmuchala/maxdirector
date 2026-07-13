"""Prove the multimodal assembly works: scout thumbnails become image content blocks that go
to the model. (A 1x1 PNG stands in for a real scout render.)"""

import base64
from dataclasses import replace

from maxdirector.core import director
from maxdirector.core.scout import scout_poses

# smallest valid 1x1 PNG
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def test_scout_thumbnails_become_image_blocks(living_room, tmp_path):
    p = tmp_path / "scout0.png"
    p.write_bytes(_PNG)
    scouts = scout_poses(living_room.scene_bounds)
    scouts[0].thumb_path = str(p)               # only scout 0 has a rendered thumbnail
    digest = replace(living_room, scouts=scouts)

    content = director._user_content("design shots", digest)
    kinds = [b.get("type") for b in content]
    assert kinds[0] == "text"                   # the instruction
    assert "image" in kinds                     # at least one scout image attached
    img = next(b for b in content if b.get("type") == "image")
    assert img["source"]["media_type"] == "image/png"
    assert img["source"]["data"]                # base64 payload present


def test_no_thumbnails_degrades_to_text_only(living_room):
    content = director._user_content("design shots", living_room)  # no scouts
    assert [b.get("type") for b in content] == ["text"]


def test_scout_legend_lists_ids(living_room):
    from dataclasses import replace as _r
    digest = _r(living_room, scouts=scout_poses(living_room.scene_bounds))
    legend = director._scout_legend(digest)
    assert "id=0" in legend and "plan" in legend
