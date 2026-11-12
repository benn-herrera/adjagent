#!/usr/bin/env bash
# `render-agents-file`'s body. A stable interface, not a convenience: a later revision of this
# repository invokes it inside a worktree of an earlier one to render that revision's agents file.
# Its name and its arguments, HARNESS OUT [PLUGIN], never change incompatibly; the body, and the
# `render-agents-file` verb behind it, may change. PLUGIN, absent or empty, is the verb's default
# plugin, which this body does not name; a copy predating PLUGIN ignores it.
set -euo pipefail
: "${PROJECT_ROOT:?PROJECT_ROOT is empty or unset — run this script through its justfile recipe}"
: "${GEN:?GEN is empty or unset — run this script through its justfile recipe}"

: "${1:?usage: render-agents-file.sh HARNESS OUT [PLUGIN]}"
: "${2:?usage: render-agents-file.sh HARNESS OUT [PLUGIN]}"

plugin_flag=()
if [[ -n "${3:-}" ]]; then
    plugin_flag=("--plugin=${3}")
fi
PYTHONPATH="${PROJECT_ROOT}" python3 -m "${GEN}" render-agents-file "${1}" "${2}" "${plugin_flag[@]+"${plugin_flag[@]}"}"
