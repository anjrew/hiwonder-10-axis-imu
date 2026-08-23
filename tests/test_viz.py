import itertools

from hiwonder_imu.viz import WEB_DIR, demo_source


def test_page_is_packaged():
    html = (WEB_DIR / "index.html").read_text()
    assert "<canvas" in html
    assert "/stream" in html


def test_demo_source_shape():
    for sample in itertools.islice(demo_source(), 3):
        assert sample["demo"] is True
        assert len(sample["angle"]) == 3
        assert len(sample["accel"]) == 3
        assert len(sample["gyro"]) == 3
        roll, pitch, yaw = sample["angle"]
        assert -90 <= roll <= 90
        assert -90 <= pitch <= 90
        assert -180 <= yaw <= 180


def test_page_reads_quaternion_w_first():
    html = (WEB_DIR / "index.html").read_text()
    assert "const [qw, qx, qy, qz] = s.quaternion" in html
    assert "targetQ = [qx, qy, qz, qw]" in html


def test_page_eases_between_readings():
    html = (WEB_DIR / "index.html").read_text()
    assert "function slerp(" in html
    assert "SMOOTH_TAU" in html


def test_view_is_not_mirrored():
    """The eye is at +y, so world +x must project to the viewer's left.

    With the sign the other way the whole picture is a mirror image and every
    rotation appears to turn the wrong way.
    """
    html = (WEB_DIR / "index.html").read_text()
    assert "return [w / 2 - p[0] * f, h / 2 - p[2] * f, depth];" in html
    assert "const depth = cam - p[1];" in html
