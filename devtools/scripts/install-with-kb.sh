#!/usr/bin/env bash
# `just install-with-kb`'s body: the bare install with the kb set added. "$@" is the caller's own
# $1 (the target) and flags, unchanged: install.sh's leading-flag scan and existence check own
# them, so this script resolves no target of its own.
set -euo pipefail
: "${PROJECT_ROOT:?PROJECT_ROOT is empty or unset — run this script through its justfile recipe}"

"${PROJECT_ROOT}/devtools/scripts/install.sh" "$@" --with-kb
