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

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution


def _launch_file(package, filename):
    return PathJoinSubstitution(
        [get_package_share_directory(package), "launch", filename]
    )


def generate_launch_description():
    localization_map_path = LaunchConfiguration("localization_map_path")
    course_path = LaunchConfiguration("course_path")
    serial_port = LaunchConfiguration("serial_port")
    imu_device = LaunchConfiguration("imu_device")
    launch_lidar = LaunchConfiguration("launch_lidar")
    launch_imu = LaunchConfiguration("launch_imu")
    enable_drive_commands = LaunchConfiguration("enable_drive_commands")
    config = PathJoinSubstitution(
        [get_package_share_directory("autoracer_rc_bringup"), "config", "rc"]
    )
    vehicle_info = PathJoinSubstitution(
        [
            get_package_share_directory("autoracer_rc_description"),
            "config",
            "vehicle_info.param.yaml",
        ]
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("localization_map_path"),
            DeclareLaunchArgument("course_path"),
            DeclareLaunchArgument("serial_port"),
            DeclareLaunchArgument("imu_device"),
            DeclareLaunchArgument("launch_lidar", default_value="true"),
            DeclareLaunchArgument("launch_imu", default_value="true"),
            DeclareLaunchArgument("enable_drive_commands", default_value="false"),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    _launch_file("autoracer_rc_bringup", "sensing.launch.py")
                ),
                launch_arguments={
                    "launch_lidar": launch_lidar,
                    "launch_imu": launch_imu,
                    "imu_device": imu_device,
                }.items(),
            ),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    _launch_file("autoracer_rc_bringup", "vehicle.launch.py")
                ),
                launch_arguments={
                    "serial_port": serial_port,
                    "enable_drive_commands": enable_drive_commands,
                }.items(),
            ),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    _launch_file("autoracer_bringup", "race.launch.py")
                ),
                launch_arguments={
                    "localization_map_path": localization_map_path,
                    "course_path": course_path,
                    "use_sim_time": "false",
                    "system_run_mode": "online",
                    "vehicle_info_param_file": vehicle_info,
                    "gate_param_file": PathJoinSubstitution(
                        [config, "vehicle_cmd_gate.param.yaml"]
                    ),
                    "runtime_param_file": PathJoinSubstitution(
                        [config, "race_runtime.param.yaml"]
                    ),
                    "max_speed_mps": "0.5",
                    "max_accel_mps2": "0.4",
                    "max_decel_mps2": "-0.8",
                    "command_latency_sec": "0.1",
                    "stopping_margin_m": "1.0",
                }.items(),
            ),
        ]
    )
