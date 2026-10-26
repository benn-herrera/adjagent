#!/usr/bin/env bash
# `format-python`'s body. `*paths` arrives as "$@" with each path its own word (the justfile sets
# positional-arguments), so a path containing a space still reaches every tool as one argument. No
# paths given reproduces the three-path, tool-by-tool argument order exactly — the order flake8 was
# already called with differs from black/isort's, and that difference is preserved rather than
# normalized away.
set -euo pipefail
: "${VENV_PYTHON:?VENV_PYTHON is empty or unset — run this script through its justfile recipe}"
: "${FLAKE8_IGNORE:?FLAKE8_IGNORE is empty or unset — run this script through its justfile recipe}"

if [[ "$#" -eq 0 ]]; then
    black_isort_paths=(tests adjagent devtools)
    flake8_paths=(adjagent devtools tests)
else
    black_isort_paths=("$@")
    flake8_paths=("$@")
fi
"${VENV_PYTHON}" -m black --line-length=120 "${black_isort_paths[@]}"
"${VENV_PYTHON}" -m isort --profile black --line-length 120 "${black_isort_paths[@]}"
"${VENV_PYTHON}" -m flake8 --ignore="${FLAKE8_IGNORE}" "${flake8_paths[@]}"
