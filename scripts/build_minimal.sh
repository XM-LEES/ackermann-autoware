#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

AUTORACER_SOURCE_LOCAL_SETUP=false
# shellcheck source=scripts/ros_env.sh
source "$ROOT_DIR/scripts/ros_env.sh"

COLCON_WORKER_ARGS=()
if [[ -n "${COLCON_PARALLEL_WORKERS:-}" ]]; then
  COLCON_WORKER_ARGS+=(--parallel-workers "$COLCON_PARALLEL_WORKERS")
fi

ACTIVE_RUNTIME_PACKAGES=(
  autoracer_sensing
  autoracer_safety
  autoracer_vehicle_interface
  autoracer_rc_description
  autoracer_rc_launch
  autoracer_rc_sensor_kit_description
  autoracer_rc_sensor_kit_launch
  hipnuc_imu
  lslidar_msgs
  lslidar_driver
  autoware_launch
  tier4_autoware_api_launch
  tier4_map_launch
  tier4_planning_launch
  tier4_control_launch
  tier4_system_launch
  tier4_vehicle_launch
  tier4_sensing_launch
  autoware_adapi_v1_msgs
  autoware_adapi_version_msgs
  autoware_adapi_specs
  autoware_adapi_adaptors
  autoware_default_adapi
  autoware_default_adapi_universe
  autoware_evaluation_adapter
  autoware_component_interface_specs
  autoware_control_msgs
  autoware_geography_utils
  autoware_global_parameter_loader
  autoware_internal_debug_msgs
  autoware_internal_localization_msgs
  autoware_lanelet2_extension
  autoware_lanelet2_utils
  autoware_localization_util
  autoware_map_msgs
  autoware_planning_msgs
  autoware_qos_utils
  autoware_sensing_msgs
  autoware_vehicle_msgs
  autoware_agnocast_wrapper
  tier4_api_msgs
  tier4_debug_msgs
  tier4_external_api_msgs
  tier4_vehicle_msgs
  tier4_api_utils
  autoware_vehicle_info_utils
  autoware_lanelet2_map_visualizer
  autoware_map_tf_generator
  autoware_map_projection_loader
  autoware_map_loader
  autoware_ndt_scan_matcher
  autoware_gnss_poser
  autoware_localization_rviz_plugin
  autoware_planning_rviz_plugin
  autoware_perception_rviz_plugin
  autoware_overlay_rviz_plugin
  autoware_mission_details_overlay_rviz_plugin
  autoware_string_stamped_rviz_plugin
  tier4_adapi_rviz_plugin
  tier4_datetime_rviz_plugin
  tier4_control_mode_rviz_plugin
  tier4_state_rviz_plugin
  tier4_vehicle_rviz_plugin
  tier4_planning_factor_rviz_plugin
  autoware_behavior_velocity_rtc_interface
  autoware_behavior_velocity_crosswalk_module
  autoware_behavior_velocity_walkway_module
  autoware_behavior_velocity_traffic_light_module
  autoware_behavior_velocity_intersection_module
  autoware_behavior_velocity_blind_spot_module
  autoware_behavior_velocity_detection_area_module
  autoware_behavior_velocity_virtual_traffic_light_module
  autoware_behavior_velocity_no_stopping_area_module
  autoware_behavior_velocity_stop_line_module
  autoware_motion_velocity_obstacle_stop_module
  autoware_motion_velocity_obstacle_slow_down_module
  autoware_motion_velocity_obstacle_cruise_module
  autoware_motion_velocity_out_of_lane_module
  autoware_motion_velocity_obstacle_velocity_limiter_module
  autoware_motion_velocity_dynamic_obstacle_stop_module
  autoware_motion_velocity_run_out_module
  autoware_motion_velocity_boundary_departure_prevention_module
  autoware_motion_velocity_road_user_stop_module
)

# These packages are buildable extension points, but official planning/control
# remains the default runtime until a candidate is explicitly wired and tested.
CANDIDATE_PACKAGES=(
  autoracer_localization
  autoracer_planning
  autoracer_control
)

# Reference packages are kept buildable for platform integration work. They are
# not selected by the current RC profile and must not be treated as active nodes.
REFERENCE_PACKAGES=(
  autoracer_description
  nebula_msgs
  nebula_hesai
  nebula_hesai_decoders
  fixposition_driver_msgs
  fixposition_driver_lib
  rtcm_msgs
  fpsdk_common
  fpsdk_ros2
  fixposition_driver_ros2
)

PACKAGES=("${ACTIVE_RUNTIME_PACKAGES[@]}")

if [[ "${BUILD_CANDIDATES:-false}" == "true" ]]; then
  PACKAGES+=("${CANDIDATE_PACKAGES[@]}")
fi

if [[ "${BUILD_REFERENCES:-false}" == "true" ]]; then
  PACKAGES+=("${REFERENCE_PACKAGES[@]}")
fi

OVERRIDE_PACKAGES=(
  autoware_adapi_v1_msgs
  autoware_adapi_version_msgs
  autoware_global_parameter_loader
  autoware_internal_planning_msgs
  autoware_lanelet2_extension
  autoware_map_msgs
  autoware_perception_msgs
  autoware_planning_msgs
  autoware_utils_geometry
  autoware_utils_math
  autoware_utils_system
  autoware_utils_visualization
  autoware_vehicle_msgs
)

colcon build --symlink-install \
  "${COLCON_WORKER_ARGS[@]}" \
  --packages-up-to "${PACKAGES[@]}" \
  --allow-overriding "${OVERRIDE_PACKAGES[@]}" \
  --cmake-args -DBUILD_TESTING=OFF
