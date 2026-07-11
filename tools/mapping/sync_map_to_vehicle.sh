#!/usr/bin/env bash
set -euo pipefail

MAP_NAME="${1:?usage: sync_map_to_vehicle.sh <map_name>}"
VEHICLE_HOST="${VEHICLE_HOST:?set VEHICLE_HOST, for example user@vehicle-host}"
VEHICLE_MAP_DIR="${VEHICLE_MAP_DIR:-/home/wheeltec/Desktop/autoracer_hooke/maps}"
TOOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${TOOL_DIR}/../.." && pwd)"
MAPPING_DATA_DIR="${MAPPING_DATA_DIR:-$(dirname "${REPO_ROOT}")/rc_mapping_data}"
SOURCE_DIR="${MAPPING_DATA_DIR}/autoware_maps/${MAP_NAME}"

for asset in pointcloud_map_metadata.yaml lanelet2_map.osm map_projector_info.yaml; do
  [[ -f "${SOURCE_DIR}/${asset}" ]] || { echo "ERROR: missing map asset: ${SOURCE_DIR}/${asset}" >&2; exit 1; }
done
if [[ ! -f "${SOURCE_DIR}/pointcloud_map.pcd" && ! -d "${SOURCE_DIR}/pointcloud_map.pcd" ]]; then
  echo "ERROR: missing pointcloud_map.pcd file or tile directory in ${SOURCE_DIR}" >&2
  exit 1
fi
"${TOOL_DIR}/validate_pointcloud_metadata.py" "${SOURCE_DIR}"

ssh "${VEHICLE_HOST}" mkdir -p "${VEHICLE_MAP_DIR}/${MAP_NAME}"
rsync -av --delete "${SOURCE_DIR}/" "${VEHICLE_HOST}:${VEHICLE_MAP_DIR}/${MAP_NAME}/"
echo "[mapping] vehicle MAP_PATH=${VEHICLE_MAP_DIR}/${MAP_NAME}"
