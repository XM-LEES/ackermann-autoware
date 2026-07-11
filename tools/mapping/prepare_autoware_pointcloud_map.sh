#!/usr/bin/env bash
set -euo pipefail

RUN_ID="${1:?usage: prepare_autoware_pointcloud_map.sh <run_id> <map_name> [lanelet2_map.osm]}"
MAP_NAME="${2:?usage: prepare_autoware_pointcloud_map.sh <run_id> <map_name> [lanelet2_map.osm]}"
LANELET2_MAP="${3:-}"
MAPPING_WS="${MAPPING_WS:-/home/milesli/Desktop/RC/rc_mapping_ws}"
MAPPING_DATA_DIR="${MAPPING_DATA_DIR:-/home/milesli/Desktop/RC/rc_mapping_data}"
SOURCE_PCD="${SOURCE_PCD:-${MAPPING_DATA_DIR}/runs/${RUN_ID}/map/map.pcd}"
OUTPUT_ROOT="${MAPPING_DATA_DIR}/autoware_maps"
OUTPUT_DIR="${OUTPUT_ROOT}/${MAP_NAME}"
LEAF_SIZE="${LEAF_SIZE:--0.1}"
GRID_SIZE="${GRID_SIZE:-20.0}"

[[ -f "${SOURCE_PCD}" ]] || { echo "ERROR: source PCD not found: ${SOURCE_PCD}" >&2; exit 1; }
[[ "${MAP_NAME}" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "ERROR: invalid map name: ${MAP_NAME}" >&2; exit 1; }
if [[ -e "${OUTPUT_DIR}" && "${REPLACE_EXISTING_MAP:-false}" != "true" ]]; then
  echo "ERROR: map already exists: ${OUTPUT_DIR}" >&2
  echo "Set REPLACE_EXISTING_MAP=true only after reviewing the existing map." >&2
  exit 1
fi
if [[ -n "${LANELET2_MAP}" && ! -f "${LANELET2_MAP}" ]]; then
  echo "ERROR: Lanelet2 map not found: ${LANELET2_MAP}" >&2
  exit 1
fi

mkdir -p "${OUTPUT_ROOT}"
quality_report="$(mktemp)"
STAGING_DIR="$(mktemp -d "${OUTPUT_ROOT}/.${MAP_NAME}.XXXXXX")"
cleanup() {
  rm -f "${quality_report}"
  if [[ -n "${STAGING_DIR}" && -d "${STAGING_DIR}" ]]; then
    rm -rf "${STAGING_DIR}"
  fi
}
trap cleanup EXIT
"$(dirname "${BASH_SOURCE[0]}")/audit_pointcloud_map.py" "${SOURCE_PCD}" \
  --output "${quality_report}" \
  --max-ground-tilt-deg "${MAX_GROUND_TILT_DEG:-3.0}" \
  --min-ground-fraction "${MIN_GROUND_FRACTION:-0.15}" >/dev/null
echo "[mapping] pointcloud quality gate passed"

set +u
source "/opt/ros/${ROS_DISTRO:-humble}/setup.bash"
source "${MAPPING_WS}/install/setup.bash"
set -u
ros2 pkg prefix autoware_pointcloud_divider >/dev/null

ros2 launch autoware_pointcloud_divider pointcloud_divider.launch.xml \
  input_pcd_or_dir:="$(realpath "${SOURCE_PCD}")" \
  output_pcd_dir:="$(realpath "${STAGING_DIR}")" \
  prefix:="${MAP_NAME}" \
  point_type:=point_xyzi \
  leaf_size:="${LEAF_SIZE}" \
  grid_size_x:="${GRID_SIZE}" \
  grid_size_y:="${GRID_SIZE}"

[[ -f "${STAGING_DIR}/pointcloud_map_metadata.yaml" ]] || {
  echo "ERROR: pointcloud_map_metadata.yaml was not generated." >&2
  exit 1
}
find "${STAGING_DIR}/pointcloud_map.pcd" -type f -name '*.pcd' -print -quit | grep -q . || {
  echo "ERROR: divided PCD tiles were not generated." >&2
  exit 1
}
"$(dirname "${BASH_SOURCE[0]}")/validate_pointcloud_metadata.py" "${STAGING_DIR}"
printf 'projector_type: Local\n' > "${STAGING_DIR}/map_projector_info.yaml"
install -m 0644 "${quality_report}" "${STAGING_DIR}/quality_report.json"
if [[ -n "${LANELET2_MAP}" ]]; then
  cp "${LANELET2_MAP}" "${STAGING_DIR}/lanelet2_map.osm"
fi

if [[ -e "${OUTPUT_DIR}" ]]; then
  rm -rf "${OUTPUT_DIR}"
fi
mv "${STAGING_DIR}" "${OUTPUT_DIR}"
STAGING_DIR=""

echo "[mapping] Autoware pointcloud map: ${OUTPUT_DIR}"
if [[ ! -f "${OUTPUT_DIR}/lanelet2_map.osm" ]]; then
  echo "[mapping] localization-only until lanelet2_map.osm is added and reviewed"
fi
