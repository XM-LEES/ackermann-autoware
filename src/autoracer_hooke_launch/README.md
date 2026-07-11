# autoracer_hooke_launch

Status: `pending`.

This directory reserves the official Autoware vehicle launch package name for
the target Hooke platform. It is not runtime ready and is intentionally kept out
of colcon discovery with `COLCON_IGNORE`.

Remove COLCON_IGNORE only after this directory contains the real Hooke vehicle
interface launch and adapter wiring:

- `vehicle_interface.launch.xml`
- Hooke CAN adapter launch integration
- command gate before the chassis adapter

The final package must expose the `autoracer_hooke` vehicle profile and stay
paired with `autoracer_hooke_sensor_kit`.

Do not route Hooke through the RC UART adapter. The Hooke CAN adapter and its
status topics must be validated before this placeholder becomes an active ROS
package.
