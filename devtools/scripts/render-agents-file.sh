#!/usr/bin/env bash
# `render-agents-file`'s body. A stable interface, not a convenience: a later revision of this
# repository invokes it inside a worktree of an earlier one to render that revision's agents file.
# Its name and its two arguments never change incompatibly; the body, and the
# `render-agents-file` verb behind it, may change.
set -euo pipefail
: "${PROJECT_ROOT:?PROJECT_ROOT is empty or unset — run this script through its justfile recipe}"
: "${GEN:?GEN is empty or unset — run this script through its justfile recipe}"

PYTHONPATH="${PROJECT_ROOT}" python3 -m "${GEN}" render-agents-file "$1" "$2"
