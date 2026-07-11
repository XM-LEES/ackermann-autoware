#!/usr/bin/env bash
set -euo pipefail

if (( EUID != 0 )); then
  echo "ERROR: run this configurator with sudo -E." >&2
  exit 1
fi

TOOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYSCTL_SOURCE="${TOOL_DIR}/autoracer-dds.conf"
SYSCTL_PATH="/etc/sysctl.d/60-autoracer-dds.conf"

[[ -f "${SYSCTL_SOURCE}" ]] || {
  echo "ERROR: missing DDS sysctl configuration: ${SYSCTL_SOURCE}" >&2
  exit 1
}

install -m 0644 "${SYSCTL_SOURCE}" "${SYSCTL_PATH}"
sysctl -p "${SYSCTL_PATH}"
ip link set dev lo multicast on
"${TOOL_DIR}/install_traffic_reader_service.sh"

[[ "$(sysctl -n net.core.rmem_max)" == "2147483647" ]]
[[ "$(sysctl -n net.core.rmem_default)" == "134217728" ]]
[[ "$(sysctl -n net.ipv4.ipfrag_time)" == "3" ]]
[[ "$(sysctl -n net.ipv4.ipfrag_high_thresh)" == "134217728" ]]
ip link show dev lo | grep -q MULTICAST
systemctl is-active --quiet autoracer-traffic-reader.service
test -S /tmp/traffic_reader

echo "[system] onboard DDS and Autoware monitor prerequisites are ready"
