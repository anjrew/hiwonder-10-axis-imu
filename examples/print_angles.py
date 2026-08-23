"""Print roll/pitch/yaw as fast as the IMU sends it."""

from hiwonder_imu import ImuReader

with ImuReader() as imu:  # pass port="/dev/cu.usbserial-0001" to pick one
    for sample in imu.samples():
        if sample.angle:
            roll, pitch, yaw = sample.angle
            print(f"roll {roll:7.2f}  pitch {pitch:7.2f}  yaw {yaw:7.2f}")
