#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="${AUTORACER_PROFILE:-hooke2}"
VENDOR_WS="${AUTORACER_VENDOR_WS:-${ROOT_DIR}/vendor_ws}"

case "${PROFILE}" in
  hooke2) PLATFORM_ROOT="${ROOT_DIR}/src/platform/hooke2" ;;
  rc) PLATFORM_ROOT="${ROOT_DIR}/src/platform/rc" ;;
  *) echo "Usage: AUTORACER_PROFILE={hooke2|rc} $0" >&2; exit 2 ;;
esac

if [[ "${PROFILE}" != "hooke2" && -z "${AUTORACER_VENDOR_WS:-}" ]]; then
  echo "AUTORACER_VENDOR_WS is required for non-Hooke profile ${PROFILE}" >&2
  exit 2
fi
cd "${ROOT_DIR}"

AUTORACER_SOURCE_VENDOR_SETUP=false
AUTORACER_SOURCE_PRODUCT_SETUP=false
# shellcheck source=scripts/ros_env.sh
source "${ROOT_DIR}/scripts/ros_env.sh"
rosdep update
rosdep install --from-paths \
  "${VENDOR_WS}/src" \
  "${ROOT_DIR}/src/core" \
  "${PLATFORM_ROOT}" \
  --ignore-src -y -r
