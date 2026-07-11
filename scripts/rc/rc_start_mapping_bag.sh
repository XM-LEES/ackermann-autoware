#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

usage() {
  cat <<'EOF'
Usage:
  rc_start_mapping_bag.sh

Environment:
  RUN_ID             mapping run id, default: rc_mapping_<timestamp>
  BAG_ROOT           bag root on the vehicle host, default: ~/autoracer_mapping_bags
  BAG_PATH           full bag output path, default: ${BAG_ROOT}/${RUN_ID}
  SENSOR_WARMUP_SEC  seconds to wait before input check, default: 16
  RC_RUNTIME_DIR     runtime state directory, default: /tmp/autoracer_rc

Starts RC C32/IMU/TF, verifies mapping inputs, then records the formal mapping
bag in the background. Finish with scripts/rc/rc_stop_mapping_bag.sh.
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

RUN_ID="${RUN_ID:-rc_mapping_$(date +%Y%m%d_%H%M%S)}"
BAG_ROOT="${BAG_ROOT:-${HOME}/autoracer_mapping_bags}"
BAG_PATH="${BAG_PATH:-${BAG_ROOT}/${RUN_ID}}"
SENSOR_WARMUP_SEC="${SENSOR_WARMUP_SEC:-16}"
RC_RUNTIME_DIR="${RC_RUNTIME_DIR:-/tmp/autoracer_rc}"
STATE_FILE="${RC_MAPPING_STATE_FILE:-${RC_RUNTIME_DIR}/mapping_bag.env}"
LOG_ROOT="${LOG_ROOT:-/tmp}"
SENSOR_LOG="${SENSOR_LOG:-${LOG_ROOT}/${RUN_ID}_sensors.log}"
RECORD_LOG="${RECORD_LOG:-${LOG_ROOT}/${RUN_ID}_record.log}"

mkdir -p "$RC_RUNTIME_DIR"
chmod 0700 "$RC_RUNTIME_DIR"

process_start_ticks() {
  local pid="$1"
  [[ -r "/proc/${pid}/stat" ]] || return 1
  awk '{print $22}' "/proc/${pid}/stat"
}

process_group_id() {
  local pid="$1"
  ps -o pgid= -p "${pid}" 2>/dev/null | tr -d '[:space:]'
}

capture_owned_process_group() {
  local pid="$1"
  local label="$2"
  local ticks pgid
  for _ in $(seq 1 20); do
    ticks="$(process_start_ticks "${pid}" 2>/dev/null || true)"
    pgid="$(process_group_id "${pid}" 2>/dev/null || true)"
    if [[ "${ticks}" =~ ^[0-9]+$ && "${pgid}" == "${pid}" ]]; then
      printf '%s %s\n' "${ticks}" "${pgid}"
      return 0
    fi
    sleep 0.05
  done
  echo "ERROR: ${label} did not start as an owned process group: pid=${pid} pgid=${pgid:-unknown}" >&2
  return 1
}

if [[ -f "$STATE_FILE" ]]; then
  state_rec_pid="$(
    # shellcheck disable=SC1090
    source "$STATE_FILE" && printf '%s' "${REC_PID:-}"
  )"
  state_bag_path="$(
    # shellcheck disable=SC1090
    source "$STATE_FILE" && printf '%s' "${BAG_PATH:-unknown}"
  )"
  if [[ -n "$state_rec_pid" ]] && kill -0 "$state_rec_pid" 2>/dev/null; then
    echo "ERROR: mapping bag is already recording: ${state_bag_path}" >&2
    echo "Finish it with: scripts/rc/rc_stop_mapping_bag.sh" >&2
    exit 1
  fi
  rm -f "$STATE_FILE"
fi

echo "[rc-bag] starting sensors, log: ${SENSOR_LOG}"
setsid env ./scripts/rc/rc_start_sensors.sh >"$SENSOR_LOG" 2>&1 &
SENSOR_PID=$!

cleanup_on_error() {
  set +e
  if [[ -n "${REC_PID:-}" ]] && kill -0 "$REC_PID" 2>/dev/null; then
    kill -INT -- "-${REC_PID}" 2>/dev/null || true
  fi
  ./scripts/rc/rc_stop.sh >/dev/null 2>&1 || true
  if [[ -n "${SENSOR_PID:-}" ]]; then
    kill -TERM -- "-${SENSOR_PID}" 2>/dev/null || true
  fi
  rm -f "$STATE_FILE"
}
trap cleanup_on_error ERR INT TERM

read -r SENSOR_START_TICKS SENSOR_PGID < <(
  capture_owned_process_group "${SENSOR_PID}" "sensor stack"
)

sleep "$SENSOR_WARMUP_SEC"

echo "[rc-bag] checking mapping inputs"
./scripts/check_mapping_inputs.sh

echo "[rc-bag] recording to ${BAG_PATH}, log: ${RECORD_LOG}"
setsid env BAG_PATH="$BAG_PATH" ./scripts/record_mapping_bag.sh >"$RECORD_LOG" 2>&1 &
REC_PID=$!
read -r REC_START_TICKS REC_PGID < <(
  capture_owned_process_group "${REC_PID}" "rosbag recorder"
)

{
  printf 'OWNER_UID=%q\n' "$(id -u)"
  printf 'ROOT_DIR=%q\n' "$ROOT_DIR"
  printf 'RUN_ID=%q\n' "$RUN_ID"
  printf 'BAG_PATH=%q\n' "$BAG_PATH"
  printf 'SENSOR_PID=%q\n' "$SENSOR_PID"
  printf 'SENSOR_START_TICKS=%q\n' "$SENSOR_START_TICKS"
  printf 'SENSOR_PGID=%q\n' "$SENSOR_PGID"
  printf 'REC_PID=%q\n' "$REC_PID"
  printf 'REC_START_TICKS=%q\n' "$REC_START_TICKS"
  printf 'REC_PGID=%q\n' "$REC_PGID"
  printf 'SENSOR_LOG=%q\n' "$SENSOR_LOG"
  printf 'RECORD_LOG=%q\n' "$RECORD_LOG"
} >"$STATE_FILE"

trap - ERR INT TERM

echo "[rc-bag] recording started"
echo "[rc-bag] finish with: scripts/rc/rc_stop_mapping_bag.sh"
echo "[rc-bag] state: ${STATE_FILE}"
echo "[rc-bag] bag path: ${BAG_PATH}"
