#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/ros_env.sh
source "$ROOT_DIR/scripts/ros_env.sh"

SERVICE_TYPE="autoware_adapi_v1_msgs/srv/ChangeOperationMode"
STATE_TYPE="autoware_adapi_v1_msgs/msg/OperationModeState"
STATE_TOPIC="/api/operation_mode/state"
ROS2_CLI="${ROS2_CLI:-ros2}"
SERVICE_TIMEOUT_SEC="${SERVICE_TIMEOUT_SEC:-10}"
AUTONOMOUS_MODE_TIMEOUT_SEC="${AUTONOMOUS_MODE_TIMEOUT_SEC:-20}"

call_operation_service() {
  local service_name="$1"
  local output

  if ! output="$(timeout "${SERVICE_TIMEOUT_SEC}" \
    "${ROS2_CLI}" service call "${service_name}" "${SERVICE_TYPE}" "{}" 2>&1)"; then
    printf '%s\n' "${output}" >&2
    echo "ERROR: operation-mode service failed or timed out: ${service_name}" >&2
    return 1
  fi

  printf '%s\n' "${output}"
  if ! grep -Eqi 'success[=:][[:space:]]*true' <<<"${output}"; then
    echo "ERROR: operation-mode service rejected the request: ${service_name}" >&2
    return 1
  fi
}

wait_for_operation_state() {
  local description="$1"
  local filter_expression="$2"

  if ! timeout "${AUTONOMOUS_MODE_TIMEOUT_SEC}" \
    "${ROS2_CLI}" topic echo \
      --qos-durability transient_local \
      --once \
      --filter "${filter_expression}" \
      "${STATE_TOPIC}" "${STATE_TYPE}" >/dev/null; then
    echo "ERROR: timed out waiting for ${description} after ${AUTONOMOUS_MODE_TIMEOUT_SEC}s." >&2
    echo "Check localization, route, planning, control, safety, and operation-mode diagnostics." >&2
    return 1
  fi
}

call_operation_service "/api/operation_mode/enable_autoware_control"
wait_for_operation_state \
  "stable Autoware control" \
  'm.is_autoware_control_enabled and not m.is_in_transition'

call_operation_service "/api/operation_mode/change_to_autonomous"
wait_for_operation_state \
  "stable autonomous operation mode" \
  'm.mode == 2 and m.is_autoware_control_enabled and not m.is_in_transition'

echo "[rc-mode] Autoware control is enabled and operation mode is autonomous"
