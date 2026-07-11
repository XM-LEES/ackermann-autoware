#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

usage() {
  cat <<'EOF'
Usage:
  MAP_PATH=<map_dir> rc_start_localization.sh

Environment:
  MAP_PATH       required map directory
  LAUNCH_RVIZ    default: true

Starts official sensing + map + localization plus the official API/RViz
initial-pose adaptor. Planning, perception, control, and vehicle interface are
disabled for PCD/localization checks.
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

if [[ -z "${MAP_PATH:-}" ]]; then
  echo "ERROR: MAP_PATH is required." >&2
  usage >&2
  exit 1
fi

export LAUNCH_VEHICLE="${LAUNCH_VEHICLE:-true}"
export LAUNCH_VEHICLE_INTERFACE=false
export LAUNCH_SENSING="${LAUNCH_SENSING:-true}"
export LAUNCH_SENSING_DRIVER="${LAUNCH_SENSING_DRIVER:-true}"
export LAUNCH_MAP="${LAUNCH_MAP:-true}"
export LAUNCH_SYSTEM="${LAUNCH_SYSTEM:-false}"
export LAUNCH_SYSTEM_MONITOR="${LAUNCH_SYSTEM_MONITOR:-false}"
export LAUNCH_LOCALIZATION="${LAUNCH_LOCALIZATION:-true}"
export LAUNCH_PERCEPTION="${LAUNCH_PERCEPTION:-false}"
export LAUNCH_PLANNING=false
export LAUNCH_CONTROL=false
export LAUNCH_API="${LAUNCH_API:-true}"
export LAUNCH_RVIZ="${LAUNCH_RVIZ:-true}"
export ENABLE_DRIVE_COMMANDS="${ENABLE_DRIVE_COMMANDS:-false}"

exec ./scripts/run_official_autoware.sh
