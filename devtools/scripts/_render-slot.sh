#!/usr/bin/env bash
# `_render-slot`'s body: everything `render` does once the slug is accepted. The slot is removed
# and rebuilt from the flags given, which are recorded in it. `--harness=NAME` is read here as well
# as forwarded.
#
# The harness's agents file lands in one of two shapes: at the slot root as `<agents-file>`, for a
# harness whose own files sit at its root (`user-harness-dir` `.` — a plugin, whose `.mcp.json` is
# written beside it), otherwise under `harness/<name>/<agents-file>`.
set -euo pipefail
: "${PROJECT_ROOT:?PROJECT_ROOT is empty or unset — run this script through its justfile recipe}"
: "${RENDERED_DIR:?RENDERED_DIR is empty or unset — run this script through its justfile recipe}"

slug="${1}"
shift
harness=""
args=("${@+"${@}"}")
for arg in "${args[@]+"${args[@]}"}"; do
    if [[ "${arg}" == --harness=* ]]; then
        harness="${arg#--harness=}"
    fi
done
[[ -z "${harness}" ]] && { harness="claude" && args+=("--harness=${harness}"); } || true
agents_file="$("${PROJECT_ROOT}/devtools/scripts/_harness-value.sh" "${harness}" agents-file)"
project_harness_dir="$("${PROJECT_ROOT}/devtools/scripts/_harness-value.sh" "${harness}" project-harness-dir)"
user_harness_dir="$("${PROJECT_ROOT}/devtools/scripts/_harness-value.sh" "${harness}" user-harness-dir)"
out="${PROJECT_ROOT}/${RENDERED_DIR}/${slug}"
rm -rf "${out}"
if [[ "${user_harness_dir}" == "." ]]; then
    agents_target="${out}/${agents_file}"
    mkdir -p "${out}"
else
    agents_target="${out}/harness/${harness}/${agents_file}"
    mkdir -p "${out}/harness/${harness}"
fi
if [[ "$#" -gt 0 ]]; then
    printf '%s\n' "$@" > "${out}/RENDER-FLAGS.txt"
else
    : > "${out}/RENDER-FLAGS.txt"
fi
"${PROJECT_ROOT}/devtools/scripts/render-agents-file.sh" "${harness}" "${agents_target}"
kbase_bin="$("${PROJECT_ROOT}/devtools/scripts/_kbase-bin.sh")"
"${PROJECT_ROOT}/devtools/scripts/install.sh" "${out}" --subdir= --with-kb --kbase-dist="${kbase_bin}" "${args[@]}"
