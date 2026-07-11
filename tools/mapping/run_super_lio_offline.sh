#!/usr/bin/env bash
set -euo pipefail

TOOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${TOOL_DIR}/../.." && pwd)"
BAG_PATH="${1:?usage: run_super_lio_offline.sh <bag_path> [run_id]}"
RUN_ID="${2:-$(date +%Y%m%d_%H%M%S)_super_lio}"
MAPPING_WS="${MAPPING_WS:-/home/milesli/Desktop/RC/rc_mapping_ws}"
MAPPING_DATA_DIR="${MAPPING_DATA_DIR:-/home/milesli/Desktop/RC/rc_mapping_data}"
CONFIG="${CONFIG:-${REPO_ROOT}/tools/mapping/config/rc_c32_super_lio.yaml}"
PLAYBACK_RATE="${PLAYBACK_RATE:-1.0}"
RUN_DIR="${MAPPING_DATA_DIR}/runs/${RUN_ID}"
SUPER_LIO_REPO="${MAPPING_WS}/src/Super-LIO"
SUPER_LIO_MAP_DIR="${SUPER_LIO_REPO}/src/super_lio/map"

for path in "${BAG_PATH}" "${CONFIG}" "${MAPPING_WS}/install/setup.bash"; do
  [[ -e "${path}" ]] || { echo "ERROR: missing required path: ${path}" >&2; exit 1; }
done
[[ ! -e "${RUN_DIR}" ]] || { echo "ERROR: run directory already exists: ${RUN_DIR}" >&2; exit 1; }

mkdir -p "${RUN_DIR}/ros_log"
OUTPUT_ENV_FILE="${RUN_DIR}/selected_topics.env" \
  "${TOOL_DIR}/inspect_bag_topics.sh" "${BAG_PATH}" | tee "${RUN_DIR}/bag_inspection.txt"
source "${RUN_DIR}/selected_topics.env"
cp "${CONFIG}" "${RUN_DIR}/rc_c32_super_lio.yaml"
git -C "${SUPER_LIO_REPO}" rev-parse HEAD > "${RUN_DIR}/super_lio_commit.txt"
git -C "${SUPER_LIO_REPO}" status --short > "${RUN_DIR}/super_lio_status.txt"

set +u
source "/opt/ros/${ROS_DISTRO:-humble}/setup.bash"
source "${MAPPING_WS}/install/setup.bash"
set -u
export ROS_LOG_DIR="${RUN_DIR}/ros_log"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-77}"

rm -f "${SUPER_LIO_MAP_DIR}/map.pcd"
rm -rf "${SUPER_LIO_MAP_DIR}/PCD"

cd "${RUN_DIR}"
setsid ros2 run super_lio super_lio_node --ros-args \
  --params-file "${RUN_DIR}/rc_c32_super_lio.yaml" \
  -p "lio.ros.lidar_topic:=${LIDAR_TOPIC}" \
  -p "lio.ros.imu_topic:=${IMU_TOPIC}" > super_lio.log 2>&1 &
lio_pid=$!

stop_lio() {
  set +e
  if pgrep -g "${lio_pid}" >/dev/null 2>&1; then
    kill -INT "-${lio_pid}" 2>/dev/null || true
    for _ in $(seq 1 25); do
      pgrep -g "${lio_pid}" >/dev/null 2>&1 || return 0
      sleep 1
    done
    kill -TERM "-${lio_pid}" 2>/dev/null || true
  fi
}
trap stop_lio EXIT

sleep 2
ros2 bag play "${BAG_PATH}" --clock --rate "${PLAYBACK_RATE}" > bag_play.log 2>&1
sleep 2
stop_lio
trap - EXIT

if [[ ! -f "${SUPER_LIO_MAP_DIR}/map.pcd" ]]; then
  echo "ERROR: Super-LIO did not generate map.pcd; inspect ${RUN_DIR}/super_lio.log" >&2
  exit 1
fi
mkdir -p "${RUN_DIR}/map"
cp "${SUPER_LIO_MAP_DIR}/map.pcd" "${RUN_DIR}/map/map.pcd"
"${TOOL_DIR}/audit_pointcloud_map.py" "${RUN_DIR}/map/map.pcd" \
  --output "${RUN_DIR}/map/quality_report.json" \
  --max-ground-tilt-deg "${MAX_GROUND_TILT_DEG:-3.0}" \
  --min-ground-fraction "${MIN_GROUND_FRACTION:-0.15}" >/dev/null
echo "[mapping] pointcloud quality gate passed"
echo "[mapping] Super-LIO run: ${RUN_DIR}"
