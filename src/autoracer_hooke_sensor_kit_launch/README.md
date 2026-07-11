# autoracer_hooke_sensor_kit_launch

Status: `pending`.

This directory reserves the official Autoware sensor-kit launch package name for
the target Hooke platform. It is not runtime ready and is intentionally kept out
of colcon discovery with `COLCON_IGNORE`.

Remove COLCON_IGNORE only after this directory contains the real Hooke sensing
launch and hardware configuration:

- `sensing.launch.xml`
- Hesai LiDAR driver configuration
- Fixposition/GNSS/INS/IMU launch and topic mapping
- pointcloud filtering or format adapters needed for the official contracts

The final package must expose the `autoracer_hooke_sensor_kit` sensor model and
stay paired with `autoracer_hooke`.

Do not reuse RC C32 launch files for Hooke. The Hooke sensing chain must publish
the official Autoware sensing topics with real Hesai and Fixposition settings.
