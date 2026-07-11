#!/usr/bin/env bash
set -euo pipefail

TOOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${TOOL_DIR}/../.." && pwd)"
MAPPING_WS="${MAPPING_WS:-$(dirname "${REPO_ROOT}")/rc_mapping_ws}"
ROS_DISTRO="${ROS_DISTRO:-humble}"
LIVOX_SDK_PREFIX="${MAPPING_WS}/third_party/livox_sdk2_install"

command -v vcs >/dev/null || {
  echo "ERROR: vcs is required (package: python3-vcstool)." >&2
  exit 1
}
command -v colcon >/dev/null || {
  echo "ERROR: colcon is required." >&2
  exit 1
}

mkdir -p "${MAPPING_WS}"
vcs import "${MAPPING_WS}" < "${TOOL_DIR}/mapping.repos"
touch "${MAPPING_WS}/third_party/COLCON_IGNORE"

declare -A expected_commits=(
  ["${MAPPING_WS}/src/Super-LIO"]="42a61372e02feaf656f84cdf3b5b793ff06d7ed4"
  ["${MAPPING_WS}/src/livox_ros_driver2"]="13eb05e4e6dd7a765b934d0c5fd6236676a57b49"
  ["${MAPPING_WS}/src/autoware_tools"]="2b5e7ed4c4a6e7a93f7aa4f46d6c75359c9e9b26"
  ["${MAPPING_WS}/src/autoware_cmake"]="0e0794e034fe1b8fea6e3a0bbcb9d9b8cdba03ad"
  ["${MAPPING_WS}/third_party/Livox-SDK2"]="f5d9375f84efe2b15bc0a052d3e18482ed13adf4"
)
for repo in "${!expected_commits[@]}"; do
  actual="$(git -C "${repo}" rev-parse HEAD)"
  if [[ "${actual}" != "${expected_commits[${repo}]}" ]]; then
    echo "ERROR: unexpected revision in ${repo}: ${actual}" >&2
    exit 1
  fi
done

livox_driver="${MAPPING_WS}/src/livox_ros_driver2"
cp -f "${livox_driver}/package_ROS2.xml" "${livox_driver}/package.xml"
rm -rf "${livox_driver}/launch"
cp -a "${livox_driver}/launch_ROS2" "${livox_driver}/launch"

if [[ ! -f "${LIVOX_SDK_PREFIX}/lib/liblivox_lidar_sdk_shared.so" ]]; then
  sdk="${MAPPING_WS}/third_party/Livox-SDK2"
  cmake -S "${sdk}" -B "${sdk}/build" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="${LIVOX_SDK_PREFIX}"
  cmake --build "${sdk}/build" -j"${BUILD_JOBS:-2}"
  cmake --install "${sdk}/build"
fi

set +u
source "/opt/ros/${ROS_DISTRO}/setup.bash"
set -u
export CMAKE_PREFIX_PATH="${LIVOX_SDK_PREFIX}:${CMAKE_PREFIX_PATH:-}"

cd "${MAPPING_WS}"
colcon build \
  --symlink-install \
  --packages-up-to super_lio autoware_pointcloud_divider \
  --cmake-args -DCMAKE_BUILD_TYPE=Release -DROS_EDITION=ROS2 -DDISTRO_ROS="${ROS_DISTRO}"

echo "[mapping] workspace ready: ${MAPPING_WS}"
