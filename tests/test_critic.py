from maxdirector.core.critic import critique_shot, has_blockers
from maxdirector.core.models import CameraState, ResolvedShot, Severity


def _shot(states):
    return ResolvedShot(id="s1", camera_name="MD_Cam_01", states=states)


def test_camera_in_void_blocks(living_room):
    cam = CameraState(pos=(0.0, -500.0, 1.5), look_at=(0.0, 0.0, 0.4), fov_mm=35.0)
    findings = critique_shot(_shot([(0.0, cam)]), living_room)
    assert has_blockers(findings)
    assert any(f.code == "camera_in_void" for f in findings)


def test_camera_inside_solid_blocks(living_room):
    # inside the north wall bbox (-4..4, 3..3.2, 0..3)
    cam = CameraState(pos=(0.0, 3.1, 1.5), look_at=(0.0, 0.0, 0.4), fov_mm=35.0)
    findings = critique_shot(_shot([(0.0, cam)]), living_room)
    assert any(f.code == "camera_inside_solid" for f in findings)


def test_degenerate_lookat_blocks(living_room):
    cam = CameraState(pos=(0.0, -2.0, 1.5), look_at=(0.0, -2.0, 1.5), fov_mm=35.0)
    findings = critique_shot(_shot([(0.0, cam)]), living_room)
    assert any(f.code == "degenerate_lookat" for f in findings)


def test_subject_out_of_frame_warns(living_room):
    # camera looking away from the subject at origin
    cam = CameraState(pos=(0.0, -3.0, 1.5), look_at=(0.0, -10.0, 1.5), fov_mm=50.0)
    findings = critique_shot(_shot([(0.0, cam)]), living_room, subject_center=(0.0, 0.0, 0.4))
    assert any(f.code == "subject_out_of_frame" for f in findings)


def test_good_shot_is_clean(living_room):
    cam = CameraState(pos=(0.0, -3.0, 1.5), look_at=(0.0, 0.0, 0.4), fov_mm=35.0)
    findings = critique_shot(_shot([(0.0, cam)]), living_room, subject_center=(0.0, 0.0, 0.4))
    assert not has_blockers(findings)
    assert not any(f.code == "subject_out_of_frame" for f in findings)
