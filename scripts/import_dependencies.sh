#!/usr/bin/env bash
set -euo pipefail

PRODUCT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT_DIR="$(dirname "${PRODUCT_ROOT}")"
PROFILE="${AUTORACER_PROFILE:-hooke2}"
RESOLVER="${PRODUCT_ROOT}/scripts/vendor/resolve_dependencies.py"
VENDOR_WS="${AUTORACER_VENDOR_WS:-${PRODUCT_ROOT}/vendor_ws}"
PILOT_REPO="${PILOT_REPO:-${ROOT_DIR}/pilot-auto.x1}"
PATCH_DIR="${PRODUCT_ROOT}/dependencies/patches"

if [[ "${PROFILE}" != "hooke2" && -z "${AUTORACER_VENDOR_WS:-}" ]]; then
  echo "AUTORACER_VENDOR_WS is required for non-Hooke profile ${PROFILE}" >&2
  exit 2
fi

mode="reuse"
case "${1:-}" in
  "") ;;
  --refresh) mode="pilot" ;;
  --network) mode="network" ;;
  --verify-only) mode="verify" ;;
  *)
    echo "Usage: $0 [--refresh|--network|--verify-only]" >&2
    exit 2
    ;;
esac

if ! RESOLVED_RECORDS="$(python3 "${RESOLVER}" --profile "${PROFILE}" --format records)"; then
  echo "Unable to resolve vendor profile: ${PROFILE}" >&2
  exit 1
fi
[[ -n "${RESOLVED_RECORDS}" ]] || { echo "Empty vendor profile: ${PROFILE}" >&2; exit 1; }

copy_curated_packages() {
  local source_root="$1"
  local package relative_path repository source_dir destination_dir

  while IFS=$'\t' read -r package relative_path repository; do
    [[ -n "${package}" && -n "${relative_path}" ]] || continue
    source_dir="${source_root}/${relative_path}"
    destination_dir="${VENDOR_WS}/src/${relative_path}"
    if [[ ! -f "${source_dir}/package.xml" ]]; then
      echo "Missing ${package} in dependency source: ${source_dir}" >&2
      exit 1
    fi
    mkdir -p "$(dirname "${destination_dir}")"
    rsync -a --delete \
      --exclude='.git' \
      --exclude='build' \
      --exclude='install' \
      --exclude='log' \
      --exclude='COLCON_IGNORE' \
      --exclude='*.db3' \
      "${source_dir}/" "${destination_dir}/"
  done <<< "${RESOLVED_RECORDS}"
}

apply_patch_once() {
  local patch_file="$1"
  if patch --batch --forward --dry-run --silent -d "${VENDOR_WS}" -p1 \
    < "${patch_file}" >/dev/null 2>&1
  then
    patch --batch --forward --silent -d "${VENDOR_WS}" -p1 < "${patch_file}"
  elif patch --batch --reverse --dry-run --silent -d "${VENDOR_WS}" -p1 \
    < "${patch_file}" >/dev/null 2>&1
  then
    printf 'already applied: %s\n' "$(basename "${patch_file}")"
  else
    echo "Patch does not apply cleanly: ${patch_file}" >&2
    exit 1
  fi
}

verify_package_set() {
  local expected actual
  expected="$(mktemp)"
  actual="$(mktemp)"
  python3 "${RESOLVER}" --profile "${PROFILE}" --format names | sort -u > "${expected}"
  colcon list --base-paths "${VENDOR_WS}/src" --names-only | sort -u > "${actual}"
  if ! diff -u "${expected}" "${actual}"; then
    rm -f "${expected}" "${actual}"
    echo "Vendor package set differs from profile ${PROFILE}" >&2
    return 1
  fi
  printf 'verified vendor package set: %s packages\n' "$(wc -l < "${actual}")"
  rm -f "${expected}" "${actual}"
}

if [[ "${mode}" == "pilot" || "${mode}" == "network" ]]; then
  if [[ -z "${VENDOR_WS}" || "${VENDOR_WS}" == "/" || "${VENDOR_WS}" == "${HOME}" ]]; then
    echo "Refusing unsafe vendor workspace path: ${VENDOR_WS}" >&2
    exit 1
  fi
  rm -rf "${VENDOR_WS}/src"
  mkdir -p "${VENDOR_WS}/src"

  if [[ "${mode}" == "pilot" ]]; then
    if [[ ! -d "${PILOT_REPO}/src" ]]; then
      echo "Missing real-vehicle source repository: ${PILOT_REPO}" >&2
      exit 1
    fi
    copy_curated_packages "${PILOT_REPO}/src"
  else
    command -v vcs >/dev/null || {
      echo "vcs is required for --network" >&2
      exit 1
    }
    temporary_checkout="$(mktemp -d)"
    trap 'rm -rf "${temporary_checkout}"' EXIT
    mkdir -p "${temporary_checkout}/src"
    python3 "${RESOLVER}" --profile "${PROFILE}" --format repositories \
      > "${temporary_checkout}/filtered.repos"
    vcs import "${temporary_checkout}/src" < "${temporary_checkout}/filtered.repos"
    copy_curated_packages "${temporary_checkout}/src"
  fi
elif [[ ! -d "${VENDOR_WS}/src" ]]; then
  echo "Missing vendor workspace. Run $0 --refresh." >&2
  exit 1
fi

if [[ "${mode}" != "verify" ]]; then
  while IFS= read -r patch_file; do
    apply_patch_once "${patch_file}"
  done < <(find "${PATCH_DIR}" -maxdepth 1 -type f -name '*.patch' -print | sort)
fi

verify_package_set
