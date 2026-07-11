#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

usage() {
  cat <<'EOF'
Usage:
  record_mapping_bag.sh

Environment:
  BAG_ROOT                      default: ~/autoracer_mapping_bags
  BAG_NAME                      default: rc_mapping_<timestamp>
  BAG_PATH                      full output path, default: ${BAG_ROOT}/${BAG_NAME}
  INCLUDE_MAPPING_DIAGNOSTICS   include vehicle/status diagnostic topics, default: false

Records the formal mapping bag topics. This is a lower-level helper; operators
normally use scripts/rc/rc_capture_mapping_bag.sh or the start/stop pair.
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

# shellcheck disable=SC1091
source "${ROOT_DIR}/scripts/ros_env.sh"

STAMP="$(date +%Y%m%d_%H%M%S)"
BAG_ROOT="${BAG_ROOT:-${HOME}/autoracer_mapping_bags}"
BAG_NAME="${BAG_NAME:-rc_mapping_${STAMP}}"
BAG_PATH="${BAG_PATH:-${BAG_ROOT}/${BAG_NAME}}"
INCLUDE_MAPPING_DIAGNOSTICS="${INCLUDE_MAPPING_DIAGNOSTICS:-false}"
BAG_DISCOVERY_POLL_MS="${BAG_DISCOVERY_POLL_MS:-100}"

topics=(
  /sensing/lidar/raw/pointcloud
  /sensing/lidar/concatenated/pointcloud
  /sensing/lidar/filtered/pointcloud
  /sensing/imu/imu_data_raw
  /sensing/imu/imu_data
  /tf
  /tf_static
  /rosout
)

if [[ "${INCLUDE_MAPPING_DIAGNOSTICS}" == "true" ]]; then
  topics+=(
    /vehicle/status/velocity_status
    /vehicle/status/steering_status
    /vehicle/status/gear_status
    /autoracer/vehicle_interface/state
    /scan_raw
  )
fi

mkdir -p "$(dirname "${BAG_PATH}")"
echo "[mapping-bag] recording to ${BAG_PATH}"
printf '[mapping-bag] topic: %s\n' "${topics[@]}"

topic_regex="$(IFS='|'; printf '^(%s)$' "${topics[*]}")"
exec ros2 bag record \
  -s sqlite3 \
  -o "${BAG_PATH}" \
  -e "${topic_regex}" \
  --include-unpublished-topics \
  --polling-interval "${BAG_DISCOVERY_POLL_MS}"
