#!/usr/bin/env bash
# Cold read: one agent reads one brief with no tools and no project instructions in context.
#
# usage: cold-read.sh <agent> <brief-file> [<output-file>]
#   agent        e.g. <plugin>:architect
#   brief-file   the question plus the material, pasted in full
#   output-file  default: beside the brief, <brief name without .md>-<agent, ":" as "-">.md
#
# Needs DEVPRO_COLD_READ_DIR: an existing directory outside the project with no instruction file
# at or above it (the user's own ~/.claude/ excepted). Each run works in a fresh 0700 child of it
# and removes the child on exit. Under claude the child stays empty: the agents load from the
# plugin root, the nearest ancestor of this script holding .claude-plugin/. Under opencode the
# child holds the named agent's file alone, composed from its record in registry.json
# (the nearest ancestor of this script holding one) and its body file, with permission deny-all.
# Optional DEVPRO_COLD_READ_MODEL pins the reader's model: claude takes a name or alias, opencode provider/model.
# Under opencode, needs python3 on PATH to compose the agent file.
# Runs under the claude and opencode installs only.
set -euo pipefail

# Restated from the harness profiles; tests pin them to Harness.project_harness_dir and agents_file.
readonly CLAUDE_DIR=".claude"
readonly OPENCODE_DIR=".opencode"
readonly INSTRUCTION_NAMES=(
  CLAUDE.md CLAUDE.local.md AGENTS.md .claude/CLAUDE.md .claude/AGENTS.md .claude/rules
  .opencode opencode.json opencode.jsonc
)

function refuse() {
  printf 'cold-read: %s\n' "${1}" >&2
  exit 1
}

