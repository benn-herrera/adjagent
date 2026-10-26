#!/usr/bin/env bash
# `_harness-names`'s body: every harness name, one per line.
set -euo pipefail
: "${PROJECT_ROOT:?PROJECT_ROOT is empty or unset — run this script through its justfile recipe}"
: "${GEN:?GEN is empty or unset — run this script through its justfile recipe}"

PYTHONPATH="${PROJECT_ROOT}" python3 -m "${GEN}" harnesses
