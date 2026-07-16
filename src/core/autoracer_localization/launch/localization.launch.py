from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription
from launch.launch_description_sources import AnyLaunchDescriptionSource, PythonLaunchDescriptionSource
from launch.substitutions import (
    EnvironmentVariable,
    LaunchConfiguration,
    PathJoinSubstitution,
)
from launch_ros.actions import Node, SetParameter
from launch_ros.parameter_descriptions import ParameterValue


def _pkg_file(package, *parts):
    return PathJoinSubstitution([get_package_share_directory(package), *parts])


def _localization_param(*parts):
    return _pkg_file("autoracer_localization", "config", "pilot_compatible", *parts)


def _workspace_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "autoracer_hooke":
            return parent
    raise RuntimeError("failed to locate autoracer_hooke workspace from launch file path")


def generate_launch_description():
    default_map_path = str(
        _workspace_root() / "maps" / "urbanroad_route271_20260710"
    )
    map_path = LaunchConfiguration("localization_map_path")
    use_sim_time = LaunchConfiguration("use_sim_time")
    system_run_mode = LaunchConfiguration("system_run_mode")
    input_pointcloud = LaunchConfiguration("input_pointcloud")
    initial_pose = LaunchConfiguration("initial_pose")
    gnss_enabled = LaunchConfiguration("gnss_enabled")
    localization_pointcloud_container_name = LaunchConfiguration(
        "localization_pointcloud_container_name"
    )
    map_projector_info = PathJoinSubstitution([map_path, "map_projector_info.yaml"])
    pointcloud_map = PathJoinSubstitution([map_path, "pointcloud_map.pcd"])
    pointcloud_metadata = PathJoinSubstitution([map_path, "pointcloud_map_metadata.yaml"])

    localization_launch = PathJoinSubstitution(
        [
            get_package_share_directory("tier4_localization_launch"),
            "launch",
            "localization.launch.xml",
        ]
    )

    runtime_actions = [
        SetParameter(
            name="use_sim_time",
            value=ParameterValue(use_sim_time, value_type=bool),
        ),
        Node(
            package="autoware_map_projection_loader",
            executable="autoware_map_projection_loader_node",
            name="map_projection_loader",
            output="screen",
            parameters=[
                {
                    "map_projector_info_path": map_projector_info,
                    "lanelet2_map_path": "",
                }
            ],
        ),
        Node(
            package="autoware_map_loader",
            executable="autoware_pointcloud_map_loader",
            namespace="/map",
            name="pointcloud_map_loader",
            output="screen",
            parameters=[
                {
                    "enable_whole_load": True,
                    "enable_downsampled_whole_load": False,
                    "enable_partial_load": True,
                    "enable_selected_load": False,
                    "leaf_size": 3.0,
                    "pcd_paths_or_directory": ParameterValue(
                        [[pointcloud_map]], value_type=list[str]
                    ),
                    "pcd_metadata_path": pointcloud_metadata,
                }
            ],
            remappings=[
                ("output/pointcloud_map", "/map/pointcloud_map"),
                ("output/pointcloud_map_metadata", "/map/pointcloud_map_metadata"),
                ("service/get_partial_pcd_map", "/map/get_partial_pointcloud_map"),
                ("service/get_differential_pcd_map", "/map/get_differential_pointcloud_map"),
                ("service/get_selected_pcd_map", "/map/get_selected_pointcloud_map"),
            ],
        ),
        Node(
            package="rclcpp_components",
            executable="component_container_mt",
            name="pointcloud_container",
            output="screen",
        ),
        GroupAction(
            [
                IncludeLaunchDescription(
                    AnyLaunchDescriptionSource(
                        _pkg_file(
                            "autoware_vehicle_velocity_converter",
                            "launch",
                            "vehicle_velocity_converter.launch.xml",
                        )
                    ),
                    launch_arguments={
                        "input_vehicle_velocity_topic": "/vehicle/status/velocity_status",
                        "output_twist_with_covariance": (
                            "/sensing/vehicle_velocity_converter/twist_with_covariance"
                        ),
                    }.items(),
                )
            ]
        ),
        Node(
            package="autoracer_sensing",
            executable="localization_adapi_bridge",
            name="localization_adapi_bridge",
            output="screen",
            parameters=[
                {
                    "min_initialize_stamp_sec": ParameterValue(
                        EnvironmentVariable(
                            "CM_LOCALIZATION_AUTO_INIT_MIN_STAMP_SEC",
                            default_value="6.0",
                        ),
                        value_type=float,
                    ),
                    "max_auto_retry_attempts": ParameterValue(
                        EnvironmentVariable(
                            "CM_LOCALIZATION_AUTO_RETRY_MAX_ATTEMPTS",
                            default_value="1",
                        ),
                        value_type=int,
                    ),
                    "auto_retry_max_gnss_xy_m": ParameterValue(
                        EnvironmentVariable(
                            "CM_LOCALIZATION_AUTO_RETRY_MAX_GNSS_XY_M",
                            default_value="0.0",
                        ),
                        value_type=float,
                    ),
                    "auto_retry_max_gnss_yaw_deg": ParameterValue(
                        EnvironmentVariable(
                            "CM_LOCALIZATION_AUTO_RETRY_MAX_GNSS_YAW_DEG",
                            default_value="0.0",
                        ),
                        value_type=float,
                    ),
                    "auto_retry_delay_sec": ParameterValue(
                        EnvironmentVariable(
                            "CM_LOCALIZATION_AUTO_RETRY_DELAY_SEC",
                            default_value="0.2",
                        ),
                        value_type=float,
                    ),
                    "auto_retry_initialpose_timeout_sec": ParameterValue(
                        EnvironmentVariable(
                            "CM_LOCALIZATION_AUTO_RETRY_INITIALPOSE_TIMEOUT_SEC",
                            default_value="3.0",
                        ),
                        value_type=float,
                    ),
                }
            ],
        ),
        IncludeLaunchDescription(
            AnyLaunchDescriptionSource(localization_launch),
            launch_arguments={
                "pose_source": "ndt",
                "twist_source": "gyro_odom",
                "initial_pose": initial_pose,
                "gnss_enabled": gnss_enabled,
                "system_run_mode": system_run_mode,
                "input_pointcloud": input_pointcloud,
                "localization_pointcloud_container_name": (
                    localization_pointcloud_container_name
                ),
                "ndt_scan_matcher/ndt_scan_matcher_param_path": _localization_param(
                    "ndt_scan_matcher", "ndt_scan_matcher.param.yaml"
                ),
                "ndt_scan_matcher/pointcloud_preprocessor/crop_box_filter_measurement_range_param_path": _localization_param(
                    "ndt_scan_matcher",
                    "pointcloud_preprocessor",
                    "crop_box_filter_measurement_range.param.yaml",
                ),
                "ndt_scan_matcher/pointcloud_preprocessor/voxel_grid_downsample_filter_param_path": _localization_param(
                    "ndt_scan_matcher",
                    "pointcloud_preprocessor",
                    "voxel_grid_filter.param.yaml",
                ),
                "ndt_scan_matcher/pointcloud_preprocessor/random_downsample_filter_param_path": _localization_param(
                    "ndt_scan_matcher",
                    "pointcloud_preprocessor",
                    "random_downsample_filter.param.yaml",
                ),
                "localization_error_monitor_param_path": _localization_param(
                    "localization_error_monitor.param.yaml"
                ),
                "ekf_localizer_param_path": _localization_param(
                    "ekf_localizer.param.yaml"
                ),
                "stop_filter_param_path": _localization_param("stop_filter.param.yaml"),
                "pose_instability_detector_param_path": _localization_param(
                    "pose_instability_detector.param.yaml"
                ),
                "pose_initializer_param_path": _localization_param(
                    "pose_initializer.param.yaml"
                ),
                "twist2accel_param_path": _localization_param(
                    "twist2accel.param.yaml"
                ),
                "eagleye_param_path": _localization_param("eagleye_config.param.yaml"),
                "ar_tag_based_localizer_param_path": _localization_param(
                    "ar_tag_based_localizer.param.yaml"
                ),
                "lidar_marker_localizer/lidar_marker_localizer_param_path": _localization_param(
                    "lidar_marker_localizer", "lidar_marker_localizer.param.yaml"
                ),
                "lidar_marker_localizer/pointcloud_preprocessor/crop_box_filter_measurement_range_param_path": _localization_param(
                    "lidar_marker_localizer",
                    "pointcloud_preprocessor",
                    "crop_box_filter_measurement_range.param.yaml",
                ),
                "lidar_marker_localizer/pointcloud_preprocessor/ring_filter_param_path": _localization_param(
                    "lidar_marker_localizer",
                    "pointcloud_preprocessor",
                    "ring_filter.param.yaml",
                ),
            }.items(),
        ),
    ]

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "map_path",
                default_value=EnvironmentVariable("MAP_PATH", default_value=default_map_path),
            ),
            DeclareLaunchArgument(
                "localization_map_path",
                default_value=LaunchConfiguration("map_path"),
            ),
            DeclareLaunchArgument("use_sim_time", default_value="true"),
            DeclareLaunchArgument(
                "system_run_mode",
                default_value="logging_simulation",
                choices=["online", "logging_simulation"],
            ),
            DeclareLaunchArgument(
                "input_pointcloud",
                default_value="/sensing/lidar/concatenated/pointcloud",
            ),
            DeclareLaunchArgument(
                "localization_pointcloud_container_name",
                default_value="/pointcloud_container",
            ),
            DeclareLaunchArgument("initial_pose", default_value="[]"),
            DeclareLaunchArgument("gnss_enabled", default_value="true"),
            GroupAction(runtime_actions),
        ]
    )
