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

from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
LAUNCH = PACKAGE / "launch"


def source(name):
    return (LAUNCH / name).read_text(encoding="utf-8")


def test_rc_race_is_only_a_composition_root():
    race = source("race.launch.py")
    for launch_name in ("sensing.launch.py", "vehicle.launch.py"):
        assert launch_name in race
    assert '"autoracer_bringup", "race.launch.py"' in race
    for forbidden in (
        "autoware_trajectory_follower_node",
        "autoware_vehicle_cmd_gate",
        "race_runtime_manager",
        "ndt_scan_matcher",
        "safe_control_cmd",
    ):
        assert forbidden not in race
    assert race.count("IncludeLaunchDescription(") == 3


def test_rc_race_injects_only_platform_owned_files_and_conservative_dynamics():
    race = source("race.launch.py")
    for argument in (
        '"use_sim_time": "false"',
        '"system_run_mode": "online"',
        '"max_speed_mps": "0.5"',
        '"max_accel_mps2": "0.4"',
        '"max_decel_mps2": "-0.8"',
        '"vehicle_info_param_file"',
        '"gate_param_file"',
        '"runtime_param_file"',
    ):
        assert argument in race
    assert '"control_param_file"' not in race
    assert "controller.param.yaml" not in race
    assert 'DeclareLaunchArgument("localization_map_path")' in race
    assert 'DeclareLaunchArgument("course_path")' in race


def test_vehicle_launch_owns_only_the_uart_adapter():
    vehicle = source("vehicle.launch.py")
    assert 'package="autoracer_rc_adapter"' in vehicle
    assert 'executable="rc_serial_interface"' in vehicle
    assert vehicle.count("Node(") == 1
    assert "vehicle_cmd_gate" not in vehicle
    assert "vehicle_velocity_converter" not in vehicle


def test_sensing_launch_owns_hardware_and_normalization_only():
    sensing = source("sensing.launch.py")
    assert "RegisterEventHandler" in sensing
    for required in (
        "autoracer_rc_description",
        "lslidar_driver",
        "lslidar_driver_node",
        "c32_pointcloud_adapter",
        "hipnuc_imu",
        "imu_filter_madgwick",
        "/sensing/lidar/raw/pointcloud",
        "/sensing/lidar/concatenated/pointcloud",
        "/sensing/imu/raw",
        "/sensing/imu/imu_data",
    ):
        assert required in sensing
    for forbidden in ("ndt_scan_matcher", "trajectory_follower", "vehicle_cmd_gate"):
        assert forbidden not in sensing
