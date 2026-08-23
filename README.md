# hiwonder-10-axis-imu

Read a Hiwonder 10-axis IMU (accelerometer, gyroscope, magnetometer, barometer)
over USB serial from a Mac, with Python.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

hiwonder-imu --list-ports        # find the device
hiwonder-imu                     # live roll/pitch/yaw, accel, gyro
hiwonder-imu --raw -n 20         # 20 decoded frames, one line each
```

On macOS you may need a USB-serial driver for the adapter on the board
(CP210x, CH340 or FTDI). Once installed the device shows up as something like
`/dev/cu.usbserial-0001`.

## In your own code

```python
from hiwonder_imu import ImuReader

with ImuReader() as imu:          # or ImuReader("/dev/cu.usbserial-0001")
    for sample in imu.samples():
        print(sample.angle)       # (roll, pitch, yaw) in degrees
```

`ImuSample` fields:

| field | unit |
| --- | --- |
| `accel` | m/s² |
| `gyro` | deg/s |
| `angle` | degrees (roll, pitch, yaw) |
| `mag` | raw counts |
| `quaternion` | unitless (x, y, z, w) |
| `temperature` | °C |

Any field the board isn't currently sending stays `None`.

More in [`examples/`](examples/): [`print_angles.py`](examples/print_angles.py)
and [`log_to_csv.py`](examples/log_to_csv.py).

## Wire format

The board streams fixed 11-byte frames:

```
0x55  <type>  d0 d1  d2 d3  d4 d5  d6 d7  <checksum>
```

Four little-endian signed 16-bit values per frame; the checksum is the low byte
of the sum of the first ten bytes. Frame types are `0x51` accel, `0x52` gyro,
`0x53` angle, `0x54` magnetometer, `0x56` pressure, `0x59` quaternion. The
parser drops bad bytes one at a time, so it recovers on its own if you plug in
mid-stream.

**Check this against your datasheet.** The frame layout and the scale factors
(±16 g, ±2000 deg/s, ±180°) are the common Hiwonder/WitMotion defaults, but
your board's configuration may differ. If numbers look wrong by a constant
factor, that's where to look — `hiwonder_imu/protocol.py`.

Default baud rate is 9600; pass `-b 115200` if yours is configured faster.

## Tests

```bash
pytest
```

The parser tests build synthetic frames, so they run without hardware.

## License

MIT
