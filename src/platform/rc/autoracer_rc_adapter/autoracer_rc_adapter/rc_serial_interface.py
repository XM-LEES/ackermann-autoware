# Copyright 2026 OpenAI
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""RC UART adapter terminating at standard Autoware vehicle topics."""

import math
import time
from typing import Tuple

from .rc_serial_protocol import Telemetry, TelemetryParser, encode_control_frame


GEAR_NONE = 0
GEAR_NEUTRAL = 1
GEAR_DRIVE = 2
GEAR_REVERSE = 20
GEAR_PARK = 22
GEAR_LOW = 23

Motion = Tuple[float, float, float, bool]


def _require_positive(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and positive")


def control_to_motion(
    target_velocity: float,
    steering_tire_angle: float,
    gear: int,
    wheelbase: float,
    max_speed: float,
    max_steer: float,
) -> Motion:
    """Convert standard velocity/steering/gear into firmware vx/vy/wz."""

    _require_positive("wheelbase", wheelbase)
    _require_positive("max_speed", max_speed)
    _require_positive("max_steer", max_steer)
    if not math.isfinite(target_velocity) or not math.isfinite(steering_tire_angle):
        return (0.0, 0.0, 0.0, True)
    if gear not in (GEAR_DRIVE, GEAR_LOW, GEAR_REVERSE):
        return (0.0, 0.0, 0.0, True)
    direction = -1.0 if gear == GEAR_REVERSE else 1.0
    vx_mps = direction * min(abs(target_velocity), max_speed)
    steering = max(-max_steer, min(max_steer, steering_tire_angle))
    wz_rad_s = 0.0 if vx_mps == 0.0 else vx_mps * math.tan(steering) / wheelbase
    return (vx_mps, 0.0, wz_rad_s, False)


def command_or_stop(
    motion: Motion,
    command_age: float,
    timeout: float,
    drive_enabled: bool,
) -> Motion:
    """Fail closed when commands are stale or physical output is disabled."""

    _require_positive("timeout", timeout)
    if not drive_enabled or not math.isfinite(command_age) or command_age > timeout:
        return (0.0, 0.0, 0.0, True)
    return motion


def telemetry_to_status(
    telemetry: Telemetry,
    last_steer: float,
    selected_gear: int,
    wheelbase: float,
    max_steer: float,
) -> Tuple[float, float, int]:
    """Convert feedback while preserving the adapter's selected logical gear."""

    _require_positive("wheelbase", wheelbase)
    _require_positive("max_steer", max_steer)
    values = (
        telemetry.vx_mps,
        telemetry.vy_mps,
        telemetry.wz_rad_s,
        telemetry.battery_v,
        last_steer,
    )
    if not all(math.isfinite(value) for value in values):
        raise ValueError("telemetry contains a non-finite value")
    if abs(telemetry.vx_mps) < 1e-6:
        steering = max(-max_steer, min(max_steer, last_steer))
    else:
        steering = math.atan(telemetry.wz_rad_s * wheelbase / telemetry.vx_mps)
        steering = max(-max_steer, min(max_steer, steering))
    valid_gears = (
        GEAR_NONE,
        GEAR_NEUTRAL,
        GEAR_DRIVE,
        GEAR_REVERSE,
        GEAR_PARK,
        GEAR_LOW,
    )
    reported_gear = selected_gear if selected_gear in valid_gears else GEAR_NEUTRAL
    return telemetry.vx_mps, steering, reported_gear


