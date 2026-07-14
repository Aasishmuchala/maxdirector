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
    # subject in FRONT of the camera but well off the optical axis (narrow lens)
    cam = CameraState(pos=(0.0, -3.0, 1.5), look_at=(6.0, 2.0, 1.5), fov_mm=50.0)
    findings = critique_shot(_shot([(0.0, cam)]), living_room, subject_center=(0.0, 0.0, 0.4))
    assert any(f.code == "subject_out_of_frame" for f in findings)


def test_subject_behind_camera_blocks(living_room):
    # camera pointed away from the subject at origin → subject is behind the lens
    cam = CameraState(pos=(0.0, -3.0, 1.5), look_at=(0.0, -10.0, 1.5), fov_mm=50.0)
    findings = critique_shot(_shot([(0.0, cam)]), living_room, subject_center=(0.0, 0.0, 0.4))
    assert has_blockers(findings)
    assert any(f.code == "subject_behind_camera" for f in findings)


def test_subject_too_small_warns(living_room):
    # sofa (~2.4m) framed from 40m on a wide lens → a speck
    cam = CameraState(pos=(0.0, -40.0, 1.5), look_at=(0.0, 0.0, 0.4), fov_mm=20.0)
    findings = critique_shot(_shot([(0.0, cam)]), living_room, subject_center=(0.0, 0.0, 0.4))
    assert any(f.code == "subject_too_small" for f in findings)


def test_subject_too_close_warns(living_room):
    # sofa framed from 0.3m → overflows the frame
    cam = CameraState(pos=(0.0, -0.3, 0.4), look_at=(0.0, 0.0, 0.4), fov_mm=35.0)
    findings = critique_shot(_shot([(0.0, cam)]), living_room, subject_center=(0.0, 0.0, 0.4))
    assert any(f.code == "subject_too_close" for f in findings)


def test_good_shot_is_clean(living_room):
    cam = CameraState(pos=(0.0, -3.0, 1.5), look_at=(0.0, 0.0, 0.4), fov_mm=35.0)
    findings = critique_shot(_shot([(0.0, cam)]), living_room, subject_center=(0.0, 0.0, 0.4))
    assert not has_blockers(findings)
    assert not any(f.code == "subject_out_of_frame" for f in findings)
