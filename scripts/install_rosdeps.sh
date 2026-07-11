#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

AUTORACER_SOURCE_LOCAL_SETUP=false
# shellcheck source=scripts/ros_env.sh
source "$ROOT_DIR/scripts/ros_env.sh"

ROSDEP_SOURCES_LIST="${ROSDEP_SOURCES_LIST:-/etc/ros/rosdep/sources.list.d/20-default.list}"
if ! command -v rosdep >/dev/null 2>&1; then
  echo "ERROR: rosdep is required. Install python3-rosdep first." >&2
  exit 1
fi
if [[ ! -r "${ROSDEP_SOURCES_LIST}" ]]; then
  echo "ERROR: rosdep is not initialized; missing ${ROSDEP_SOURCES_LIST}." >&2
  echo "Run once: sudo rosdep init" >&2
  exit 1
fi

rosdep update
rosdep install --from-paths src --ignore-src -y -r
