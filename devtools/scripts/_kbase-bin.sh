#!/usr/bin/env bash
# `_kbase-bin`'s body: the executable `_download-kbase-dist` leaves in the cache — the release
# script's one unsuffixed name, which carries `.exe` under a Windows shell (msys, cygwin and mingw
# all report it from `uname -s`). Printed, not interpolated into a recipe line, so the one platform
# decision is made where `uname` is readable.
set -euo pipefail
: "${TOOL_DIST_CACHE:?TOOL_DIST_CACHE is empty or unset — run this script through its justfile recipe}"
: "${KBASE_VERSION:?KBASE_VERSION is empty or unset — run this script through its justfile recipe}"

exe=""
case "$(uname -s)" in
    MSYS*|CYGWIN*|MINGW*) exe=".exe" ;;
esac
printf '%s\n' "${TOOL_DIST_CACHE}/kbase-${KBASE_VERSION}/kbase${exe}"
