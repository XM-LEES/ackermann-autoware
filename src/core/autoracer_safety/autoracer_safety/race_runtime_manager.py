from __future__ import annotations

from enum import IntEnum
import json

from autoware_adapi_v1_msgs.msg import (
    LocalizationInitializationState,
    MrmState,
    OperationModeState,
)
from autoware_control_msgs.msg import Control
from autoware_planning_msgs.msg import RouteState, Trajectory
from autoware_vehicle_msgs.msg import (
    ControlModeReport,
    Engage,
    GearCommand,
    GearReport,
    HazardLightsCommand,
    SteeringReport,
    TurnIndicatorsCommand,
    VelocityReport,
)
from autoware_vehicle_msgs.srv import ControlModeCommand
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import String
from std_srvs.srv import Trigger
from tier4_control_msgs.msg import GateMode
from tier4_external_api_msgs.srv import Engage as EngageService

from autoracer_safety.race_contract import COMMAND_QOS, STATE_QOS, TimedInput


class RuntimePhase(IntEnum):
    IDLE = 0
    READY = 1
    ARMING = 2
    ACTIVE = 3
    STOPPING = 4
    FINISHED = 5
    FAULT = 6


def localization_readiness_failure(
    *, initialized: bool, odometry_fresh: bool, pose_estimator_fresh: bool
) -> str | None:
    if not initialized:
        return "LOCALIZATION_NOT_INITIALIZED"
    if not odometry_fresh:
        return "LOCALIZATION_STALE"
    if not pose_estimator_fresh:
        return "POSE_ESTIMATOR_STALE"
    return None


def desired_gear_command(
    phase: RuntimePhase, speed_mps: float, stop_speed_mps: float
) -> int:
    driving = phase in (RuntimePhase.ARMING, RuntimePhase.ACTIVE) or abs(
        speed_mps
    ) >= stop_speed_mps
    return GearCommand.DRIVE if driving else GearCommand.PARK


