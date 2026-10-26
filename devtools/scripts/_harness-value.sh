#!/usr/bin/env bash
# `_harness-value`'s body: the one reader of a harness's values for recipes. Prints KEY of harness
# NAME through `python3 -m adjagent harness`, a leading `~` expanded to $HOME.
set -euo pipefail
: "${PROJECT_ROOT:?PROJECT_ROOT is empty or unset — run this script through its justfile recipe}"
: "${GEN:?GEN is empty or unset — run this script through its justfile recipe}"
: "${1:?the first argument is the harness name}"
: "${2:?the second argument is the harness key}"

value="$(PYTHONPATH="${PROJECT_ROOT}" python3 -m "${GEN}" harness "${1}" "${2}")"
printf '%s\n' "${value/#\~/${HOME}}"
