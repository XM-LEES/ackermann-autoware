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
    use_sim_time = LaunchConfiguration("use_sim_time")
    system_run_mode = LaunchConfiguration("system_run_mode")
    max_speed_mps = LaunchConfiguration("max_speed_mps")
    max_accel_mps2 = LaunchConfiguration("max_accel_mps2")
    max_decel_mps2 = LaunchConfiguration("max_decel_mps2")
    command_latency_sec = LaunchConfiguration("command_latency_sec")
    stopping_margin_m = LaunchConfiguration("stopping_margin_m")
    vehicle_info_param_file = LaunchConfiguration("vehicle_info_param_file")
    control_param_file = LaunchConfiguration("control_param_file")
    gate_param_file = LaunchConfiguration("gate_param_file")
    runtime_param_file = LaunchConfiguration("runtime_param_file")
    gnss_enabled = LaunchConfiguration("gnss_enabled")
    initial_pose = LaunchConfiguration("initial_pose")
    publish_visualization = LaunchConfiguration("publish_visualization")

    return LaunchDescription(
        [
            DeclareLaunchArgument("localization_map_path"),
            DeclareLaunchArgument("course_path"),
            DeclareLaunchArgument("use_sim_time", default_value="true"),
            DeclareLaunchArgument(
                "system_run_mode",
                default_value="logging_simulation",
                choices=["online", "logging_simulation"],
            ),
            DeclareLaunchArgument("max_speed_mps", default_value="100.0"),
            DeclareLaunchArgument("max_accel_mps2", default_value="0.8"),
            DeclareLaunchArgument("max_decel_mps2", default_value="-1.5"),
            DeclareLaunchArgument("command_latency_sec", default_value="0.2"),
            DeclareLaunchArgument("stopping_margin_m", default_value="5.0"),
            DeclareLaunchArgument("gnss_enabled", default_value="true"),
            DeclareLaunchArgument("initial_pose", default_value="[]"),
            DeclareLaunchArgument("publish_visualization", default_value="false"),
            DeclareLaunchArgument("vehicle_info_param_file"),
            DeclareLaunchArgument(
                "control_param_file",
                default_value=PathJoinSubstitution(
                    [
                        get_package_share_directory("autoracer_control"),
                        "config",
                        "race_controller.param.yaml",
                    ]
                ),
            ),
            DeclareLaunchArgument(
                "gate_param_file",
                default_value=PathJoinSubstitution(
                    [
                        get_package_share_directory("autoracer_safety"),
                        "config",
                        "race",
                        "vehicle_cmd_gate.safe.param.yaml",
                    ]
                ),
            ),
            DeclareLaunchArgument(
                "runtime_param_file",
                default_value=PathJoinSubstitution(
                    [
                        get_package_share_directory("autoracer_safety"),
                        "config",
                        "race",
                        "race_runtime.safe.param.yaml",
                    ]
                ),
            ),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    _launch_file("autoracer_bringup", "planning.launch.py")
                ),
                launch_arguments={
                    "localization_map_path": localization_map_path,
                    "course_path": course_path,
                    "use_sim_time": use_sim_time,
                    "system_run_mode": system_run_mode,
                    "max_speed_mps": max_speed_mps,
                    "max_accel_mps2": max_accel_mps2,
                    "max_decel_mps2": max_decel_mps2,
                    "command_latency_sec": command_latency_sec,
                    "stopping_margin_m": stopping_margin_m,
                    "gnss_enabled": gnss_enabled,
                    "initial_pose": initial_pose,
                    "publish_visualization": publish_visualization,
                }.items(),
            ),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    _launch_file("autoracer_control", "race_control.launch.py")
                ),
                launch_arguments={
                    "use_sim_time": use_sim_time,
                    "vehicle_info_param_file": vehicle_info_param_file,
                    "race_param_file": control_param_file,
                }.items(),
            ),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    _launch_file("autoracer_safety", "race_safety.launch.py")
                ),
                launch_arguments={
                    "use_sim_time": use_sim_time,
                    "vehicle_info_param_file": vehicle_info_param_file,
                    "gate_param_file": gate_param_file,
                    "runtime_param_file": runtime_param_file,
                }.items(),
            ),
        ]
    )
