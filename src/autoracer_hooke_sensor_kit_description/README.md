# autoracer_hooke_sensor_kit_description

Status: `pending`.

This directory reserves the official Autoware sensor-kit description package
name for the target Hooke platform. It is not runtime ready and is intentionally
kept out of colcon discovery with `COLCON_IGNORE`.

Remove COLCON_IGNORE only after this directory contains real Hooke sensor
extrinsics and Autoware sensor-kit description files:

- `sensor_kit_calibration.yaml`
- `sensors_calibration.yaml`
- `sensor_kit.xacro`
- `sensors.xacro`

The final package must expose the `autoracer_hooke_sensor_kit` sensor model and
stay paired with `autoracer_hooke`.

Do not reuse RC C32/Hipnuc extrinsics. The handoff requires real Hooke sensor
extrinsics for the Hooke LiDAR, Fixposition/GNSS/INS/IMU, and any additional
sensor frames.
