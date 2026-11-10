#!/usr/bin/env bash
# `_render-slot`'s body: everything `render` does once the slug is accepted. The slot is removed
# and rebuilt from the flags given, which are recorded in it. `--harness=NAME` is read here as well
# as forwarded.
#
# Each plugin is rendered into its own slot project below the slot, <slot>/<plugin>/, which is also
# the install's harness directory (`--subdir=`), so a claude slot project holds its plugin at
# <slot>/<plugin>/skills/<plugin>/.
#
# Each plugin's agents file lands in one of two shapes: at the slot project's root as
# `<agents-file>`, for a harness whose own files sit at its root (`user-harness-dir` `.` — a
# harness-directory plugin, whose `.mcp.json` is written beside it), otherwise under
# `<plugin>/harness/<name>/<agents-file>`.
#
# HOME is a fresh, empty scratch home for the whole render, removed on exit, so nothing the render
# runs reads or writes the operator's real one.
set -euo pipefail
: "${PROJECT_ROOT:?PROJECT_ROOT is empty or unset — run this script through its justfile recipe}"
: "${RENDERED_DIR:?RENDERED_DIR is empty or unset — run this script through its justfile recipe}"
: "${GEN:?GEN is empty or unset — run this script through its justfile recipe}"

plugin_names="$("${PROJECT_ROOT}/devtools/scripts/_plugin-names.sh")"
plugins=()
while IFS= read -r name; do plugins+=("${name}"); done <<<"${plugin_names}"
slug="${1}"
shift
scratch_home="${PROJECT_ROOT}/.claude-temp/render-home/${slug}"
command rm -rf "${scratch_home}"
mkdir -p "${scratch_home}"
trap 'command rm -rf "${scratch_home}"' EXIT
export HOME="${scratch_home}"
harness=""
args=("${@+"${@}"}")
for arg in "${args[@]+"${args[@]}"}"; do
    if [[ "${arg}" == --harness=* ]]; then
        harness="${arg#--harness=}"
    fi
done
[[ -z "${harness}" ]] && { harness="claude" && args+=("--harness=${harness}"); } || true
agents_file="$("${PROJECT_ROOT}/devtools/scripts/_harness-value.sh" "${plugins[0]}" "${harness}" agents-file)"
user_harness_dir="$("${PROJECT_ROOT}/devtools/scripts/_harness-value.sh" "${plugins[0]}" "${harness}" user-harness-dir)"
out="${PROJECT_ROOT}/${RENDERED_DIR}/${slug}"
rm -rf "${out}"
mkdir -p "${out}"
if [[ "$#" -gt 0 ]]; then
    printf '%s\n' "$@" > "${out}/RENDER-FLAGS.txt"
else
    : > "${out}/RENDER-FLAGS.txt"
fi
for plugin in "${plugins[@]}"; do
    if [[ "${user_harness_dir}" == "." ]]; then
        agents_target="${out}/${plugin}/${agents_file}"
    else
        agents_target="${out}/${plugin}/harness/${harness}/${agents_file}"
    fi
    mkdir -p "$(dirname "${agents_target}")"
    "${PROJECT_ROOT}/devtools/scripts/render-agents-file.sh" "${harness}" "${agents_target}" "${plugin}"
    PYTHONPATH="${PROJECT_ROOT}" python3 -m "${GEN}" install "${plugin}" "${out}/${plugin}" --subdir= "${args[@]}"
done
