#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

usage() {
  cat <<'EOF'
Usage:
  rc_stop_mapping_bag.sh

Environment:
  RC_RUNTIME_DIR          runtime state directory, default: /tmp/autoracer_rc
  RC_MAPPING_STATE_FILE   state file from rc_start_mapping_bag.sh

Stops the active mapping bag gracefully, stops the RC sensing stack, prints
rosbag metadata, and removes the runtime state file.
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

RC_RUNTIME_DIR="${RC_RUNTIME_DIR:-/tmp/autoracer_rc}"
STATE_FILE="${RC_MAPPING_STATE_FILE:-${RC_RUNTIME_DIR}/mapping_bag.env}"
BAG_STOP_GRACE_SEC="${BAG_STOP_GRACE_SEC:-20}"
BAG_TERM_GRACE_SEC="${BAG_TERM_GRACE_SEC:-5}"
BAG_KILL_GRACE_SEC="${BAG_KILL_GRACE_SEC:-2}"
SENSOR_TERM_GRACE_SEC="${SENSOR_TERM_GRACE_SEC:-5}"
SENSOR_KILL_GRACE_SEC="${SENSOR_KILL_GRACE_SEC:-2}"
CURRENT_UID="$(id -u)"

process_start_ticks() {
  local pid="$1"
  [[ -r "/proc/${pid}/stat" ]] || return 1
  awk '{print $22}' "/proc/${pid}/stat"
}

process_state() {
  local pid="$1"
  [[ -r "/proc/${pid}/stat" ]] || return 1
  awk '{print $3}' "/proc/${pid}/stat"
}

process_group_id() {
  local pid="$1"
  ps -o pgid= -p "${pid}" 2>/dev/null | tr -d '[:space:]'
}

process_matches_identity() {
  local pid="$1"
  local expected_ticks="$2"
  local expected_pgid="$3"
  local current_ticks current_pgid

  [[ "${pid}" =~ ^[0-9]+$ && "${expected_ticks}" =~ ^[0-9]+$ ]] || return 1
  [[ "${expected_pgid}" =~ ^[0-9]+$ && "${expected_pgid}" == "${pid}" ]] || return 1
  [[ -d "/proc/${pid}" ]] || return 1
  [[ "$(stat -c '%u' "/proc/${pid}")" == "${CURRENT_UID}" ]] || return 1
  [[ "$(process_state "${pid}" 2>/dev/null || true)" != "Z" ]] || return 1
  current_ticks="$(process_start_ticks "${pid}" 2>/dev/null || true)"
  current_pgid="$(process_group_id "${pid}" 2>/dev/null || true)"
  [[ "${current_ticks}" == "${expected_ticks}" && "${current_pgid}" == "${expected_pgid}" ]]
}

wait_for_process_exit() {
  local pid="$1"
  local expected_ticks="$2"
  local expected_pgid="$3"
  local timeout_sec="$4"
  local ticks=$((timeout_sec * 5))
  local tick
  for ((tick = 0; tick < ticks; tick++)); do
    process_matches_identity "${pid}" "${expected_ticks}" "${expected_pgid}" || return 0
    sleep 0.2
  done
  ! process_matches_identity "${pid}" "${expected_ticks}" "${expected_pgid}"
}

signal_process_group() {
  local signal_name="$1"
  local pid="$2"
  local expected_ticks="$3"
  local expected_pgid="$4"

  process_matches_identity "${pid}" "${expected_ticks}" "${expected_pgid}" || return 1
  kill "-${signal_name}" -- "-${expected_pgid}" 2>/dev/null
}

if [[ ! -f "$STATE_FILE" ]]; then
  echo "ERROR: no active mapping bag state file: ${STATE_FILE}" >&2
  exit 1
fi

if [[ "$(stat -c '%u' "${STATE_FILE}")" != "${CURRENT_UID}" ]]; then
  echo "ERROR: mapping state is not owned by the current user: ${STATE_FILE}" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$STATE_FILE"

if [[ "${OWNER_UID:-}" != "${CURRENT_UID}" || "${ROOT_DIR:-}" != "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)" ]]; then
  echo "ERROR: mapping state owner or repository root does not match the current checkout." >&2
  exit 1
fi

recorder_stop_status=0
if [[ -n "${REC_PID:-}" ]] && process_matches_identity \
  "${REC_PID}" "${REC_START_TICKS:-}" "${REC_PGID:-}"; then
  echo "[rc-bag] stopping recorder pid ${REC_PID}"
  signal_process_group INT "${REC_PID}" "${REC_START_TICKS}" "${REC_PGID}" || true
  if ! wait_for_process_exit \
    "${REC_PID}" "${REC_START_TICKS}" "${REC_PGID}" "${BAG_STOP_GRACE_SEC}"; then
    echo "[rc-bag] recorder did not stop after SIGINT; sending SIGTERM" >&2
    signal_process_group TERM "${REC_PID}" "${REC_START_TICKS}" "${REC_PGID}" || true
  fi
  if ! wait_for_process_exit \
    "${REC_PID}" "${REC_START_TICKS}" "${REC_PGID}" "${BAG_TERM_GRACE_SEC}"; then
    echo "[rc-bag] recorder did not stop after SIGTERM; sending SIGKILL" >&2
    signal_process_group KILL "${REC_PID}" "${REC_START_TICKS}" "${REC_PGID}" || true
  fi
  if ! wait_for_process_exit \
    "${REC_PID}" "${REC_START_TICKS}" "${REC_PGID}" "${BAG_KILL_GRACE_SEC}"; then
    echo "ERROR: rosbag recorder remains active: ${REC_PID}" >&2
    recorder_stop_status=1
  fi
elif [[ -n "${REC_PID:-}" ]] && kill -0 "${REC_PID}" 2>/dev/null; then
  echo "ERROR: recorder identity mismatch; refusing to signal pid ${REC_PID}." >&2
  recorder_stop_status=1
fi

runtime_stop_status=0
./scripts/rc/rc_stop.sh || runtime_stop_status=$?

sensor_stop_status=0
if [[ -n "${SENSOR_PID:-}" ]] && process_matches_identity \
  "${SENSOR_PID}" "${SENSOR_START_TICKS:-}" "${SENSOR_PGID:-}"; then
  echo "[rc-bag] tracked shutdown did not stop sensor pid ${SENSOR_PID}; using owned process-group fallback" >&2
  signal_process_group TERM "${SENSOR_PID}" "${SENSOR_START_TICKS}" "${SENSOR_PGID}" || true
  if ! wait_for_process_exit \
    "${SENSOR_PID}" "${SENSOR_START_TICKS}" "${SENSOR_PGID}" "${SENSOR_TERM_GRACE_SEC}"; then
    echo "[rc-bag] sensor stack did not stop after SIGTERM; sending SIGKILL" >&2
    signal_process_group KILL "${SENSOR_PID}" "${SENSOR_START_TICKS}" "${SENSOR_PGID}" || true
  fi
  if ! wait_for_process_exit \
    "${SENSOR_PID}" "${SENSOR_START_TICKS}" "${SENSOR_PGID}" "${SENSOR_KILL_GRACE_SEC}"; then
    echo "ERROR: sensor stack remains active: ${SENSOR_PID}" >&2
    sensor_stop_status=1
  fi
elif [[ -n "${SENSOR_PID:-}" ]] && kill -0 "${SENSOR_PID}" 2>/dev/null; then
  echo "ERROR: sensor identity mismatch; refusing to signal pid ${SENSOR_PID}." >&2
  sensor_stop_status=1
fi

# shellcheck source=scripts/ros_env.sh
source "$ROOT_DIR/scripts/ros_env.sh"

if [[ -n "${BAG_PATH:-}" && -d "$BAG_PATH" ]]; then
  echo "[rc-bag] bag info: ${BAG_PATH}"
  ros2 bag info "$BAG_PATH"
else
  echo "[rc-bag] warning: bag path was not found: ${BAG_PATH:-unset}" >&2
fi

rm -f "$STATE_FILE"
echo "[rc-bag] sensor log: ${SENSOR_LOG:-unknown}"
echo "[rc-bag] record log: ${RECORD_LOG:-unknown}"
echo "[rc-bag] stopped"

if ((recorder_stop_status != 0 || runtime_stop_status != 0 || sensor_stop_status != 0)); then
  exit 1
fi
