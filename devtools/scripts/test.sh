#!/usr/bin/env bash
# `test`'s body. PYTHONPATH is the repository root, here and in the tests: `adjagent` and
# `devtools` are top-level packages under it, and the tests import `adjagent` from that root the
# same way `sweep-python` runs `devtools.dupe_sweep`. Nothing an install writes is importable — the
# installed tree holds runner snippets, not a python package.
#
# `surface` is always positional parameter $1 (the justfile sets positional-arguments); the pytest
# arguments follow it from $2, and are forwarded as the separate words `just` received them as, so
# `-k "a and b"` stays one argument. A path argument (not starting with `-`, and an existing path
# or containing `::`) narrows the run: pytest gets the paths and flags but not the surface
# directory. A flag alone does not narrow: pytest gets the directory plus the flags. A path outside
# the surface's directory is refused. The word after a flag that takes a separate value (`-k expr`)
# is that value, never a path.
set -euo pipefail
: "${PROJECT_ROOT:?PROJECT_ROOT is empty or unset — run this script through its justfile recipe}"
: "${VENV_PYTHON:?VENV_PYTHON is empty or unset — run this script through its justfile recipe}"

surface="${1}"
# A surface is a name, never a flag: `just` binds a leading flag to the surface parameter, so a
# caller reaching this check with `-k` meant to pass a flag and needs the explicit empty surface.
case "${surface}" in
    "") dirs=(tests devtools/tests) ;;
    adjagent) dirs=(tests) ;;
    dupe_sweep) dirs=(devtools/tests) ;;
    *)
        printf '%s\n' "error: unknown test surface '${surface}' — valid values: adjagent, dupe_sweep; a leading flag binds here instead — pass it with an explicit empty surface: just test \"\" ${surface}" >&2
        exit 1
        ;;
esac
root="${PROJECT_ROOT}"
has_path=0
skip_next=0
for arg in "${@:2}"; do
    if [[ "${skip_next}" -eq 1 ]]; then
        skip_next=0
        continue
    fi
    case "${arg}" in
        -k|-m|-p|-o|-c|-n|--deselect|--ignore|--ignore-glob|--maxfail|--tb|--durations) skip_next=1; continue ;;
        -*) continue ;;
    esac
    [[ -e "${arg}" || "${arg}" == *::* ]] || continue
    has_path=1
    rel="${arg#"${root}"/}"
    rel="${rel#./}"
    rel="${rel%%::*}"
    under=0
    for dir in "${dirs[@]}"; do
        if [[ "${rel}" == "${dir}" || "${rel}" == "${dir}/"* ]]; then
            under=1
        fi
    done
    if [[ "${under}" -eq 0 ]]; then
        printf "error: test path '%s' is outside surface '%s' (directory: %s)\n" \
            "${arg}" "${surface}" "${dirs[*]}" >&2
        exit 1
    fi
done
if [[ "${has_path}" -eq 1 ]]; then
    targets=()
else
    targets=("${dirs[@]}")
fi
PYTHONPATH="${root}" "${VENV_PYTHON}" -m pytest ${targets[@]+"${targets[@]}"} "${@:2}"