class RaceRuntimeManager(Node):
    def __init__(self) -> None:
        super().__init__("race_runtime_manager")
        defaults = {
            "update_rate_hz": 20.0,
            "auto_start": True,
            "startup_timeout_sec": 90.0,
            "localization_timeout_sec": 0.20,
            "pose_estimator_timeout_sec": 0.35,
            "trajectory_timeout_sec": 0.35,
            "control_timeout_sec": 0.20,
            "vehicle_status_timeout_sec": 0.25,
            "stop_speed_mps": 0.10,
            "service_retry_sec": 0.25,
            "emergency_acceleration_mps2": -2.4,
        }
        for name, default in defaults.items():
            self.declare_parameter(name, default)

        self._phase = RuntimePhase.IDLE
        self._phase_since = self._now()
        self._start_sec = self._phase_since
        self._last_now = -1.0
        self._start_requested = bool(self.get_parameter("auto_start").value)
        self._stop_requested = False
        self._activation_armed = False
        self._activation_stamp = -1.0
        self._last_service_call = {"control_mode": -1.0, "engage": -1.0}
        self._pending = {"control_mode": None, "engage": None}
        self._reason = "WAITING_FOR_START"

        self._localization_state = TimedInput()
        self._odometry = TimedInput()
        self._ndt_pose = TimedInput()
        self._trajectory = TimedInput()
        self._route_state = TimedInput()
        self._raw_control = TimedInput()
        self._final_control = TimedInput()
        self._control_mode = TimedInput()
        self._gear = TimedInput()
        self._velocity = TimedInput()
        self._steering = TimedInput()
        self._engage = TimedInput()
        self._timed_inputs = (
            self._localization_state,
            self._odometry,
            self._ndt_pose,
            self._trajectory,
            self._route_state,
            self._raw_control,
            self._final_control,
            self._control_mode,
            self._gear,
            self._velocity,
            self._steering,
            self._engage,
        )

        self.create_subscription(
            LocalizationInitializationState,
            "/api/localization/initialization_state",
            lambda message: self._localization_state.update(
                message, self._now(), message.stamp
            ),
            STATE_QOS,
        )
        self.create_subscription(
            Odometry,
            "/localization/kinematic_state",
            lambda message: self._odometry.update(
                message, self._now(), message.header.stamp
            ),
            COMMAND_QOS,
        )
        self.create_subscription(
            PoseStamped,
            "/localization/pose_estimator/pose",
            lambda message: self._ndt_pose.update(
                message, self._now(), message.header.stamp
            ),
            COMMAND_QOS,
        )
        self.create_subscription(
            Trajectory,
            "/planning/trajectory",
            lambda message: self._trajectory.update(
                message, self._now(), message.header.stamp
            ),
            COMMAND_QOS,
        )
        self.create_subscription(
            RouteState,
            "/planning/route_state",
            lambda message: self._route_state.update(message, self._now(), message.stamp),
            STATE_QOS,
        )
        self.create_subscription(
            Control,
            "/control/trajectory_follower/control_cmd",
            lambda message: self._raw_control.update(message, self._now(), message.stamp),
            COMMAND_QOS,
        )
        self.create_subscription(
            Control,
            "/control/command/control_cmd",
            lambda message: self._final_control.update(
                message, self._now(), message.stamp
            ),
            COMMAND_QOS,
        )
        self.create_subscription(
            ControlModeReport,
            "/vehicle/status/control_mode",
            lambda message: self._control_mode.update(
                message, self._now(), message.stamp
            ),
            COMMAND_QOS,
        )
        self.create_subscription(
            GearReport,
            "/vehicle/status/gear_status",
            lambda message: self._gear.update(message, self._now(), message.stamp),
            COMMAND_QOS,
        )
        self.create_subscription(
            VelocityReport,
            "/vehicle/status/velocity_status",
            lambda message: self._velocity.update(
                message, self._now(), message.header.stamp
            ),
            COMMAND_QOS,
        )
        self.create_subscription(
            SteeringReport,
            "/vehicle/status/steering_status",
            lambda message: self._steering.update(
                message, self._now(), message.stamp
            ),
            COMMAND_QOS,
        )
        self.create_subscription(
            Engage,
            "/api/autoware/get/engage",
            lambda message: self._engage.update(message, self._now(), message.stamp),
            STATE_QOS,
        )

        self._operation_mode_pub = self.create_publisher(
            OperationModeState, "/system/operation_mode/state", STATE_QOS
        )
        self._state_pub = self.create_publisher(
            String, "/system/race_runtime/state", STATE_QOS
        )
        self._gate_mode_pub = self.create_publisher(
            GateMode, "/control/gate_mode_cmd", STATE_QOS
        )
        self._gear_pub = self.create_publisher(
            GearCommand, "/control/race_runtime/gear_cmd", COMMAND_QOS
        )
        self._turn_pub = self.create_publisher(
            TurnIndicatorsCommand,
            "/control/race_runtime/turn_indicators_cmd",
            COMMAND_QOS,
        )
        self._hazard_pub = self.create_publisher(
            HazardLightsCommand,
            "/control/race_runtime/hazard_lights_cmd",
            COMMAND_QOS,
        )
        self._mrm_pub = self.create_publisher(
            MrmState, "/system/fail_safe/mrm_state", COMMAND_QOS
        )
        self._emergency_control_pub = self.create_publisher(
            Control, "/system/emergency/control_cmd", COMMAND_QOS
        )
        self._emergency_gear_pub = self.create_publisher(
            GearCommand, "/system/emergency/gear_cmd", COMMAND_QOS
        )
        self._emergency_turn_pub = self.create_publisher(
            TurnIndicatorsCommand,
            "/system/emergency/turn_indicators_cmd",
            COMMAND_QOS,
        )
        self._emergency_hazard_pub = self.create_publisher(
            HazardLightsCommand,
            "/system/emergency/hazard_lights_cmd",
            COMMAND_QOS,
        )

        self._control_mode_client = self.create_client(
            ControlModeCommand, "/control/control_mode_request"
        )
        self._engage_client = self.create_client(
            EngageService, "/api/autoware/set/engage"
        )
        self.create_service(Trigger, "/autoracer/race/start", self._on_start)
        self.create_service(Trigger, "/autoracer/race/stop", self._on_stop)
        self.create_service(Trigger, "/autoracer/race/reset", self._on_reset)
        self.create_timer(
            1.0 / float(self.get_parameter("update_rate_hz").value), self._on_timer
        )

    def _now(self) -> float:
        return self.get_clock().now().nanoseconds * 1.0e-9

    def _fresh(self, tracker: TimedInput, parameter: str) -> bool:
        return tracker.fresh(self._now(), float(self.get_parameter(parameter).value))

    def _on_start(self, request, response):
        del request
        if self._phase not in (RuntimePhase.IDLE, RuntimePhase.READY):
            response.success = False
            response.message = f"cannot start from {self._phase.name}"
            return response
        self._start_requested = True
        response.success = True
        response.message = "start accepted"
        return response

    def _on_stop(self, request, response):
        del request
        self._stop_requested = True
        response.success = True
        response.message = "stop accepted"
        return response

    def _on_reset(self, request, response):
        del request
        if abs(self._speed_mps()) >= float(self.get_parameter("stop_speed_mps").value):
            response.success = False
            response.message = "vehicle must be stopped before reset"
            return response
        if self._control_mode.message is not None and self._control_mode.message.mode not in (
            ControlModeReport.MANUAL,
            ControlModeReport.NO_COMMAND,
        ):
            response.success = False
            response.message = "control must be manual before reset"
            return response
        if self._engage.message is not None and bool(self._engage.message.engage):
            response.success = False
            response.message = "vehicle must be disengaged before reset"
            return response
        self._reset_state(clear_inputs=False)
        response.success = True
        response.message = "reset accepted"
        return response

    def _reset_state(self, clear_inputs: bool) -> None:
        self._phase = RuntimePhase.IDLE
        self._phase_since = self._now()
        self._start_sec = self._phase_since
        self._start_requested = bool(self.get_parameter("auto_start").value)
        self._stop_requested = False
        self._activation_armed = False
        self._activation_stamp = -1.0
        self._pending = {"control_mode": None, "engage": None}
        self._reason = "RESET"
        if clear_inputs:
            for tracker in self._timed_inputs:
                tracker.clear()

    def _transition(self, phase: RuntimePhase, reason: str) -> None:
        if phase != self._phase:
            self.get_logger().info(
                f"race runtime {self._phase.name} -> {phase.name}: {reason}"
            )
            self._phase = phase
            self._phase_since = self._now()
        self._reason = reason

    def _fault(self, reason: str) -> None:
        if self._phase == RuntimePhase.FAULT:
            return
        self.get_logger().error(f"race runtime fault latched: {reason}")
        self._transition(RuntimePhase.FAULT, reason)

    def _speed_mps(self) -> float:
        if self._velocity.message is None:
            return 0.0
        return float(self._velocity.message.longitudinal_velocity)

    def _base_failure(self) -> str | None:
        localization_failure = localization_readiness_failure(
            initialized=(
                self._localization_state.message is not None
                and self._localization_state.message.state
                == LocalizationInitializationState.INITIALIZED
            ),
            odometry_fresh=self._fresh(self._odometry, "localization_timeout_sec"),
            pose_estimator_fresh=self._fresh(
                self._ndt_pose, "pose_estimator_timeout_sec"
            ),
        )
        if localization_failure is not None:
            return localization_failure
        if not self._fresh(self._trajectory, "trajectory_timeout_sec"):
            return "TRAJECTORY_STALE"
        if self._trajectory.message is None or len(self._trajectory.message.points) < 2:
            return "TRAJECTORY_INVALID"
        for tracker, reason in (
            (self._velocity, "VELOCITY_STALE"),
            (self._steering, "STEERING_STALE"),
            (self._gear, "GEAR_STALE"),
            (self._control_mode, "CONTROL_MODE_STALE"),
        ):
            if not self._fresh(tracker, "vehicle_status_timeout_sec"):
                return reason
        return None

    def _active_failure(self) -> str | None:
        failure = self._base_failure()
        if failure is not None:
            return failure
        if not self._fresh(self._raw_control, "control_timeout_sec"):
            return "RAW_CONTROL_STALE"
        if not self._fresh(self._final_control, "control_timeout_sec"):
            return "FINAL_CONTROL_STALE"
        if (
            self._control_mode.message.mode != ControlModeReport.AUTONOMOUS
            and not self._expected_control_handover()
        ):
            return "AUTONOMOUS_CONTROL_LOST"
        return None

    def _expected_control_handover(self) -> bool:
        return self._phase in (RuntimePhase.STOPPING, RuntimePhase.FAULT) and abs(
            self._speed_mps()
        ) < float(self.get_parameter("stop_speed_mps").value)

    def _final_is_stop(self) -> bool:
        if not self._fresh(self._final_control, "control_timeout_sec"):
            return False
        command = self._final_control.message
        return (
            command.longitudinal.velocity <= 0.05
            and command.longitudinal.acceleration <= 0.1
        )

    def _call_control_mode(self, mode: int) -> None:
        self._call_service(
            "control_mode",
            self._control_mode_client,
            ControlModeCommand.Request(mode=mode),
        )

    def _call_engage(self, engage: bool) -> None:
        request = EngageService.Request()
        request.engage = engage
        self._call_service("engage", self._engage_client, request)

    def _call_service(self, key: str, client, request) -> None:
        now = self._now()
        pending = self._pending[key]
        if pending is not None and not pending.done():
            return
        retry = float(self.get_parameter("service_retry_sec").value)
        if now - self._last_service_call[key] < retry or not client.service_is_ready():
            return
        self._pending[key] = client.call_async(request)
        self._last_service_call[key] = now

    def _on_timer(self) -> None:
        now = self._now()
        if self._last_now >= 0.0 and now + 0.05 < self._last_now:
            self._reset_state(clear_inputs=True)
            self._reason = "TIME_ROLLBACK_RESET"
        self._last_now = now
        base_failure = self._base_failure()

        if self._phase == RuntimePhase.IDLE:
            if not self._start_requested:
                self._reason = "WAITING_FOR_START"
            elif base_failure is None:
                self._transition(RuntimePhase.READY, "READINESS_COMPLETE")
            elif now - self._start_sec > float(
                self.get_parameter("startup_timeout_sec").value
            ):
                self._fault(base_failure)
            else:
                self._reason = base_failure
        elif self._phase == RuntimePhase.READY:
            if base_failure is not None:
                self._fault(base_failure)
            else:
                self._call_control_mode(ControlModeCommand.Request.AUTONOMOUS)
                pending = self._pending["control_mode"]
                if (
                    pending is not None
                    and pending.done()
                    and pending.result() is not None
                    and pending.result().success
                ):
                    self._transition(RuntimePhase.ARMING, "AUTO_REQUEST_ACCEPTED")
        elif self._phase == RuntimePhase.ARMING:
            if base_failure is not None:
                self._fault(base_failure)
            elif not self._fresh(self._raw_control, "control_timeout_sec"):
                self._reason = "WAITING_RAW_CONTROL"
            elif (
                self._activation_armed
                and self._engage.message is not None
                and bool(self._engage.message.engage)
            ):
                self._transition(RuntimePhase.ACTIVE, "ENGAGE_CONFIRMED")
            elif (
                self._control_mode.message.mode == ControlModeReport.AUTONOMOUS
                and self._gear.message.report == GearReport.DRIVE
                and self._final_is_stop()
            ):
                if not self._activation_armed:
                    self._activation_armed = True
                    self._activation_stamp = now
                    self._reason = "WAITING_POST_ENABLE_CONTROL"
                elif self._raw_control.receipt_sec > self._activation_stamp:
                    self._call_engage(True)
            else:
                self._reason = "WAITING_AUTO_GEAR_STOP"
        elif self._phase == RuntimePhase.ACTIVE:
            failure = self._active_failure()
            if failure is not None:
                self._fault(failure)
            elif self._stop_requested or (
                self._route_state.message is not None
                and self._route_state.message.state == RouteState.ARRIVED
            ):
                self._transition(RuntimePhase.STOPPING, "STOP_REQUESTED_OR_ARRIVED")
        elif self._phase == RuntimePhase.STOPPING:
            if abs(self._speed_mps()) >= float(
                self.get_parameter("stop_speed_mps").value
            ):
                failure = self._active_failure()
                if failure is not None:
                    self._fault(failure)
            else:
                self._call_engage(False)
                self._call_control_mode(ControlModeCommand.Request.MANUAL)
                if (
                    self._control_mode.message is not None
                    and self._control_mode.message.mode
                    in (ControlModeReport.MANUAL, ControlModeReport.NO_COMMAND)
                    and self._gear.message is not None
                    and self._gear.message.report in (GearReport.PARK, GearReport.NEUTRAL)
                    and self._engage.message is not None
                    and not bool(self._engage.message.engage)
                ):
                    self._transition(RuntimePhase.FINISHED, "STOP_CONFIRMED")
        elif self._phase == RuntimePhase.FAULT:
            if abs(self._speed_mps()) < float(
                self.get_parameter("stop_speed_mps").value
            ):
                self._call_engage(False)
                self._call_control_mode(ControlModeCommand.Request.MANUAL)

        self._publish(base_failure is None)

    def _publish(self, ready: bool) -> None:
        stamp = self.get_clock().now().to_msg()
        speed = self._speed_mps()
        fault = self._phase == RuntimePhase.FAULT

        gate_mode = GateMode()
        gate_mode.data = GateMode.AUTO
        self._gate_mode_pub.publish(gate_mode)

        gear = GearCommand()
        gear.stamp = stamp
        gear.command = desired_gear_command(
            self._phase,
            speed,
            float(self.get_parameter("stop_speed_mps").value),
        )
        self._gear_pub.publish(gear)

        turn = TurnIndicatorsCommand()
        turn.stamp = stamp
        turn.command = TurnIndicatorsCommand.DISABLE
        self._turn_pub.publish(turn)
        hazard = HazardLightsCommand()
        hazard.stamp = stamp
        hazard.command = (
            HazardLightsCommand.ENABLE if fault else HazardLightsCommand.DISABLE
        )
        self._hazard_pub.publish(hazard)

        operation = OperationModeState()
        operation.stamp = stamp
        autonomous_intent = self._phase in (
            RuntimePhase.READY,
            RuntimePhase.ARMING,
            RuntimePhase.ACTIVE,
            RuntimePhase.STOPPING,
        )
        operation.mode = (
            OperationModeState.AUTONOMOUS if autonomous_intent else OperationModeState.STOP
        )
        operation.is_autoware_control_enabled = self._phase in (
            RuntimePhase.ACTIVE,
            RuntimePhase.STOPPING,
        ) or (self._phase == RuntimePhase.ARMING and self._activation_armed)
        operation.is_in_transition = self._phase in (
            RuntimePhase.READY,
            RuntimePhase.ARMING,
            RuntimePhase.STOPPING,
        )
        operation.is_stop_mode_available = True
        operation.is_autonomous_mode_available = ready and not fault
        self._operation_mode_pub.publish(operation)

        mrm = MrmState()
        mrm.stamp = stamp
        mrm.state = MrmState.MRM_OPERATING if fault else MrmState.NORMAL
        mrm.behavior = MrmState.EMERGENCY_STOP if fault else MrmState.NONE
        self._mrm_pub.publish(mrm)

        emergency_control = Control()
        emergency_control.stamp = stamp
        emergency_control.lateral.stamp = stamp
        emergency_control.longitudinal.stamp = stamp
        emergency_control.lateral.steering_tire_angle = (
            float(self._steering.message.steering_tire_angle)
            if self._steering.message is not None
            else 0.0
        )
        emergency_control.lateral.steering_tire_rotation_rate = 0.0
        emergency_control.lateral.is_defined_steering_tire_rotation_rate = True
        emergency_control.longitudinal.velocity = 0.0
        emergency_control.longitudinal.acceleration = float(
            self.get_parameter("emergency_acceleration_mps2").value
        )
        emergency_control.longitudinal.jerk = -4.0
        emergency_control.longitudinal.is_defined_acceleration = True
        emergency_control.longitudinal.is_defined_jerk = True
        self._emergency_control_pub.publish(emergency_control)

        emergency_gear = GearCommand()
        emergency_gear.stamp = stamp
        emergency_gear.command = (
            GearCommand.DRIVE
            if abs(speed) >= float(self.get_parameter("stop_speed_mps").value)
            else GearCommand.PARK
        )
        self._emergency_gear_pub.publish(emergency_gear)
        emergency_turn = TurnIndicatorsCommand()
        emergency_turn.stamp = stamp
        emergency_turn.command = TurnIndicatorsCommand.NO_COMMAND
        self._emergency_turn_pub.publish(emergency_turn)
        emergency_hazard = HazardLightsCommand()
        emergency_hazard.stamp = stamp
        emergency_hazard.command = (
            HazardLightsCommand.ENABLE if fault else HazardLightsCommand.DISABLE
        )
        self._emergency_hazard_pub.publish(emergency_hazard)

        state = String()
        state.data = json.dumps(
            {
                "state": self._phase.name,
                "state_id": int(self._phase),
                "ready": ready and not fault,
                "reason": self._reason,
                "control_enabled": operation.is_autoware_control_enabled,
                "control_mode": None
                if self._control_mode.message is None
                else int(self._control_mode.message.mode),
                "gear": None
                if self._gear.message is None
                else int(self._gear.message.report),
                "engaged": bool(self._engage.message.engage)
                if self._engage.message is not None
                else False,
                "raw_control_fresh": self._fresh(
                    self._raw_control, "control_timeout_sec"
                ),
                "pose_estimator_fresh": self._fresh(
                    self._ndt_pose, "pose_estimator_timeout_sec"
                ),
                "final_control_fresh": self._fresh(
                    self._final_control, "control_timeout_sec"
                ),
                "stamp": self._now(),
            },
            sort_keys=True,
        )
        self._state_pub.publish(state)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = RaceRuntimeManager()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
