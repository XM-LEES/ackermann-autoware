from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node, SetParameter
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    course_path = LaunchConfiguration("course_path")
    map_path = LaunchConfiguration("map_path")
    use_sim_time = LaunchConfiguration("use_sim_time")
    max_speed_mps = LaunchConfiguration("max_speed_mps")
    max_accel_mps2 = LaunchConfiguration("max_accel_mps2")
    max_decel_mps2 = LaunchConfiguration("max_decel_mps2")
    command_latency_sec = LaunchConfiguration("command_latency_sec")
    stopping_margin_m = LaunchConfiguration("stopping_margin_m")
    publish_visualization = LaunchConfiguration("publish_visualization")

    return LaunchDescription(
        [
            DeclareLaunchArgument("course_path"),
            DeclareLaunchArgument("map_path"),
            DeclareLaunchArgument("use_sim_time", default_value="true"),
            DeclareLaunchArgument("max_speed_mps", default_value="100.0"),
            DeclareLaunchArgument("max_accel_mps2", default_value="0.8"),
            DeclareLaunchArgument("max_decel_mps2", default_value="-1.5"),
            DeclareLaunchArgument("command_latency_sec", default_value="0.2"),
            DeclareLaunchArgument("stopping_margin_m", default_value="5.0"),
            DeclareLaunchArgument("publish_visualization", default_value="false"),
            SetParameter(
                name="use_sim_time",
                value=ParameterValue(use_sim_time, value_type=bool),
            ),
            Node(
                package="autoracer_planning",
                executable="fixed_course_publisher",
                name="fixed_course_publisher",
                output="screen",
                parameters=[
                    {
                        "course_path": course_path,
                        "map_path": map_path,
                        "trajectory_topic": "/planning/global_trajectory",
                        "visualization_topic": "/planning/course_markers",
                        "publish_visualization": ParameterValue(
                            publish_visualization, value_type=bool
                        ),
                    }
                ],
            ),
            Node(
                package="autoracer_planning",
                executable="local_trajectory_planner",
                name="local_trajectory_planner",
                output="screen",
                parameters=[
                    {
                        "global_trajectory_topic": "/planning/global_trajectory",
                        "odometry_topic": "/localization/kinematic_state",
                        "localization_state_topic": "/api/localization/initialization_state",
                        "odometry_timeout_sec": 0.35,
                        "trajectory_topic": "/planning/trajectory",
                        "route_state_topic": "/planning/route_state",
                        "publish_rate_hz": 10.0,
                        "lookahead_distance_m": 40.0,
                        "backward_distance_m": 2.0,
                        "max_speed_mps": ParameterValue(max_speed_mps, value_type=float),
                        "max_accel_mps2": ParameterValue(
                            max_accel_mps2, value_type=float
                        ),
                        "max_decel_mps2": ParameterValue(
                            max_decel_mps2, value_type=float
                        ),
                        "command_latency_sec": ParameterValue(
                            command_latency_sec, value_type=float
                        ),
                        "stopping_margin_m": ParameterValue(
                            stopping_margin_m, value_type=float
                        ),
                        "departure_speed_mps": 0.1,
                        "nearest_search_forward_distance_m": 3.0,
                        "nearest_search_forward_time_sec": 0.35,
                        "nearest_position_gate_m": 3.0,
                        "publish_markers": ParameterValue(
                            publish_visualization, value_type=bool
                        ),
                    }
                ],
            ),
        ]
    )
