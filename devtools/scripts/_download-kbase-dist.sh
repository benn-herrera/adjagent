#!/usr/bin/env bash
# `_download-kbase-dist`'s body: fetch the pinned kbase release into the dist cache and unpack it,
# once. The release script unpacks `kbase-<version>/` beside itself, so it runs from the cache
# directory the executable is later read from — the `cd` is the installer's own requirement, not a
# convenience.
#
# The probe below accepts either `kbase` or, under a Windows shell, `kbase.exe`, so it tests both
# names; a probe testing only `kbase` never matched there and re-ran the script on every
# invocation. `_kbase-bin` is the one place that decides which name runs.
set -euo pipefail
: "${TOOL_DIST_CACHE:?TOOL_DIST_CACHE is empty or unset — run this script through its justfile recipe}"
: "${KBASE_VERSION:?KBASE_VERSION is empty or unset — run this script through its justfile recipe}"

mkdir -p "${TOOL_DIST_CACHE}"
cd "${TOOL_DIST_CACHE}"
[[ -f "install-kbase-${KBASE_VERSION}.sh" ]] || \
  curl --fail --silent --show-error --location --proto '=https' -O "https://github.com/benn-herrera/kbase/releases/download/${KBASE_VERSION}/install-kbase-${KBASE_VERSION}.sh"
[[ -x "kbase-${KBASE_VERSION}/kbase" || -x "kbase-${KBASE_VERSION}/kbase.exe" ]] || bash "./install-kbase-${KBASE_VERSION}.sh"
