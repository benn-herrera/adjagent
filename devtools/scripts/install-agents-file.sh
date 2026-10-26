#!/usr/bin/env bash
# `install-agents-file`'s body: a thin invocation on purpose. Every protection the agents-file
# install carries — block-only replacement, malformed-marker refusal, the uncommitted-sources
# refusal, the rolling backup — lives in adjagent/agents_file.py. The one thing done here is naming
# the harness when the caller omits it: the one whose user-harness-dir is DIR (resolved to an
# absolute path). Zero or several matches fail rather than guess — a project root matches none, so
# it takes an explicit harness.
set -euo pipefail
: "${PROJECT_ROOT:?PROJECT_ROOT is empty or unset — run this script through its justfile recipe}"
: "${GEN:?GEN is empty or unset — run this script through its justfile recipe}"

dir="${1}"
harness="${2}"
if [[ -z "${harness}" ]]; then
    # pwd -P so a symlinked path compares equal to its target.
    function resolve() { (cd "${1}" 2>/dev/null && pwd -P) || printf '%s\n' "${1}"; }
    want="$(resolve "${dir}")"
    matches=()
    inferable=()
    for name in $("${PROJECT_ROOT}/devtools/scripts/_harness-names.sh"); do
        user_dir="$("${PROJECT_ROOT}/devtools/scripts/_harness-value.sh" "${name}" user-harness-dir)"
        # A relative value names no directory — mage's `.` is the caller's working directory, not DIR —
        # so it is never an inference basis, whatever DIR resolves to.
        [[ "${user_dir}" == /* ]] || continue
        inferable+=("${name}")
        if [[ "$(resolve "${user_dir}")" == "${want}" ]]; then
            matches+=("${name}")
        fi
    done
    if [[ "${#matches[@]}" -ne 1 ]]; then
        printf '%s\n' "error: cannot infer the harness for '${dir}' (${#matches[@]} harnesses use it as their user directory) — pass it explicitly, naming one whose user-harness-dir is absolute (${inferable[*]}), e.g. just install-agents-file ${dir} <harness>" >&2
        exit 1
    fi
    harness="${matches[0]}"
fi
PYTHONPATH="${PROJECT_ROOT}" python3 -m "${GEN}" install-agents-file "${harness}" "${dir}"
