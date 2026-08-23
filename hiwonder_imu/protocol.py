"""Packet parsing for the Hiwonder 10-axis IMU.

The board streams fixed 11-byte frames (WitMotion-style):

    0x55  <type>  d0 d1  d2 d3  d4 d5  d6 d7  <checksum>

Each frame carries four little-endian signed 16-bit values. The checksum is
the low byte of the sum of the first 10 bytes.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import Iterator

HEADER = 0x55
FRAME_LEN = 11

GRAVITY = 9.80665


class FrameType(IntEnum):
    TIME = 0x50
    ACCEL = 0x51
    GYRO = 0x52
    ANGLE = 0x53
    MAG = 0x54
    PRESSURE = 0x56
    QUATERNION = 0x59


@dataclass(frozen=True)
class Frame:
    """One decoded 11-byte frame."""

    type: int
    values: tuple[float, float, float, float]
    raw: bytes

    @property
    def name(self) -> str:
        try:
            return FrameType(self.type).name
        except ValueError:
            return f"UNKNOWN_0x{self.type:02X}"


def checksum_ok(frame: bytes) -> bool:
    return sum(frame[:10]) & 0xFF == frame[10]


def decode(frame: bytes) -> Frame:
    """Decode one 11-byte frame into engineering units."""
    if len(frame) != FRAME_LEN:
        raise ValueError(f"expected {FRAME_LEN} bytes, got {len(frame)}")
    kind = frame[1]
    a, b, c, d = struct.unpack("<hhhh", frame[2:10])

    if kind == FrameType.ACCEL:
        scale = 16.0 / 32768.0 * GRAVITY  # m/s^2
        values = (a * scale, b * scale, c * scale, d / 100.0)  # 4th = temperature
    elif kind == FrameType.GYRO:
        scale = 2000.0 / 32768.0  # deg/s
        values = (a * scale, b * scale, c * scale, d / 100.0)
    elif kind == FrameType.ANGLE:
        scale = 180.0 / 32768.0  # degrees
        values = (a * scale, b * scale, c * scale, d / 100.0)
    elif kind == FrameType.MAG:
        values = (float(a), float(b), float(c), d / 100.0)  # raw counts
    elif kind == FrameType.QUATERNION:
        scale = 1.0 / 32768.0
        values = (a * scale, b * scale, c * scale, d * scale)
    else:
        values = (float(a), float(b), float(c), float(d))

    return Frame(type=kind, values=values, raw=bytes(frame))


def parse_stream(chunks) -> Iterator[Frame]:
    """Turn an iterable of byte chunks into a stream of valid frames.

    Resynchronises on its own: bytes that don't start a checksum-valid frame
    are dropped one at a time until the stream lines up again.
    """
    buf = bytearray()
    for chunk in chunks:
        buf.extend(chunk)
        while len(buf) >= FRAME_LEN:
            if buf[0] != HEADER:
                del buf[0]
                continue
            frame = bytes(buf[:FRAME_LEN])
            if not checksum_ok(frame):
                del buf[0]
                continue
            del buf[:FRAME_LEN]
            yield decode(frame)
