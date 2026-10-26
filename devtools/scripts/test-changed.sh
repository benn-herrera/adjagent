#!/usr/bin/env bash
# `test-changed`'s body: run only the test surfaces a change touches.
#
# Changed paths are the uncommitted tree (`git status`: staged, unstaged and untracked, both sides
# of a rename) plus, when <base> is given, everything committed since it (`git diff base...HEAD`).
# Each path selects the surface its prefix names in the justfile's TEST_SURFACE_MAP; a path matching
# no row (docs, plans, scratch) selects nothing. There are no cross-surface "just in case" rows. The
# one exception is the runner itself: `justfile`, `python.just` and the `devtools/scripts/` tree
# select every surface, because a change to a recipe — or to the script its body became — cannot be
# validated by skipping it. With nothing selected, it says so and exits zero without running tests.
# Git is only read.
#
# TEST_SURFACE_MAP is one row per line: "<path prefix, or exact file> <surface | ALL>". A prefix
# ending in `/` matches everything under it.
set -euo pipefail
: "${PROJECT_ROOT:?PROJECT_ROOT is empty or unset — run this script through its justfile recipe}"
: "${TEST_SURFACE_MAP:?TEST_SURFACE_MAP is empty or unset — run this script through its justfile recipe}"
: "${JUST:?JUST is empty or unset — run this script through its justfile recipe}"
: "${JUSTFILE:?JUSTFILE is empty or unset — run this script through its justfile recipe}"

cd "${PROJECT_ROOT}"
base="${1}"
all_surfaces=(adjagent dupe_sweep)
rows="${TEST_SURFACE_MAP}"

changed=()
# -z: NUL-separated, unquoted paths; a rename or copy entry (R/C in either
# status column) is followed by its source path as a separate entry.
# Both sides count — the source leaving a surface is a change to it.
while IFS= read -r -d '' entry; do
    changed+=("${entry:3}")
    if [[ "${entry:0:1}" == [RC] || "${entry:1:1}" == [RC] ]]; then
        IFS= read -r -d '' source
        changed+=("${source}")
    fi
done < <(git status --porcelain -z --untracked-files=all)
if [[ -n "${base}" ]]; then
    if ! git rev-parse --verify --quiet "${base}^{commit}" > /dev/null; then
        printf '%s\n' "error: base '${base}' is not a commit" >&2
        exit 1
    fi
    while IFS= read -r -d '' path; do
        changed+=("${path}")
    done < <(git diff --name-only --no-renames -z "${base}...HEAD")
fi

# "<surface> <path>" lines, one per (surface, changed path) match.
hits=""
for path in ${changed[@]+"${changed[@]}"}; do
    while read -r prefix surface; do
        [[ -n "${prefix}" ]] || continue
        if [[ "${path}" == "${prefix}" || ( "${prefix}" == */ && "${path}" == "${prefix}"* ) ]]; then
            if [[ "${surface}" == ALL ]]; then
                for each in "${all_surfaces[@]}"; do
                    hits+="${each} ${path}"$'\n'
                done
            else
                hits+="${surface} ${path}"$'\n'
            fi
        fi
    done <<< "${rows}"
done

chosen=()
for surface in "${all_surfaces[@]}"; do
    matched="$(printf '%s' "${hits}" | sed -n "s/^${surface} //p" | sort -u)"
    if [[ -n "${matched}" ]]; then
        chosen+=("${surface}")
        printf '%s\n' "${surface}:"
        printf '%s\n' "${matched}" | sed 's/^/  /'
    fi
done
if [[ "${#chosen[@]}" -eq 0 ]]; then
    printf '%s\n' "no test surface touched by the changed paths; nothing to run"
    exit 0
fi

# `just` is re-entered rather than the test script called directly: `test` carries the `_venv`
# dependency, which is what provisions the interpreter a fresh clone has not built yet, and a
# dependency is just's to run.
failed=()
for surface in "${chosen[@]}"; do
    if ! "${JUST}" --justfile "${JUSTFILE}" test "${surface}"; then
        failed+=("${surface}")
    fi
done
if [[ "${#failed[@]}" -gt 0 ]]; then
    printf '%s\n' "FAILED surfaces: ${failed[*]}" >&2
    exit 1
fi
