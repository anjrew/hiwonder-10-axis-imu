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


def test_pressure_frame_is_two_int32s():
    # captured from the board on a bench at roughly sea level
    frame = bytes.fromhex("5556f88b0100a3feffffce")
    assert checksum_ok(frame)
    pressure, altitude, _, _ = decode(frame).values
    assert pressure == pytest.approx(101368.0)
    assert altitude == pytest.approx(-3.49)


def test_quaternion_is_w_first():
    # captured at the same moment as roll -10.99, pitch 0.36, yaw -176.19
    w, x, y, z = decode(bytes.fromhex("5559d0fbffffbaf3567ff9")).values
    assert w == pytest.approx(-0.0327, abs=1e-3)   # w is small near 180 deg yaw
    assert z == pytest.approx(0.9948, abs=1e-3)    # z is large
    assert abs(w) < abs(z)


def test_configure_refuses_rates_the_link_cannot_carry():
    from hiwonder_imu.configure import configure

    with pytest.raises(ValueError, match="raise the baud rate first"):
        configure("/dev/null", baudrate=9600, rate_hz=100)
    with pytest.raises(ValueError, match="baud rate must be one of"):
        configure("/dev/null", baudrate=12345)


def test_frame_bits_matches_the_wire_format():
    from hiwonder_imu.configure import FRAME_BITS
    from hiwonder_imu.protocol import FRAME_LEN, FrameType

    # seven frame types, each FRAME_LEN bytes, 10 bits on the wire per byte
    assert FRAME_BITS == len(FrameType) * FRAME_LEN * 10
