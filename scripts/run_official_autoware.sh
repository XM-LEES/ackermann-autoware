#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f "$ROOT_DIR/defaults.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/defaults.env"
  set +a
fi

: "${AUTORACER_VEHICLE_MODEL:=autoracer_rc}"
: "${AUTORACER_SENSOR_MODEL:=autoracer_rc_sensor_kit}"
: "${AUTOWARE_DATA_PATH:=${HOME}/autoware_data}"
: "${POINTCLOUD_CONTAINER_NAME:=pointcloud_container}"
: "${LANELET2_MAP_FILE:=lanelet2_map.osm}"
: "${POINTCLOUD_MAP_FILE:=pointcloud_map.pcd}"
: "${LAUNCH_VEHICLE:=true}"
: "${LAUNCH_SENSING:=true}"
: "${LAUNCH_LOCALIZATION:=true}"
: "${LAUNCH_PLANNING:=true}"
: "${LAUNCH_CONTROL:=true}"
: "${LAUNCH_RVIZ:=false}"
: "${LAUNCH_MAP:=true}"
: "${LAUNCH_SYSTEM:=true}"
: "${LAUNCH_SYSTEM_MONITOR:=true}"
: "${LAUNCH_API:=true}"
: "${LAUNCH_PERCEPTION:=false}"
: "${LAUNCH_SENSING_DRIVER:=${LAUNCH_SENSING:-true}}"
: "${LAUNCH_VEHICLE_INTERFACE:=${LAUNCH_VEHICLE:-true}}"
: "${RVIZ_CONFIG:=}"
: "${RVIZ_DISPLAY:=}"
: "${RVIZ_XAUTHORITY:=}"
: "${SYSTEM_MONITOR_NET_PARAM_PATH:=}"
: "${ENABLE_ALL_MODULES_AUTO_MODE:=false}"
: "${GNSS_ENABLED:=false}"

ACTIVE_AUTORACER_VEHICLE_MODEL="autoracer_rc"
ACTIVE_AUTORACER_SENSOR_MODEL="autoracer_rc_sensor_kit"

is_true() {
  case "${1,,}" in
    1 | true | yes | on) return 0 ;;
    *) return 1 ;;
  esac
}

require_active_profile_pair() {
  if [[ "${AUTORACER_VEHICLE_MODEL}" == "${ACTIVE_AUTORACER_VEHICLE_MODEL}" ]] &&
    [[ "${AUTORACER_SENSOR_MODEL}" == "${ACTIVE_AUTORACER_SENSOR_MODEL}" ]]; then
    return 0
  fi

  cat >&2 <<EOF
ERROR: Only the RC official profile is enabled in this branch.
Requested vehicle_model=${AUTORACER_VEHICLE_MODEL}
Requested sensor_model=${AUTORACER_SENSOR_MODEL}

Hooke is currently a disabled_placeholder guarded by COLCON_IGNORE. Use
scripts/hooke/hooke_start_autoware.sh for the Hooke handoff message until the
real Hooke profile is complete.
EOF
  exit 2
}

require_map_assets() {
  if ! is_true "${LAUNCH_MAP}"; then
    return 0
  fi

  if [[ ! -d "${MAP_PATH}" ]]; then
    echo "ERROR: map directory does not exist: ${MAP_PATH}" >&2
    exit 1
  fi

  local pointcloud_path="${MAP_PATH}/${POINTCLOUD_MAP_FILE}"
  local asset
  for asset in pointcloud_map_metadata.yaml "${LANELET2_MAP_FILE}" map_projector_info.yaml; do
    if [[ ! -f "${MAP_PATH}/${asset}" ]]; then
      echo "ERROR: required map asset is missing: ${MAP_PATH}/${asset}" >&2
      exit 1
    fi
  done

  if [[ -d "${pointcloud_path}" ]]; then
    if ! find "${pointcloud_path}" -type f -name '*.pcd' -print -quit | grep -q .; then
      echo "ERROR: pointcloud tile directory contains no PCD files: ${pointcloud_path}" >&2
      exit 1
    fi
    return 0
  fi

  if [[ ! -f "${pointcloud_path}" ]]; then
    echo "ERROR: pointcloud map is neither a PCD file nor a tile directory: ${pointcloud_path}" >&2
    exit 1
  fi

  local max_single_pcd_bytes="${MAX_SINGLE_PCD_BYTES:-0}"
  local pointcloud_bytes
  pointcloud_bytes="$(stat -c '%s' "${pointcloud_path}")"
  if (( max_single_pcd_bytes > 0 && pointcloud_bytes > max_single_pcd_bytes )); then
    echo "ERROR: single-file pointcloud map is too large (${pointcloud_bytes} bytes): ${pointcloud_path}" >&2
    echo "Set MAX_SINGLE_PCD_BYTES=0 to allow it, or split the map with autoware_pointcloud_divider." >&2
    echo "Repository entry point: ./tools/mapping/prepare_autoware_pointcloud_map.sh" >&2
    exit 1
  fi
}

