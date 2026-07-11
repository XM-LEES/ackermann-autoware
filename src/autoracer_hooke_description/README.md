# autoracer_hooke_description

Status: `pending`.

This directory reserves the official Autoware vehicle description package name
for the target Hooke platform. It is not runtime ready and is intentionally kept
out of colcon discovery with `COLCON_IGNORE`.

Remove COLCON_IGNORE only after this directory contains the real Hooke vehicle
geometry and Autoware description files:

- `vehicle_info.param.yaml`
- `mirror.param.yaml`
- `simulator_model.param.yaml`
- `vehicle.xacro`

The final package must publish the `autoracer_hooke` vehicle profile and stay
paired with `autoracer_hooke_sensor_kit`.

Do not copy RC dimensions into this package as a temporary shortcut. The handoff
requires real Hooke vehicle geometry, including wheelbase, track width, overhang,
vehicle dimensions, steering limits, and reference frames.
