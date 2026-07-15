#!/usr/bin/env bash
set -euo pipefail

PRODUCT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="${AUTORACER_PROFILE:-hooke2}"

case "${PROFILE}" in
  hooke2)
    PACKAGE_TARGETS=(autoracer_bringup autoracer_hooke2_bringup)
    ;;
  rc)
    PACKAGE_TARGETS=(autoracer_bringup autoracer_rc_bringup)
    ;;
  *)
    echo "Usage: AUTORACER_PROFILE={hooke2|rc} $0" >&2
    exit 2
    ;;
esac

AUTORACER_SOURCE_VENDOR_SETUP=true
AUTORACER_SOURCE_PRODUCT_SETUP=false
# shellcheck source=scripts/ros_env.sh
source "${PRODUCT_ROOT}/scripts/ros_env.sh"

cd "${PRODUCT_ROOT}"
colcon build \
  --base-paths src/core src/platform \
  --symlink-install \
  --parallel-workers "${COLCON_PARALLEL_WORKERS:-4}" \
  --packages-up-to "${PACKAGE_TARGETS[@]}" \
  --cmake-args -DCMAKE_BUILD_TYPE="${CMAKE_BUILD_TYPE:-Release}"