prepare_rviz_display() {
  if ! is_true "${LAUNCH_RVIZ}"; then
    return 0
  fi

  if [[ -z "${RVIZ_DISPLAY}" ]]; then
    RVIZ_DISPLAY="${DISPLAY:-:0}"
  fi
  if [[ -z "${RVIZ_XAUTHORITY}" ]]; then
    RVIZ_XAUTHORITY="${XAUTHORITY:-${HOME}/.Xauthority}"
  fi

  export DISPLAY="${RVIZ_DISPLAY}"
  export XAUTHORITY="${RVIZ_XAUTHORITY}"

  if command -v xdpyinfo >/dev/null 2>&1 && ! xdpyinfo -display "${DISPLAY}" >/dev/null 2>&1; then
    echo "ERROR: RViz cannot connect to display ${DISPLAY} with XAUTHORITY=${XAUTHORITY}." >&2
    echo "Start from the Orin desktop session or set LAUNCH_RVIZ=false for headless operation." >&2
    exit 1
  fi
}

lidar_route_ready() {
  local route
  route="$(ip route get "$LIDAR_SENSOR_IP" 2>/dev/null || true)"
  [[ "$route" == *" dev ${LIDAR_IFACE} "* && "$route" == *" src ${LIDAR_HOST_IP} "* ]]
}

lidar_carrier_ready() {
  [[ -r "/sys/class/net/${LIDAR_IFACE}/carrier" ]] || return 1
  [[ "$(cat "/sys/class/net/${LIDAR_IFACE}/carrier")" == "1" ]]
}

try_configure_lidar_link() {
  if ! is_true "${RC_AUTO_CONFIGURE_LIDAR_LINK:-true}"; then
    return 0
  fi

  if [[ "$EUID" -eq 0 ]]; then
    ./scripts/rc/rc_configure_lidar.sh
    return 0
  fi

  if sudo -n true 2>/dev/null; then
    sudo -n -E ./scripts/rc/rc_configure_lidar.sh
    return 0
  fi

  echo "[rc-lidar] sudo is not available non-interactively." >&2
  echo "[rc-lidar] If the link is not ready, run: sudo -E ./scripts/rc/rc_configure_lidar.sh" >&2
}

require_lidar_link_ready() {
  if ! is_true "${RC_REQUIRE_LIDAR_LINK:-true}"; then
    return 0
  fi
  if ! is_true "${LAUNCH_SENSING:-true}" || ! is_true "${LAUNCH_SENSING_DRIVER:-true}"; then
    return 0
  fi
  if [[ "${AUTORACER_SENSOR_MODEL}" != "autoracer_rc_sensor_kit" ]]; then
    return 0
  fi

  if lidar_route_ready && lidar_carrier_ready; then
    return 0
  fi

  try_configure_lidar_link

  local deadline=$((SECONDS + ${LIDAR_LINK_WAIT_SEC:-20}))
  while (( SECONDS <= deadline )); do
    if lidar_route_ready && lidar_carrier_ready; then
      return 0
    fi
    sleep 1
  done

  echo "ERROR: C32 LiDAR link is not ready." >&2
  echo "Expected ${LIDAR_IFACE} ${LIDAR_HOST_IP}/32 with route to ${LIDAR_SENSOR_IP}/32." >&2
  echo "Run: sudo -E ./scripts/rc/rc_configure_lidar.sh" >&2
  echo "Then check LiDAR power/cable if carrier is still 0/down." >&2
  ip -brief addr show dev "$LIDAR_IFACE" >&2 || true
  ip route get "$LIDAR_SENSOR_IP" >&2 || true
  if [[ -r "/sys/class/net/${LIDAR_IFACE}/carrier" ]]; then
    echo "carrier=$(cat "/sys/class/net/${LIDAR_IFACE}/carrier")" >&2
  fi
  if [[ -r "/sys/class/net/${LIDAR_IFACE}/operstate" ]]; then
    echo "operstate=$(cat "/sys/class/net/${LIDAR_IFACE}/operstate")" >&2
  fi
  exit 1
}

