import struct

import pytest

from hiwonder_imu.protocol import FrameType, checksum_ok, decode, parse_stream


def build(kind: int, a: int, b: int, c: int, d: int) -> bytes:
    body = bytes([0x55, kind]) + struct.pack("<hhhh", a, b, c, d)
    return body + bytes([sum(body) & 0xFF])


def test_checksum_roundtrip():
    assert checksum_ok(build(FrameType.ANGLE, 1, 2, 3, 4))


def test_bad_checksum_rejected():
    frame = bytearray(build(FrameType.ANGLE, 1, 2, 3, 4))
    frame[-1] ^= 0xFF
    assert not checksum_ok(bytes(frame))


def test_angle_scaling():
    frame = decode(build(FrameType.ANGLE, 32768 // 2, 0, -32768, 2500))
    roll, pitch, yaw, temp = frame.values
    assert roll == pytest.approx(90.0)
    assert yaw == pytest.approx(-180.0)
    assert temp == pytest.approx(25.0)
    assert frame.name == "ANGLE"


def test_accel_scaling_one_g():
    frame = decode(build(FrameType.ACCEL, 32768 // 16, 0, 0, 0))
    assert frame.values[0] == pytest.approx(9.80665, rel=1e-4)


def test_parse_stream_resyncs_after_garbage():
    good = build(FrameType.GYRO, 10, 20, 30, 0)
    stream = [b"\x00\x55\xff", good, b"\x55", good]
    frames = list(parse_stream(stream))
    assert len(frames) == 2
    assert all(f.type == FrameType.GYRO for f in frames)


def test_parse_stream_handles_split_frames():
    good = build(FrameType.QUATERNION, 32767, 0, 0, 0)
    frames = list(parse_stream([good[:4], good[4:]]))
    assert len(frames) == 1
    assert frames[0].values[0] == pytest.approx(1.0, abs=1e-4)


def test_wrong_length_raises():
    with pytest.raises(ValueError):
        decode(b"\x55\x53")
