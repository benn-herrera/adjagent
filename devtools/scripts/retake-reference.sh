#!/usr/bin/env bash
# `retake-reference`'s body. The three `reference*` slots are the oracle `render-diff` reads.
# `render` refuses their names so a render never overwrites the oracle by accident; this script is
# the one deliberate way to re-take them, run after a change to what the definitions say has been
# reviewed and accepted, so that the next `render-diff` measures the next change and not that one.
# Each slot is rendered with the kb set, as `render` renders one.
set -euo pipefail
: "${PROJECT_ROOT:?PROJECT_ROOT is empty or unset — run this script through its justfile recipe}"

render_slot=("${PROJECT_ROOT}/devtools/scripts/_render-slot.sh")
"${render_slot[@]}" reference
"${render_slot[@]}" reference-opencode --harness=opencode --model-tier-map=all=inherit
"${render_slot[@]}" reference-gemma --family=gemma-4 --model-pin-tier-alias-map=all=sonnet
