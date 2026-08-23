"""Change the board's own settings: output rate and serial speed.

These writes are persistent - the board keeps them across a power cycle - so
you normally run this once after unboxing and never think about it again.

Out of the box the board ships at 9600 baud, which is the real bottleneck: it
sends seven 11-byte frames per update, so 9600 baud caps it near 12 updates a
second no matter what the output rate is set to. At 115200 it reaches ~90 Hz.
"""

from __future__ import annotations

import collections
import time

import serial

UNLOCK = bytes([0xFF, 0xAA, 0x69, 0x88, 0xB5])
SAVE = bytes([0xFF, 0xAA, 0x00, 0x00, 0x00])

REG_RATE = 0x03
REG_BAUD = 0x04

# board's code for each serial speed
BAUD_CODES = {4800: 1, 9600: 2, 19200: 3, 38400: 4, 57600: 5, 115200: 6, 230400: 7}

# board's code for each output rate in Hz
RATE_CODES = {1: 0x03, 2: 0x04, 5: 0x05, 10: 0x06, 20: 0x07, 50: 0x08, 100: 0x09, 200: 0x0B}

FRAME_BITS = 7 * 11 * 10  # seven frame types, 11 bytes each, 10 bits per byte


def _write_reg(port: serial.Serial, reg: int, value: int) -> None:
    port.write(UNLOCK)
    port.flush()
    time.sleep(0.2)
    port.write(bytes([0xFF, 0xAA, reg, value & 0xFF, (value >> 8) & 0xFF]))
    port.flush()
    time.sleep(0.2)


def _save(port: serial.Serial) -> None:
    port.write(UNLOCK)
    port.flush()
    time.sleep(0.2)
    port.write(SAVE)
    port.flush()
    time.sleep(0.5)


def frame_rate(device: str, baudrate: int, seconds: float = 1.5) -> float:
    """Valid frames per second seen at this speed. Zero means wrong speed."""
    try:
        port = serial.Serial(device, baudrate, timeout=0.4)
    except Exception:
        return 0.0
    try:
        port.reset_input_buffer()
        buf = bytearray()
        start = time.monotonic()
        while time.monotonic() - start < seconds:
            buf.extend(port.read(max(1, port.in_waiting)))
        elapsed = time.monotonic() - start
    finally:
        port.close()

    count = 0
    i = 0
    while i <= len(buf) - 11:
        if buf[i] == 0x55 and sum(buf[i : i + 10]) & 0xFF == buf[i + 10]:
            count += 1
            i += 11
        else:
            i += 1
    return count / elapsed if elapsed else 0.0


def find_baudrate(device: str, candidates=None) -> int | None:
    """Work out what speed the board is currently talking at."""
    for baud in candidates or sorted(BAUD_CODES, reverse=True):
        if frame_rate(device, baud) > 20:
            return baud
    return None


def configure(device: str, baudrate: int = 115200, rate_hz: int = 100, current: int | None = None) -> dict:
    """Set the board's output rate and serial speed. Returns what happened."""
    if baudrate not in BAUD_CODES:
        raise ValueError(f"baud rate must be one of {sorted(BAUD_CODES)}")
    if rate_hz not in RATE_CODES:
        raise ValueError(f"output rate must be one of {sorted(RATE_CODES)} Hz")

    ceiling = baudrate / FRAME_BITS
    if rate_hz > ceiling:
        raise ValueError(
            f"{rate_hz} Hz needs {rate_hz * FRAME_BITS / 1000:.0f} kbit/s but {baudrate} baud "
            f"only carries about {ceiling:.0f} updates a second - raise the baud rate first"
        )

    if current is None:
        current = find_baudrate(device)
        if current is None:
            raise RuntimeError(f"no board found on {device} at any standard speed")

    before = frame_rate(device, current)

    port = serial.Serial(device, current, timeout=0.5)
    try:
        _write_reg(port, REG_RATE, RATE_CODES[rate_hz])
        _save(port)
        # the board switches speed the instant it accepts this, so nothing
        # afterwards can be sent at the old rate
        _write_reg(port, REG_BAUD, BAUD_CODES[baudrate])
    finally:
        port.close()
    time.sleep(0.5)

    # re-open at the new speed to make the change permanent
    try:
        port = serial.Serial(device, baudrate, timeout=0.5)
        try:
            _save(port)
        finally:
            port.close()
    except Exception:
        pass

    found = find_baudrate(device)
    return {
        "device": device,
        "was": current,
        "requested": baudrate,
        "found_at": found,
        "rate_before": before,
        "rate_after": frame_rate(device, found) if found else 0.0,
        "ok": found == baudrate,
    }
