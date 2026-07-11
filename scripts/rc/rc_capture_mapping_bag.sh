#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

usage() {
  cat <<'EOF'
Usage:
  rc_capture_mapping_bag.sh

Environment:
  BAG_DURATION_SEC   recording duration in seconds, default: 20
  SENSOR_WARMUP_SEC  seconds to wait before input check, default: 16
  RUN_ID             mapping run id, default: rc_mapping_<timestamp>
  BAG_ROOT           bag root on the vehicle host, default: ~/autoracer_mapping_bags
  BAG_PATH           full bag output path, default: ${BAG_ROOT}/${RUN_ID}

For open-ended recording, use rc_start_mapping_bag.sh and rc_stop_mapping_bag.sh.
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

BAG_DURATION_SEC="${BAG_DURATION_SEC:-20}"
SENSOR_WARMUP_SEC="${SENSOR_WARMUP_SEC:-16}"
RUN_ID="${RUN_ID:-rc_mapping_$(date +%Y%m%d_%H%M%S)}"
BAG_ROOT="${BAG_ROOT:-${HOME}/autoracer_mapping_bags}"
BAG_PATH="${BAG_PATH:-${BAG_ROOT}/${RUN_ID}}"
LOG_ROOT="${LOG_ROOT:-/tmp}"
SENSOR_LOG="${SENSOR_LOG:-${LOG_ROOT}/${RUN_ID}_sensors.log}"
RECORD_LOG="${RECORD_LOG:-${LOG_ROOT}/${RUN_ID}_record.log}"

SENSOR_PID=""
REC_PID=""

cleanup() {
  if [[ -n "$REC_PID" ]] && kill -0 "$REC_PID" 2>/dev/null; then
    kill -INT "$REC_PID" 2>/dev/null || true
    wait "$REC_PID" 2>/dev/null || true
  fi
  ./scripts/rc/rc_stop.sh >/dev/null 2>&1 || true
  if [[ -n "$SENSOR_PID" ]]; then
    kill -TERM -- "-${SENSOR_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "[rc-capture] starting sensors, log: ${SENSOR_LOG}"
setsid env ./scripts/rc/rc_start_sensors.sh >"$SENSOR_LOG" 2>&1 &
SENSOR_PID=$!

sleep "$SENSOR_WARMUP_SEC"

echo "[rc-capture] checking mapping inputs"
./scripts/check_mapping_inputs.sh

echo "[rc-capture] recording ${BAG_DURATION_SEC}s to ${BAG_PATH}"
env BAG_PATH="$BAG_PATH" ./scripts/record_mapping_bag.sh >"$RECORD_LOG" 2>&1 &
REC_PID=$!
sleep "$BAG_DURATION_SEC"
kill -INT "$REC_PID" 2>/dev/null || true
wait "$REC_PID"
REC_PID=""

echo "[rc-capture] bag info"
# shellcheck source=scripts/ros_env.sh
source "$ROOT_DIR/scripts/ros_env.sh"
ros2 bag info "$BAG_PATH"
echo "[rc-capture] sensor log: ${SENSOR_LOG}"
echo "[rc-capture] record log: ${RECORD_LOG}"
echo "[rc-capture] bag path: ${BAG_PATH}"
