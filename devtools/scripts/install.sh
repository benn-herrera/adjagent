#!/usr/bin/env bash
# `just install`'s body. Renders every definition into <target>/<subdir>/ and copies the shipped
# packages beside them through `python3 -m adjagent install`, overwriting what is there; a consuming
# project's git is the record of what changed. Every flag forwards verbatim; adjagent's argparse is
# the single source of flag truth. `--subdir=X`, read only as the first flag, is this recipe's own
# and defaults to the --harness's project-harness-dir.
#
# The body also resolves <target> — the first non-flag argument — and passes it beside ROOT as the
# project root, because ROOT is only the harness directory a project keeps under it: the MCP entry
# an install registers and the runner include line it appends belong at the project root, never at
# the harness directory they spell their paths from.
set -euo pipefail
: "${PROJECT_ROOT:?PROJECT_ROOT is empty or unset — run this script through its justfile recipe}"
: "${GEN:?GEN is empty or unset — run this script through its justfile recipe}"

# `just` binds the first positional to `target` whatever it looks like, so a
# caller leading with flags would have a flag taken as the path. The target is
# the first argument that is not a `--` flag, wherever it sits; everything else
# keeps its order and forwards. `just` hands the parameters through as shell
# positionals, so `"$@"` here is target followed by flags with each word intact.
positional=("${@}")
target=""
subdir=""
have_subdir=""
harness=""
args=()
for arg in ${positional[@]+"${positional[@]}"}; do
    if [[ -z "${target}" && "${arg}" != --* ]]; then
        target="${arg}"
        # infer harness from target if possible
        if [[ -z "${harness}" ]]; then
          case "${target}" in
            *claude*) harness="claude";;
            *opencode*) harness="opencode";;
            */Mage/*|*/mage/*) harness="mage";;
          esac
        fi
    elif [[ "${#args[@]}" -eq 0 && "${arg}" == --subdir=* ]]; then
        subdir="${arg#--subdir=}"
        have_subdir=1
    else
        if [[ "${arg}" == --harness=* ]]; then
            harness="${arg#--harness=}"
        fi
        args+=("${arg}")
    fi
done
if [[ -z "${target}" ]]; then
    printf '%s\n' "error: no target project root given — every argument is a flag" >&2
    exit 1
fi
# A consuming project that does not exist is an operator mistake — a typo'd
# path would otherwise be silently populated as a new project root.
if [[ ! -d "${target}" ]]; then
    printf '%s\n' "error: target project root '${target}' does not exist — create the project first" >&2
    exit 1
fi
if [[ -z "${harness}" ]]; then
  [[ -d "${target}/.opencode" ]] && harness="opencode" || true
  [[ -z "${harness}" && -d "${target}/.claude" ]] && harness="claude" || true
  # no harness set or inferrable.
  [[ -z "${harness}" ]] && {
      printf '%s\n' "error: no harness specified with --harness and none could be inferred from ${target}" >&2;
      exit 1
  }
fi

# assure harness arg present
[[ "${args[*]+"${args[*]}"}" != *--harness=* ]] && args+=(--harness="${harness}") || true

# mage always gets kb
[[ "${harness}" == "mage" && "${args[*]}" != "--with-kb" ]] && args+=("--with-kb") || true

# assure kbase dist available when installing kb
[[ "${args[*]+"${args[*]}"}" == *--with-kb* ]] && args+=(--kbase-dist="$("${PROJECT_ROOT}/devtools/scripts/_kbase-bin.sh")") || true

# pwd -P so a symlinked path resolves to the tree the install reads; the
# harness arguments name paths from the project root, not from ROOT. The
# assignment's status is `cd`'s own, so an unenterable directory stops the
# recipe here rather than at the install with no project root.
project_root="$(cd "${target}" && pwd -P)"
if [[ -z "${have_subdir}" ]]; then
    subdir="$("${PROJECT_ROOT}/devtools/scripts/_harness-value.sh" "${harness}" project-harness-dir)"
fi
root="${target}${subdir:+/${subdir}}"
mkdir -p "${root}"
# ${arr[@]+...} guard: expanding an empty array trips `set -u` on the
# bash 3.2 that macOS ships at /bin/bash.
PYTHONPATH="${PROJECT_ROOT}" python3 -m "${GEN}" install "${root}" --project-root="${project_root}" ${args[@]+"${args[@]}"}

# A harness whose own files sit at its root (`user-harness-dir` `.`) is a plugin, and its agents file
# belongs beside its `.mcp.json` at ROOT rather than at the project root. Only a subdir install has a
# ROOT of its own: with `--subdir=` the root given is the project root, whose agents file the caller
# writes itself (the slot render does), so that case is left alone.
user_harness_dir="$("${PROJECT_ROOT}/devtools/scripts/_harness-value.sh" "${harness}" user-harness-dir)"
resolved_root="$(cd "${root}" && pwd -P)"
if [[ "${user_harness_dir}" == "." && "${resolved_root}" != "${project_root}" ]]; then
    "${PROJECT_ROOT}/devtools/scripts/install-agents-file.sh" "${root}" "${harness}"
fi