# Prints the first instruction file at or above ${1}, outside the exempt ${home}/.claude/.
function find_instruction() {
  local dir="${1}" name
  while :; do
    for name in "${INSTRUCTION_NAMES[@]}"; do
      if [[ -e "${dir%/}/${name}" && ! ( "${dir}" == "${home}" && "${name}" == .claude/* ) ]]; then
        printf '%s\n' "${dir%/}/${name}"
        return 0
      fi
    done
    [[ "${dir}" == / ]] && return 1
    dir="$(dirname "${dir}")"
  done
}

# Prints the nearest ancestor of ${1} (itself included) holding ${2}.
function find_ancestor_holding() {
  local dir="${1}"
  while [[ ! -e "${dir}/${2}" ]]; do
    [[ "${dir}" != / ]] || return 1
    dir="$(dirname "${dir}")"
  done
  printf '%s\n' "${dir}"
}

# Prints the agent file for registry id ${2} in the plugin root ${1}: frontmatter from the
# record in registry.json (description, model where present, mode) with permission deny-all, then its
# body file below the leading comment banner. Exits 3 where the registry holds no such record.
function compose_agent_file() {
  python3 -I -c '
import json, sys

plugin_root, agent_id = sys.argv[1:]
with open(plugin_root + "/registry.json", encoding="utf-8") as registry:
    agents = json.load(registry)["agents"]
record = next((a for a in agents if a["id"] == agent_id), None)
if record is None:
    sys.exit(3)
print("---")
print("description: " + json.dumps(record.get("description", "")))
model = record.get("model")
if model:
    print("model: " + json.dumps(model["providerID"] + "/" + model["id"]))
print("mode: " + record["mode"])
print("permission:")
print("  \"*\": deny")
print("---")
with open(plugin_root + "/" + record["file"], encoding="utf-8") as body:
    lines = body.read().splitlines(keepends=True)
start = 0
while start < len(lines) and lines[start].startswith("<!-- !"):
    start += 1
if start < len(lines) and lines[start].strip() == "":
    start += 1
sys.stdout.write("".join(lines[start:]))
' "${1}" "${2}"
}

if [[ $# -lt 2 || $# -gt 3 ]]; then
  printf 'usage: %s <agent> <brief-file> [<output-file>]\n' "${0}" >&2
  exit 2
fi
agent="${1}"
brief_arg="${2}"
[[ -f "${brief_arg}" ]] || refuse "no brief: ${brief_arg}"
brief_dir="$(cd "$(dirname "${brief_arg}")" && pwd -P)"
brief="${brief_dir}/$(basename "${brief_arg}")"
if [[ $# -eq 3 ]]; then
  out="${3}"
  [[ "${out}" == /* ]] || out="${PWD}/${out}"
else
  out="${brief_dir}/$(basename "${brief}" .md)-${agent//:/-}.md"
fi

# The harness is the nearest ancestor of this script named for one; that directory is what is copied.
harness_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
while [[ "$(basename "${harness_dir}")" != "${CLAUDE_DIR}" && "$(basename "${harness_dir}")" != "${OPENCODE_DIR}" ]]; do
  [[ "${harness_dir}" != / ]] || refuse "no ${CLAUDE_DIR} or ${OPENCODE_DIR} directory above this script; it runs under claude and opencode only"
  harness_dir="$(dirname "${harness_dir}")"
done
harness="$(basename "${harness_dir}")"
project_root="$(dirname "${harness_dir}")"

# The calling session's own marker, where exactly one is set, must name this copy's harness.
other=""
if [[ "${harness}" == "${CLAUDE_DIR}" && -n "${OPENCODE_TERMINAL:-}" && -z "${CLAUDECODE:-}" ]]; then
  other="${OPENCODE_DIR}"
elif [[ "${harness}" == "${OPENCODE_DIR}" && -n "${CLAUDECODE:-}" && -z "${OPENCODE_TERMINAL:-}" ]]; then
  other="${CLAUDE_DIR}"
fi
[[ -z "${other}" ]] || refuse "this copy is under ${harness} but the calling session is the ${other} harness's; run the development skill copy under ${other}"

[[ -n "${DEVPRO_COLD_READ_DIR:-}" ]] || refuse "DEVPRO_COLD_READ_DIR is not set; it names an existing directory outside the project"
loc="$(cd "${DEVPRO_COLD_READ_DIR}" 2>/dev/null && pwd -P)" || refuse "DEVPRO_COLD_READ_DIR is not a directory: ${DEVPRO_COLD_READ_DIR}"
if [[ "${loc}" == "${project_root}" || "${loc}" == "${project_root}/"* ]]; then
  refuse "DEVPRO_COLD_READ_DIR is inside the project (${project_root}): ${loc}"
fi
home="$(cd "${HOME}" 2>/dev/null && pwd -P)" || home="${HOME}"
if offender="$(find_instruction "${loc}")"; then
  refuse "DEVPRO_COLD_READ_DIR has an instruction file at or above it, which the reader would load: ${offender}"
fi

if [[ "${harness}" == "${CLAUDE_DIR}" ]]; then
  plugin_root="$(find_ancestor_holding "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)" .claude-plugin)" ||
    refuse "no .claude-plugin directory above this script; claude cannot load the agents"
else
  command -v python3 >/dev/null || refuse "python3 is not on PATH; it composes the agent file under opencode"
  plugin_root="$(find_ancestor_holding "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)" registry.json)" ||
    refuse "no registry.json above this script; opencode cannot load the agents"
  # the registry spells the plugin prefix with a hyphen where the argument has a colon
  agent_id="${agent//:/-}"
  rc=0
  agent_text="$(compose_agent_file "${plugin_root}" "${agent_id}")" || rc=$?
  if [[ "${rc}" -eq 3 ]]; then
    refuse "no registry record for ${agent_id} in ${plugin_root}/registry.json"
  elif [[ "${rc}" -ne 0 ]]; then
    refuse "cannot compose the agent file for ${agent_id} from ${plugin_root}/registry.json"
  fi
  # opencode takes the brief as its message, and its help does not document "--" as the end of flags.
  message="$(<"${brief}")"
  [[ "${message}" != -* ]] || refuse "the brief starts with '-', which opencode would read as a flag"
fi

run=""
function cleanup() {
  [[ -z "${run}" ]] || rm -rf -- "${run}"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

model=()
[[ -z "${DEVPRO_COLD_READ_MODEL:-}" ]] || model=(--model "${DEVPRO_COLD_READ_MODEL}")
run="$(mktemp -d "${loc}/cold-read.XXXXXX")"
if [[ "${harness}" == "${CLAUDE_DIR}" ]]; then
  cmd=(claude -p --tools "" --plugin-dir "${plugin_root}" --agent "${agent}" --no-session-persistence ${model[@]+"${model[@]}"})
  stdin="${brief}"
else
  mkdir -p "${run}/${OPENCODE_DIR}/agents"
  printf '%s\n' "${agent_text}" >"${run}/${OPENCODE_DIR}/agents/${agent_id}.md"
  # Flags precede the message: opencode's usage is `run [flags] [<message...>]`.
  cmd=(opencode run --archived --agent "${agent_id}" ${model[@]+"${model[@]}"} "${message}")
  stdin=/dev/null
fi

# stdout is the reply, written straight to the output file; the command substitution holds stderr.
cd "${run}"
rc=0
err="$("${cmd[@]}" 2>&1 >"${out}" <"${stdin}")" || rc=$?
if [[ "${rc}" -ne 0 ]]; then
  rm -f -- "${out}"
  printf '%s\n' "${err}" >&2
  # claude exits 1 on an agent it did not load, listing the available ones on stderr.
  if [[ "${harness}" == "${CLAUDE_DIR}" && "${err}" == *"--agent '${agent}' not found"* ]]; then
    refuse "claude did not load ${agent}; no output was kept"
  fi
  refuse "${cmd[0]} failed with status ${rc}"
fi

[[ -z "${err}" ]] || printf '%s\n' "${err}" >&2
printf '%s\n' "${out}"
