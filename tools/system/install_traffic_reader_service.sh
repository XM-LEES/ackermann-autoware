#!/usr/bin/env bash
set -euo pipefail

if (( EUID != 0 )); then
  echo "ERROR: run this installer with sudo -E." >&2
  exit 1
fi

TOOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${TOOL_DIR}/../.." && pwd)"
UNIT_NAME="autoracer-traffic-reader.service"
UNIT_TEMPLATE="${TOOL_DIR}/${UNIT_NAME}.in"
UNIT_PATH="/etc/systemd/system/${UNIT_NAME}"
WORKSPACE_SETUP="${WORKSPACE_SETUP:-${REPO_ROOT}/install/setup.bash}"

[[ -f "${UNIT_TEMPLATE}" ]] || {
  echo "ERROR: missing service template: ${UNIT_TEMPLATE}" >&2
  exit 1
}
[[ -f "${WORKSPACE_SETUP}" ]] || {
  echo "ERROR: build the workspace first; missing ${WORKSPACE_SETUP}" >&2
  exit 1
}

if ! command -v nethogs >/dev/null 2>&1; then
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y nethogs
fi

set +u
source "/opt/ros/${ROS_DISTRO:-humble}/setup.bash"
source "${WORKSPACE_SETUP}"
set -u

package_prefix="$(ros2 pkg prefix autoware_system_monitor)"
traffic_reader="${package_prefix}/lib/autoware_system_monitor/traffic_reader"
[[ -x "${traffic_reader}" ]] || {
  echo "ERROR: traffic_reader is not executable: ${traffic_reader}" >&2
  exit 1
}

rendered_unit="$(mktemp)"
trap 'rm -f "${rendered_unit}"' EXIT
escaped_binary="${traffic_reader//&/\\&}"
sed "s|@TRAFFIC_READER_BINARY@|${escaped_binary}|g" \
  "${UNIT_TEMPLATE}" > "${rendered_unit}"
install -m 0644 "${rendered_unit}" "${UNIT_PATH}"

systemctl daemon-reload
systemctl enable --now "${UNIT_NAME}"

for _ in $(seq 1 50); do
  test -S /tmp/traffic_reader && break
  sleep 0.1
done
systemctl is-active --quiet "${UNIT_NAME}"
test -S /tmp/traffic_reader

echo "[system] ${UNIT_NAME} is active; socket=/tmp/traffic_reader"
