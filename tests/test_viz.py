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
