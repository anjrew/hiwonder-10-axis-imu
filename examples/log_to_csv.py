"""Log samples to a CSV file until you hit ctrl-c."""

import csv
import sys
import time

from hiwonder_imu import ImuReader

path = sys.argv[1] if len(sys.argv) > 1 else "imu_log.csv"

with open(path, "w", newline="") as handle, ImuReader() as imu:
    writer = csv.writer(handle)
    writer.writerow(
        ["t", "ax", "ay", "az", "gx", "gy", "gz", "roll", "pitch", "yaw", "temp"]
    )
    start = time.monotonic()
    try:
        for sample in imu.samples():
            if not (sample.accel and sample.gyro and sample.angle):
                continue
            writer.writerow(
                [f"{time.monotonic() - start:.4f}", *sample.accel, *sample.gyro,
                 *sample.angle, sample.temperature]
            )
    except KeyboardInterrupt:
        print(f"\nwrote {path}")
