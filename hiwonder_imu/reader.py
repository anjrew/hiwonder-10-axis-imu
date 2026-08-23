"""Serial reader for the Hiwonder 10-axis IMU."""

from __future__ import annotations

import glob
from dataclasses import dataclass, field
from typing import Iterator

import serial

from .protocol import Frame, FrameType, parse_stream

DEFAULT_BAUDRATE = 9600


def find_ports() -> list[str]:
    """USB-serial devices as macOS names them (CP210x, CH340, FTDI adapters)."""
    ports: list[str] = []
    for pattern in ("/dev/cu.usbserial*", "/dev/cu.usbmodem*", "/dev/cu.SLAB_USBtoUART*", "/dev/cu.wchusbserial*"):
        ports.extend(sorted(glob.glob(pattern)))
    return ports


@dataclass
class ImuSample:
    """The latest value of every field, refreshed as frames arrive."""

    accel: tuple[float, float, float] | None = None      # m/s^2
    gyro: tuple[float, float, float] | None = None       # deg/s
    angle: tuple[float, float, float] | None = None      # roll, pitch, yaw in degrees
    mag: tuple[float, float, float] | None = None        # raw counts
    quaternion: tuple[float, float, float, float] | None = None
    temperature: float | None = None                     # degrees C
    seen: set[int] = field(default_factory=set)

    def update(self, frame: Frame) -> None:
        x, y, z, w = frame.values
        self.seen.add(frame.type)
        if frame.type == FrameType.ACCEL:
            self.accel, self.temperature = (x, y, z), w
        elif frame.type == FrameType.GYRO:
            self.gyro, self.temperature = (x, y, z), w
        elif frame.type == FrameType.ANGLE:
            self.angle, self.temperature = (x, y, z), w
        elif frame.type == FrameType.MAG:
            self.mag, self.temperature = (x, y, z), w
        elif frame.type == FrameType.QUATERNION:
            self.quaternion = (x, y, z, w)


class ImuReader:
    """Open the serial port and hand back frames or grouped samples.

    Usage:
        with ImuReader("/dev/cu.usbserial-0001") as imu:
            for sample in imu.samples():
                print(sample.angle)
    """

    def __init__(self, port: str | None = None, baudrate: int = DEFAULT_BAUDRATE, timeout: float = 1.0):
        if port is None:
            found = find_ports()
            if not found:
                raise RuntimeError("no USB serial device found - is the IMU plugged in?")
            port = found[0]
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._serial: serial.Serial | None = None

    def __enter__(self) -> "ImuReader":
        self.open()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def open(self) -> None:
        self._serial = serial.Serial(self.port, self.baudrate, timeout=self.timeout)

    def close(self) -> None:
        if self._serial is not None:
            self._serial.close()
            self._serial = None

    def _chunks(self):
        assert self._serial is not None, "call open() first"
        while True:
            waiting = self._serial.in_waiting or 1
            data = self._serial.read(waiting)
            if data:
                yield data

    def frames(self) -> Iterator[Frame]:
        """Every valid frame, one at a time."""
        yield from parse_stream(self._chunks())

    def samples(self) -> Iterator[ImuSample]:
        """One sample per full round of frame types, so fields line up in time."""
        sample = ImuSample()
        for frame in self.frames():
            if frame.type in sample.seen:
                yield sample
                sample = ImuSample()
            sample.update(frame)
