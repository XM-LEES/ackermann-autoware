from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
import yaml


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))

from autoracer_safety.race_contract import TimedInput
from autoracer_safety.race_runtime_manager import (
    RuntimePhase,
    desired_gear_command,
    localization_readiness_failure,
)

from autoware_vehicle_msgs.msg import GearCommand


def _stamp(seconds: float):
    whole = int(seconds)
    return SimpleNamespace(sec=whole, nanosec=int((seconds - whole) * 1.0e9))


def test_timed_input_rejects_future_and_out_of_order_commands():
    tracker = TimedInput()
    assert tracker.update("first", 10.0, _stamp(10.0))
    assert not tracker.update("old", 10.1, _stamp(9.9))
    assert not tracker.update("future", 10.1, _stamp(10.2))
    assert tracker.message == "first"
    assert tracker.rejected_out_of_order == 1
    assert tracker.rejected_future == 1
    assert tracker.fresh(10.19, 0.20)
    assert not tracker.fresh(10.21, 0.20)

    delayed = TimedInput()
    assert delayed.update("delayed", 10.19, _stamp(10.0))
    assert not delayed.fresh(10.21, 0.20)


def test_gate_safe_profile_has_complete_equal_length_filter_arrays():
    path = PACKAGE / "config/race/vehicle_cmd_gate.safe.param.yaml"
    params = yaml.safe_load(path.read_text(encoding="utf-8"))["/**"]["ros__parameters"]
    assert params["use_emergency_handling"] is True
    assert params["check_external_emergency_heartbeat"] is False
    for profile_name in ("nominal", "on_transition"):
        profile = params[profile_name]
        count = len(profile["reference_speed_points"])
        assert profile["vel_lim"] == pytest.approx(100.0)
        for key in (
            "steer_cmd_lim",
            "steer_rate_lim_for_steer_cmd",
            "lon_acc_lim_for_lon_vel",
            "lon_jerk_lim_for_lon_acc",
            "lat_acc_lim_for_steer_cmd",
            "lat_jerk_lim_for_steer_cmd",
            "steer_cmd_diff_lim_from_current_steer",
        ):
            assert len(profile[key]) == count


def test_production_launch_uses_autoware_gate_and_not_legacy_command_gate():
    source = (PACKAGE / "launch/race_safety.launch.py").read_text(encoding="utf-8")
    assert 'package="autoware_vehicle_cmd_gate"' in source
    assert 'executable="vehicle_cmd_gate_exe"' in source
    assert 'executable="command_gate"' not in source
    assert 'executable="race_runtime_manager"' in source
    assert 'executable="race_guard"' not in source
    assert 'executable="race_supervisor"' not in source
    assert '"/control/command/control_cmd"' in source
    assert '"/control/command/emergency_cmd"' in source


def test_stopping_keeps_drive_while_moving_and_selects_park_at_rest():
    assert desired_gear_command(RuntimePhase.ACTIVE, 0.0, 0.10) == GearCommand.DRIVE
    assert desired_gear_command(RuntimePhase.STOPPING, 0.20, 0.10) == GearCommand.DRIVE
    assert desired_gear_command(RuntimePhase.STOPPING, 0.05, 0.10) == GearCommand.PARK
    assert desired_gear_command(RuntimePhase.FAULT, 5.0, 0.10) == GearCommand.DRIVE
    assert desired_gear_command(RuntimePhase.FAULT, 0.0, 0.10) == GearCommand.PARK
    assert desired_gear_command(RuntimePhase.FINISHED, 0.0, 0.10) == GearCommand.PARK


def test_runtime_readiness_requires_fresh_ndt_pose_not_only_ekf_odometry():
    assert (
        localization_readiness_failure(
            initialized=True,
            odometry_fresh=True,
            pose_estimator_fresh=False,
        )
        == "POSE_ESTIMATOR_STALE"
    )
    assert (
        localization_readiness_failure(
            initialized=True,
            odometry_fresh=True,
            pose_estimator_fresh=True,
        )
        is None
    )


def test_runtime_manager_is_single_state_and_mrm_owner():
    source = (
        PACKAGE / "autoracer_safety/race_runtime_manager.py"
    ).read_text(encoding="utf-8")
    assert '"/system/race_runtime/state"' in source
    assert '"/system/fail_safe/mrm_state"' in source
    assert '"/system/emergency/control_cmd"' in source
    assert "guard_timeout_sec" not in source
    assert "/system/race_guard/state" not in source
    assert "/system/race_supervisor/state" not in source


def test_planner_has_no_dead_runtime_guard_channel():
    planner_package = PACKAGE.parent / "autoracer_planning"
    source = (
        planner_package / "autoracer_planning/local_trajectory_planner.py"
    ).read_text(encoding="utf-8")
    manifest = (planner_package / "package.xml").read_text(encoding="utf-8")
    assert "/planning/race_guard/" not in source
    assert "VelocityLimitClearCommand" not in source
    assert "autoware_internal_planning_msgs" not in manifest
