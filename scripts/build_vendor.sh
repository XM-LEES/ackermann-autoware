#!/usr/bin/env bash
set -euo pipefail

PRODUCT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="${AUTORACER_PROFILE:-hooke2}"
RESOLVER="${PRODUCT_ROOT}/scripts/vendor/resolve_dependencies.py"
VENDOR_WS="${AUTORACER_VENDOR_WS:-${PRODUCT_ROOT}/vendor_ws}"

if [[ "${PROFILE}" != "hooke2" && -z "${AUTORACER_VENDOR_WS:-}" ]]; then
  echo "AUTORACER_VENDOR_WS is required for non-Hooke profile ${PROFILE}" >&2
  exit 2
fi

AUTORACER_SOURCE_VENDOR_SETUP=false
AUTORACER_SOURCE_PRODUCT_SETUP=false
# shellcheck source=scripts/ros_env.sh
source "${PRODUCT_ROOT}/scripts/ros_env.sh"

mapfile -t packages < <(python3 "${RESOLVER}" --profile "${PROFILE}" --format names)
if ((${#packages[@]} == 0)); then
  echo "No packages resolved for profile ${PROFILE}" >&2
  exit 1
fi

underlay_overrides=(
  autoware_adapi_v1_msgs
  autoware_internal_planning_msgs
  autoware_lanelet2_extension
  autoware_map_msgs
  autoware_perception_msgs
  autoware_planning_msgs
  autoware_utils_geometry
)

cmake_build_type="${CMAKE_BUILD_TYPE:-Release}"
cmake_cxx_flags="${CMAKE_CXX_FLAGS:-} -I${VENDOR_WS}/install/autoware_lanelet2_extension/include"

cd "${VENDOR_WS}"
colcon build \
  --symlink-install \
  --parallel-workers "${COLCON_PARALLEL_WORKERS:-4}" \
  --allow-overriding "${underlay_overrides[@]}" \
  --packages-select "${packages[@]}" \
  --cmake-args \
    -DBUILD_TESTING=OFF \
    -DCMAKE_BUILD_TYPE="${cmake_build_type}" \
    -DCMAKE_CXX_FLAGS="${cmake_cxx_flags}"
