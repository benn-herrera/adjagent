#!/usr/bin/env bash
# `retake-reference`'s body: re-takes the four oracle slots from the current generator, each with
# its fixed flags.
set -euo pipefail
: "${PROJECT_ROOT:?PROJECT_ROOT is empty or unset — run this script through its justfile recipe}"
: "${GEN:?GEN is empty or unset — run this script through its justfile recipe}"
: "${RENDERED_DIR:?RENDERED_DIR is empty or unset — run this script through its justfile recipe}"

slot="${PROJECT_ROOT}/devtools/scripts/_render-slot.sh"
"${slot}" reference-claude
"${slot}" reference-opencode --harness=opencode --model-tier-map=all=inherit
"${slot}" reference-gemma --family=gemma-4 --model-pin-tier-alias-map=all=sonnet
"${slot}" reference-mage --harness=mage
