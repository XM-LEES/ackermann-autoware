#!/usr/bin/env bash
# Source this file from repository scripts to load ROS and this workspace.

_autoracer_filter_path_var() {
  local var_name="$1"
  local blocked_prefix="$2"
  local value="${!var_name:-}"
  local filtered=""
  local entry

  if [[ -z "${value}" ]]; then
    return 0
  fi

  while IFS= read -r -d ':' entry; do
    [[ -z "${entry}" ]] && continue
    [[ "${entry}" == "${blocked_prefix}"* ]] && continue
    if [[ -z "${filtered}" ]]; then
      filtered="${entry}"
    else
      filtered="${filtered}:${entry}"
    fi
  done < <(printf '%s:' "${value}")

  export "${var_name}=${filtered}"
}

_autoracer_filter_blocked_underlay_paths() {
  local blocked_underlay="${AUTORACER_BLOCKED_UNDERLAY:-}"
  [[ -z "${blocked_underlay}" ]] && return 0

  local var_name
  for var_name in \
    AMENT_PREFIX_PATH \
    CMAKE_PREFIX_PATH \
    COLCON_PREFIX_PATH \
    LD_LIBRARY_PATH \
    LIBRARY_PATH \
    PKG_CONFIG_PATH \
    PYTHONPATH \
    PATH
  do
    _autoracer_filter_path_var "${var_name}" "${blocked_underlay}"
  done
}

_autoracer_reset_inherited_underlays() {
  if [[ "${AUTORACER_ALLOW_EXTERNAL_UNDERLAY:-false}" == "true" ]]; then
    _autoracer_filter_blocked_underlay_paths
    return 0
  fi

  local -a underlay_prefixes=("${ROOT_DIR}/install")
  local var_name value entry prefix
  for var_name in AMENT_PREFIX_PATH COLCON_PREFIX_PATH; do
    value="${!var_name:-}"
    while IFS= read -r -d ':' entry; do
      [[ -z "${entry}" || "${entry}" == /opt/ros/* ]] && continue
      underlay_prefixes+=("${entry}")
    done < <(printf '%s:' "${value}")
  done

  for prefix in "${underlay_prefixes[@]}"; do
    for var_name in \
      LD_LIBRARY_PATH \
      LIBRARY_PATH \
      PKG_CONFIG_PATH \
      PYTHONPATH \
      PATH
    do
      _autoracer_filter_path_var "${var_name}" "${prefix}"
    done
  done

  unset AMENT_PREFIX_PATH CMAKE_PREFIX_PATH COLCON_PREFIX_PATH
  _autoracer_filter_blocked_underlay_paths
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  echo "source scripts/ros_env.sh from another script or shell"
  exit 0
fi

ROOT_DIR="${ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
ROS_DISTRO_NAME="${ROS_DISTRO_NAME:-humble}"
ROS_SETUP="/opt/ros/${ROS_DISTRO_NAME}/setup.bash"

if [[ ! -f "${ROS_SETUP}" ]]; then
  echo "[autoracer-env] Missing ROS setup: ${ROS_SETUP}" >&2
  return 1
fi

unset AMENT_CURRENT_PREFIX COLCON_CURRENT_PREFIX
_autoracer_reset_inherited_underlays

_autoracer_had_nounset=0
case $- in
  *u*) _autoracer_had_nounset=1 ;;
esac

set +u
# shellcheck disable=SC1090
source "${ROS_SETUP}"
if [[ "${_autoracer_had_nounset}" == "1" ]]; then
  set -u
fi
_autoracer_filter_blocked_underlay_paths

if [[ "${AUTORACER_SOURCE_LOCAL_SETUP:-true}" == "true" ]]; then
  if [[ -f "${ROOT_DIR}/install/local_setup.bash" ]]; then
    set +u
    # shellcheck disable=SC1091
    source "${ROOT_DIR}/install/local_setup.bash"
    if [[ "${_autoracer_had_nounset}" == "1" ]]; then
      set -u
    fi
    _autoracer_filter_blocked_underlay_paths
  else
    echo "[autoracer-env] ${ROOT_DIR}/install/local_setup.bash not found; build first." >&2
    return 1
  fi
fi

if [[ -z "${RMW_IMPLEMENTATION:-}" ]]; then
  AUTORACER_DEFAULT_RMW="${AUTORACER_DEFAULT_RMW:-rmw_cyclonedds_cpp}"
  if [[ -n "${AUTORACER_DEFAULT_RMW}" ]]; then
    if [[ -d "/opt/ros/${ROS_DISTRO_NAME}/share/${AUTORACER_DEFAULT_RMW}" ]]; then
      export RMW_IMPLEMENTATION="${AUTORACER_DEFAULT_RMW}"
    else
      echo "[autoracer-env] ${AUTORACER_DEFAULT_RMW} is not installed; using ROS default RMW." >&2
    fi
  fi
fi

if [[ "${RMW_IMPLEMENTATION:-}" == "rmw_cyclonedds_cpp" && -z "${CYCLONEDDS_URI:-}" ]]; then
  AUTORACER_CYCLONEDDS_CONFIG="${AUTORACER_CYCLONEDDS_CONFIG:-${ROOT_DIR}/config/middleware/cyclonedds.xml}"
  if [[ -f "${AUTORACER_CYCLONEDDS_CONFIG}" ]]; then
    export CYCLONEDDS_URI="file://${AUTORACER_CYCLONEDDS_CONFIG}"
  else
    echo "[autoracer-env] Missing CycloneDDS config: ${AUTORACER_CYCLONEDDS_CONFIG}" >&2
    return 1
  fi
fi