def _create_node_class():
    import rclpy
    from autoware_control_msgs.msg import Control
    from autoware_vehicle_msgs.msg import (
        ControlModeReport,
        GearCommand,
        GearReport,
        SteeringReport,
        VelocityReport,
    )
    from autoware_vehicle_msgs.srv import ControlModeCommand
    from rclpy.node import Node

    class RcSerialInterface(Node):
        def __init__(self):
            super().__init__("rc_serial_interface")
            self.declare_parameter("device", "")
            self.declare_parameter("baud", 115200)
            self.declare_parameter("command_timeout_sec", 0.5)
            self.declare_parameter("command_rate_hz", 30.0)
            self.declare_parameter("feedback_rate_hz", 50.0)
            self.declare_parameter("wheelbase", 0.6)
            self.declare_parameter("max_speed", 0.5)
            self.declare_parameter("max_steer", 0.262)
            self.declare_parameter("enable_drive_commands", False)

            self._device = self.get_parameter("device").value
            if not self._device:
                raise ValueError("device parameter is required")
            self._baud = int(self.get_parameter("baud").value)
            self._timeout = float(self.get_parameter("command_timeout_sec").value)
            self._wheelbase = float(self.get_parameter("wheelbase").value)
            self._max_speed = float(self.get_parameter("max_speed").value)
            self._max_steer = float(self.get_parameter("max_steer").value)
            self._drive_enabled = bool(self.get_parameter("enable_drive_commands").value)
            self._serial = None
            self._next_reconnect = 0.0
            self._parser = TelemetryParser()
            self._motion = (0.0, 0.0, 0.0, True)
            self._last_command_time = float("-inf")
            self._last_steer = 0.0
            self._gear = GEAR_NEUTRAL

            self.create_subscription(Control, "/control/command/control_cmd", self._on_control, 1)
            self.create_subscription(GearCommand, "/control/command/gear_cmd", self._on_gear, 1)
            self._velocity_pub = self.create_publisher(
                VelocityReport, "/vehicle/status/velocity_status", 10
            )
            self._steering_pub = self.create_publisher(
                SteeringReport, "/vehicle/status/steering_status", 10
            )
            self._gear_pub = self.create_publisher(GearReport, "/vehicle/status/gear_status", 10)
            self._mode_pub = self.create_publisher(
                ControlModeReport, "/vehicle/status/control_mode", 10
            )
            self.create_service(
                ControlModeCommand,
                "/control/control_mode_request",
                self._on_mode_request,
            )
            command_rate = float(self.get_parameter("command_rate_hz").value)
            feedback_rate = float(self.get_parameter("feedback_rate_hz").value)
            self.create_timer(1.0 / command_rate, self._write_command)
            self.create_timer(1.0 / feedback_rate, self._read_feedback)

        def _connect(self):
            if self._serial is not None or time.monotonic() < self._next_reconnect:
                return
            try:
                import serial

                self._serial = serial.Serial(self._device, self._baud, timeout=0)
            except (OSError, ValueError) as error:
                self._next_reconnect = time.monotonic() + 1.0
                self.get_logger().warning(f"RC serial unavailable: {error}")

        def _disconnect(self, error):
            if self._serial is not None:
                self._serial.close()
            self._serial = None
            self._next_reconnect = time.monotonic() + 1.0
            self.get_logger().warning(f"RC serial disconnected: {error}")

        def _on_control(self, message):
            self._last_steer = float(message.lateral.steering_tire_angle)
            self._motion = control_to_motion(
                float(message.longitudinal.velocity),
                self._last_steer,
                self._gear,
                self._wheelbase,
                self._max_speed,
                self._max_steer,
            )
            self._last_command_time = time.monotonic()

        def _on_gear(self, message):
            self._gear = int(message.command)

        def _on_mode_request(self, request, response):
            self._drive_enabled = request.mode == ControlModeCommand.Request.AUTONOMOUS
            response.success = True
            return response

        def _write_command(self):
            self._connect()
            if self._serial is None:
                return
            motion = command_or_stop(
                self._motion,
                time.monotonic() - self._last_command_time,
                self._timeout,
                self._drive_enabled,
            )
            try:
                self._serial.write(encode_control_frame(*motion))
            except (OSError, ValueError) as error:
                self._disconnect(error)

        def _read_feedback(self):
            self._connect()
            if self._serial is None:
                self._publish_mode(False)
                return
            try:
                data = self._serial.read(self._serial.in_waiting or 1)
            except (OSError, ValueError) as error:
                self._disconnect(error)
                return
            for telemetry in self._parser.feed(data):
                self._publish_status(telemetry)

        def _publish_status(self, telemetry):
            velocity, steering, gear = telemetry_to_status(
                telemetry,
                self._last_steer,
                self._gear,
                self._wheelbase,
                self._max_steer,
            )
            stamp = self.get_clock().now().to_msg()
            velocity_report = VelocityReport()
            velocity_report.header.stamp = stamp
            velocity_report.header.frame_id = "base_link"
            velocity_report.longitudinal_velocity = velocity
            velocity_report.lateral_velocity = telemetry.vy_mps
            velocity_report.heading_rate = telemetry.wz_rad_s
            self._velocity_pub.publish(velocity_report)
            steering_report = SteeringReport()
            steering_report.stamp = stamp
            steering_report.steering_tire_angle = steering
            self._steering_pub.publish(steering_report)
            gear_report = GearReport()
            gear_report.stamp = stamp
            gear_report.report = gear
            self._gear_pub.publish(gear_report)
            self._publish_mode(True)

        def _publish_mode(self, connected):
            report = ControlModeReport()
            report.stamp = self.get_clock().now().to_msg()
            if connected and self._drive_enabled:
                report.mode = ControlModeReport.AUTONOMOUS
            elif connected:
                report.mode = ControlModeReport.MANUAL
            else:
                report.mode = ControlModeReport.NOT_READY
            self._mode_pub.publish(report)

    return rclpy, RcSerialInterface


def main(args=None):
    """Run the RC serial interface node."""

    rclpy, node_class = _create_node_class()
    rclpy.init(args=args)
    node = node_class()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
