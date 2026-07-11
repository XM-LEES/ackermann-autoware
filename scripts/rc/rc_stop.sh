#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  rc_stop.sh

Stops RC Autoware, sensor, localization, planning, control, vehicle-interface,
RViz, and rosbag processes started by the formal RC scripts.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -gt 0 ]]; then
  echo "ERROR: unknown argument: $1" >&2
  usage >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CURRENT_UID="$(id -u)"

graceful_patterns=(
  "[r]os2 launch autoware_launch autoware.launch.xml"
  "[r]os2 bag record"
)

patterns=(
  "[r]os2 launch autoware_launch autoware.launch.xml"
  "[r]un_official_autoware.sh"
  "${ROOT_DIR}/install/[a]utoware_"
  "topic_tools/relay"
  "[r]viz2"
  "[r]obot_state_publisher"
  "[s]tatic_transform_publisher"
  "component_container"
  "pointcloud_container"
  "[l]slidar_driver_node"
  "c32_pointcloud_adapter"
  "[p]ointcloud_voxel_filter"
  "[h]ipnuc_imu/lib/hipnuc_imu/talker"
  "[I]MU_publisher"
  "[i]mu_filter_madgwick"
  "[f]ixposition_seed_filter"
  "[m]anual_seed_pose_publisher"
  "[n]dt_initial_pose_predictor"
  "[n]dt_startup_helper"
  "[k]inematic_state_publisher"
  "[a]utoware_ndt_scan_matcher_node"
  "[a]utoware_pointcloud_map_loader"
  "[a]utoware_lanelet2_map_loader"
  "[a]utoware_map_projection_loader_node"
  "[l]anelet_route_planner"
  "[p]ure_pursuit_controller"
  "${ROOT_DIR}/install/[a]utoracer_safety/"
  "${ROOT_DIR}/install/[a]utoracer_vehicle_interface/"
  "${ROOT_DIR}/install/[a]utoracer_sensing/"
  "[c]ommand_gate"
  "[r]c_serial_interface"
  "[r]os2 bag record"
)

any_pattern_running() {
  local pattern
  for pattern in "$@"; do
    if pgrep -u "${CURRENT_UID}" -f "${pattern}" >/dev/null 2>&1; then
      return 0
    fi
  done
  return 1
}

wait_for_patterns() {
  local timeout_sec="$1"
  shift
  local ticks=$((timeout_sec * 5))
  local tick
  for ((tick=0; tick<ticks; tick++)); do
    any_pattern_running "$@" || return 0
    sleep 0.2
  done
  return 1
}

graceful_requested=false
for pattern in "${graceful_patterns[@]}"; do
  if pgrep -u "${CURRENT_UID}" -f "${pattern}" >/dev/null 2>&1; then
    pkill -INT -u "${CURRENT_UID}" -f "${pattern}" 2>/dev/null || true
    graceful_requested=true
  fi
done

if [[ "${graceful_requested}" == "true" ]]; then
  if ! wait_for_patterns "${INTERRUPT_GRACE_SEC:-10}" "${graceful_patterns[@]}"; then
    echo "[rc-stop] top-level launch is still active after SIGINT; sending SIGTERM"
    for pattern in "${graceful_patterns[@]}"; do
      pkill -TERM -u "${CURRENT_UID}" -f "${pattern}" 2>/dev/null || true
    done
  fi
  if ! wait_for_patterns "${SHUTDOWN_GRACE_SEC:-20}" "${patterns[@]}"; then
    echo "[rc-stop] graceful shutdown timed out; terminating residual processes"
  fi
fi

for pattern in "${patterns[@]}"; do
  pkill -TERM -u "${CURRENT_UID}" -f "${pattern}" 2>/dev/null || true
done

wait_for_patterns "${STOP_WAIT_SEC:-5}" "${patterns[@]}" || true

for pattern in "${patterns[@]}"; do
  pkill -KILL -u "${CURRENT_UID}" -f "${pattern}" 2>/dev/null || true
done

sleep 0.2
remaining="$({
  for pattern in "${patterns[@]}"; do
    pgrep -u "${CURRENT_UID}" -af "${pattern}" 2>/dev/null || true
  done
} | sort -u)"
if [[ -n "${remaining}" ]]; then
  echo "ERROR: RC processes remain after shutdown:" >&2
  echo "${remaining}" >&2
  exit 1
fi

echo "[rc-stop] RC runtime processes stopped"
