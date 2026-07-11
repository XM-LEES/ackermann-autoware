#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  VEHICLE_HOST=<user@host> VEHICLE_BAG=<remote_bag_dir> pull_mapping_bag.sh

Environment:
  VEHICLE_HOST      required vehicle SSH target
  VEHICLE_BAG       required remote bag directory
  MAPPING_DATA_DIR  default: <repo-parent>/rc_mapping_data
  DEST_DIR          default: ${MAPPING_DATA_DIR}/bags/raw

Pulls a vehicle-side mapping bag into the workstation raw-bag archive.
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

VEHICLE_HOST="${VEHICLE_HOST:?set VEHICLE_HOST, for example user@host}"
VEHICLE_BAG="${VEHICLE_BAG:?set VEHICLE_BAG to the remote bag directory}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MAPPING_DATA_DIR="${MAPPING_DATA_DIR:-$(dirname "${ROOT_DIR}")/rc_mapping_data}"
DEST_DIR="${DEST_DIR:-${MAPPING_DATA_DIR}/bags/raw}"

mkdir -p "${DEST_DIR}"
echo "[mapping-bag] pulling ${VEHICLE_HOST}:${VEHICLE_BAG} -> ${DEST_DIR}"
rsync -av --progress "${VEHICLE_HOST}:${VEHICLE_BAG}" "${DEST_DIR}/"
