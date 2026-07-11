#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  rc_stop.sh

Stops the RC runtime recorded by the formal start scripts. The command signals
only the tracked launch process and its descendants; it does not scan or stop
unrelated ROS processes owned by the same user.
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

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RC_RUNTIME_DIR="${RC_RUNTIME_DIR:-/tmp/autoracer_rc}"
RC_RUNTIME_STATE_FILE="${RC_RUNTIME_STATE_FILE:-${RC_RUNTIME_DIR}/autoware.env}"
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

process_matches_identity() {
  local pid="$1"
  local expected_ticks="$2"
  local current_ticks

  [[ "${pid}" =~ ^[0-9]+$ && "${expected_ticks}" =~ ^[0-9]+$ ]] || return 1
  [[ -d "/proc/${pid}" ]] || return 1
  [[ "$(stat -c '%u' "/proc/${pid}")" == "${CURRENT_UID}" ]] || return 1
  [[ "$(process_state "${pid}" 2>/dev/null || true)" != "Z" ]] || return 1
  current_ticks="$(process_start_ticks "${pid}" 2>/dev/null || true)"
  [[ -n "${current_ticks}" && "${current_ticks}" == "${expected_ticks}" ]]
}

collect_process_tree() {
  local pid="$1"
  local child

  process_start_ticks "${pid}" >/dev/null 2>&1 || return 0
  printf '%s\n' "${pid}"
  # Tegra kernels can omit /proc/.../children; pgrep -P uses the same exact PPID relation.
  while IFS= read -r child; do
    [[ -n "${child}" ]] || continue
    collect_process_tree "${child}"
  done < <(pgrep -P "${pid}" 2>/dev/null || true)
}

declare -a TRACKED_PIDS=()
declare -A TRACKED_TICKS=()

track_current_tree() {
  local pid ticks
  while IFS= read -r pid; do
    [[ -n "${pid}" ]] || continue
    ticks="$(process_start_ticks "${pid}" 2>/dev/null || true)"
    [[ -n "${ticks}" ]] || continue
    if [[ -z "${TRACKED_TICKS[${pid}]+x}" ]]; then
      TRACKED_PIDS+=("${pid}")
      TRACKED_TICKS["${pid}"]="${ticks}"
    fi
  done < <(collect_process_tree "${PID}")
}

any_tracked_process_alive() {
  local pid
  for pid in "${TRACKED_PIDS[@]}"; do
    if process_matches_identity "${pid}" "${TRACKED_TICKS[${pid}]}"; then
      return 0
    fi
  done
  return 1
}

wait_for_tracked_processes() {
  local timeout_sec="$1"
  local ticks=$((timeout_sec * 5))
  local tick

  for ((tick = 0; tick < ticks; tick++)); do
    any_tracked_process_alive || return 0
    sleep 0.2
  done
  ! any_tracked_process_alive
}

signal_tracked_processes() {
  local signal_name="$1"
  local index pid

  for ((index = ${#TRACKED_PIDS[@]} - 1; index >= 0; index--)); do
    pid="${TRACKED_PIDS[${index}]}"
    if process_matches_identity "${pid}" "${TRACKED_TICKS[${pid}]}"; then
      kill "-${signal_name}" "${pid}" 2>/dev/null || true
    fi
  done
}

if [[ ! -f "${RC_RUNTIME_STATE_FILE}" ]]; then
  echo "[rc-stop] no tracked RC runtime"
  exit 0
fi

if [[ "$(stat -c '%u' "${RC_RUNTIME_STATE_FILE}")" != "${CURRENT_UID}" ]]; then
  echo "ERROR: runtime state is not owned by the current user: ${RC_RUNTIME_STATE_FILE}" >&2
  exit 1
fi

PID="$(sed -n 's/^PID=//p' "${RC_RUNTIME_STATE_FILE}" | head -n 1)"
START_TICKS="$(sed -n 's/^START_TICKS=//p' "${RC_RUNTIME_STATE_FILE}" | head -n 1)"
STATE_ROOT="$(sed -n 's/^ROOT_DIR=//p' "${RC_RUNTIME_STATE_FILE}" | head -n 1)"

if [[ "${STATE_ROOT}" != "${ROOT_DIR}" ]]; then
  echo "ERROR: runtime state belongs to another checkout: ${STATE_ROOT:-unset}" >&2
  exit 1
fi

if ! process_matches_identity "${PID}" "${START_TICKS}"; then
  rm -f "${RC_RUNTIME_STATE_FILE}"
  echo "[rc-stop] no tracked RC runtime; removed stale state"
  exit 0
fi

track_current_tree
echo "[rc-stop] stopping tracked RC runtime pid ${PID}"
kill -INT "${PID}" 2>/dev/null || true

if ! wait_for_tracked_processes "${INTERRUPT_GRACE_SEC:-10}"; then
  track_current_tree
  echo "[rc-stop] graceful shutdown timed out; sending SIGTERM"
  signal_tracked_processes TERM
fi

if ! wait_for_tracked_processes "${SHUTDOWN_GRACE_SEC:-20}"; then
  track_current_tree
  echo "[rc-stop] shutdown timed out; sending SIGKILL"
  signal_tracked_processes KILL
fi

if ! wait_for_tracked_processes "${KILL_GRACE_SEC:-2}"; then
  echo "ERROR: tracked RC processes remain after shutdown" >&2
  exit 1
fi

rm -f "${RC_RUNTIME_STATE_FILE}"
echo "[rc-stop] RC runtime processes stopped"
