#!/usr/bin/env bash
# Copyright 2026 OpenAI
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -euo pipefail

fail() {
  echo "RC quick start failed: $*" >&2
  exit 2
}

if [[ $# -ne 1 ]]; then
  fail "usage: $0 floor1_mapping_10[1-4]"
fi

map_id="$1"
[[ "${map_id}" =~ ^floor1_mapping_10[1-4]$ ]] || \
  fail "unsupported course '${map_id}'"

for variable in \
  RC_REPO_ROOT \
  RC_VENDOR_WS \
  RC_PRODUCT_WS \
  RC_MAP_ROOT \
  RC_SERIAL_PORT \
  RC_IMU_DEVICE; do
  [[ -n "${!variable:-}" ]] || fail "${variable} must be set explicitly"
done

repo_marker="${RC_REPO_ROOT}/src/platform/rc/autoracer_rc_bringup/launch/race.launch.py"
[[ -f "${repo_marker}" ]] || \
  fail "RC_REPO_ROOT is not the new RC product repository: ${RC_REPO_ROOT}"

map_path="${RC_MAP_ROOT}/${map_id}"
course_path="${RC_REPO_ROOT}/courses/rc/${map_id}"
[[ -f "${map_path}/map_manifest.json" ]] || \
  fail "map asset is incomplete: ${map_path}/map_manifest.json"
[[ -f "${course_path}/manifest.json" ]] || \
  fail "course asset is incomplete: ${course_path}/manifest.json"

ros_setup="${RC_ROS_SETUP:-/opt/ros/humble/setup.bash}"
vendor_setup="${RC_VENDOR_WS}/install/local_setup.bash"
product_setup="${RC_PRODUCT_WS}/install/local_setup.bash"
[[ -r "${ros_setup}" ]] || fail "ROS setup is missing: ${ros_setup}"
[[ -r "${vendor_setup}" ]] || fail "RC vendor workspace is not built: ${vendor_setup}"
[[ -r "${product_setup}" ]] || fail "RC product workspace is not built: ${product_setup}"
[[ -e "${RC_SERIAL_PORT}" ]] || fail "vehicle serial device is missing: ${RC_SERIAL_PORT}"
[[ -e "${RC_IMU_DEVICE}" ]] || fail "IMU device is missing: ${RC_IMU_DEVICE}"

# ROS-generated setup scripts are not guaranteed to be nounset-safe.
set +u
source "${ros_setup}"
source "${vendor_setup}"
source "${product_setup}"
set -u

command -v ros2 >/dev/null 2>&1 || fail "ros2 is unavailable after sourcing workspaces"

exec ros2 launch autoracer_rc_bringup race.launch.py \
  localization_map_path:="${map_path}" \
  course_path:="${course_path}" \
  serial_port:="${RC_SERIAL_PORT}" \
  imu_device:="${RC_IMU_DEVICE}" \
  launch_lidar:="${RC_LAUNCH_LIDAR:-true}" \
  launch_imu:="${RC_LAUNCH_IMU:-true}" \
  launch_rviz:="${RC_LAUNCH_RVIZ:-true}" \
  enable_drive_commands:=false