if [[ -z "${MAP_PATH:-}" ]]; then
  if is_true "${LAUNCH_MAP}"; then
    echo "ERROR: MAP_PATH is required when LAUNCH_MAP=true." >&2
    exit 1
  fi
  MAP_PATH="${ROOT_DIR}/maps"
fi

require_active_profile_pair

if is_true "${LAUNCH_VEHICLE_INTERFACE}" && [[ -z "${SERIAL_PORT:-}" ]]; then
  echo "ERROR: SERIAL_PORT is required when LAUNCH_VEHICLE_INTERFACE=true." >&2
  echo "Current Orin RC chassis port: SERIAL_PORT=/dev/ttyCH343USB0." >&2
  echo "For map/replay checks, set LAUNCH_VEHICLE_INTERFACE=false." >&2
  exit 1
fi

require_map_assets
require_lidar_link_ready
prepare_rviz_display

# shellcheck source=scripts/ros_env.sh
source "$ROOT_DIR/scripts/ros_env.sh"

RC_LAUNCH_PREFIX="$(ros2 pkg prefix autoracer_rc_launch 2>/dev/null || true)"
if [[ -z "${RVIZ_CONFIG}" ]]; then
  if [[ -n "${RC_LAUNCH_PREFIX}" ]]; then
    RVIZ_CONFIG="${RC_LAUNCH_PREFIX}/share/autoracer_rc_launch/rviz/rc_autoware.rviz"
  else
    RVIZ_CONFIG="${ROOT_DIR}/src/autoracer_rc_launch/rviz/rc_autoware.rviz"
  fi
fi

if [[ -z "${SYSTEM_MONITOR_NET_PARAM_PATH}" ]]; then
  if [[ -n "${RC_LAUNCH_PREFIX}" ]]; then
    SYSTEM_MONITOR_NET_PARAM_PATH="${RC_LAUNCH_PREFIX}/share/autoracer_rc_launch/config/system_monitor/net_monitor.param.yaml"
  else
    SYSTEM_MONITOR_NET_PARAM_PATH="${ROOT_DIR}/src/autoracer_rc_launch/config/system_monitor/net_monitor.param.yaml"
  fi
fi

if is_true "${LAUNCH_RVIZ}" && [[ ! -r "${RVIZ_CONFIG}" ]]; then
  echo "ERROR: RViz config is not readable: ${RVIZ_CONFIG}" >&2
  exit 1
fi
if is_true "${LAUNCH_SYSTEM_MONITOR}" && [[ ! -r "${SYSTEM_MONITOR_NET_PARAM_PATH}" ]]; then
  echo "ERROR: system monitor network config is not readable: ${SYSTEM_MONITOR_NET_PARAM_PATH}" >&2
  exit 1
fi

LAUNCH_ARGS=(
  map_path:="${MAP_PATH}"
  vehicle_model:="${AUTORACER_VEHICLE_MODEL}"
  sensor_model:="${AUTORACER_SENSOR_MODEL}"
  pointcloud_container_name:="${POINTCLOUD_CONTAINER_NAME}"
  data_path:="${AUTOWARE_DATA_PATH}"
  lanelet2_map_file:="${LANELET2_MAP_FILE}"
  pointcloud_map_file:="${POINTCLOUD_MAP_FILE}"
  launch_vehicle:="${LAUNCH_VEHICLE}"
  launch_vehicle_interface:="${LAUNCH_VEHICLE_INTERFACE}"
  launch_system:="${LAUNCH_SYSTEM}"
  launch_system_monitor:="${LAUNCH_SYSTEM_MONITOR}"
  system_monitor_net_monitor_param_path:="${SYSTEM_MONITOR_NET_PARAM_PATH}"
  launch_map:="${LAUNCH_MAP}"
  launch_sensing:="${LAUNCH_SENSING}"
  launch_sensing_driver:="${LAUNCH_SENSING_DRIVER}"
  launch_localization:="${LAUNCH_LOCALIZATION}"
  gnss_enabled:="${GNSS_ENABLED}"
  launch_perception:="${LAUNCH_PERCEPTION}"
  launch_planning:="${LAUNCH_PLANNING}"
  launch_control:="${LAUNCH_CONTROL}"
  launch_api:="${LAUNCH_API}"
  enable_all_modules_auto_mode:="${ENABLE_ALL_MODULES_AUTO_MODE}"
  rviz:="${LAUNCH_RVIZ}"
  rviz_config:="${RVIZ_CONFIG}"
)

exec ros2 launch autoware_launch autoware.launch.xml \
  "${LAUNCH_ARGS[@]}"
