#!/usr/bin/env bash
# The one reader of the plugin list for scripts. Prints each loaded plugin's name, one per line,
# through `python3 -m adjagent plugins`.
set -euo pipefail
: "${PROJECT_ROOT:?PROJECT_ROOT is empty or unset — run this script through its justfile recipe}"
: "${GEN:?GEN is empty or unset — run this script through its justfile recipe}"

PYTHONPATH="${PROJECT_ROOT}" python3 -m "${GEN}" plugins
