#!/usr/bin/env bash
# `mage-dist`'s body. Builds the mage release of each plugin from the working tree as it stands and signs
# each tarball. Writes two files per plugin to DIST_DIR (default ${PROJECT_ROOT}/dist): the tarball,
# which holds the one top-level directory of that plugin, and its detached armored signature.
# A failure at any step leaves no output of the version for either plugin. No git check is made.
# Nothing is uploaded.
set -euo pipefail
: "${PROJECT_ROOT:?PROJECT_ROOT is empty or unset — run this script through its justfile recipe}"
: "${GEN:?GEN is empty or unset — run this script through its justfile recipe}"

DIST_DIR="${DIST_DIR:-${PROJECT_ROOT}/dist}"
plugin_names="$("${PROJECT_ROOT}/devtools/scripts/_plugin-names.sh")"
plugins=()
while IFS= read -r name; do plugins+=("${name}"); done <<<"${plugin_names}"

function resolve_names() {
  ver="$(PYTHONPATH="${PROJECT_ROOT}" python3 -m "${GEN}" --version)"
  if [[ ! "${ver}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    printf 'mage-dist: version %q is not <major>.<minor>.<patch>; nothing was removed or written.\n' "${ver}" >&2
    exit 1
  fi
  agents_file="$("${PROJECT_ROOT}/devtools/scripts/_harness-value.sh" "${plugins[0]}" mage agents-file)"
  stage="${DIST_DIR}/stage"
  outputs=()
  for plugin in "${plugins[@]}"; do
    outputs+=("${DIST_DIR}/$(tarball "${plugin}")" "${DIST_DIR}/$(tarball "${plugin}").asc")
  done
}

function tarball() {
  printf 'adjagent-mage-%s-v%s.tgz' "${1}" "${ver}"
}

# Runs once validation has passed: no earlier refusal removes anything.
function clean_outputs() {
  command rm -rf "${stage}"
  command rm -f "${outputs[@]}"
}

# The install refuses a target that does not exist. The agents file comes from the renderer, as the
# slot render's does: the install-agents-file path refuses while generator sources are uncommitted.
function stage_plugin() {
  local plugin="${1}" plugin_dir="${2}"
  mkdir -p "${stage}/${plugin_dir}"
  PYTHONPATH="${PROJECT_ROOT}" python3 -m "${GEN}" install "${plugin}" "${stage}/${plugin_dir}" \
    --subdir= --harness=mage >&2
  "${PROJECT_ROOT}/devtools/scripts/render-agents-file.sh" mage "${stage}/${plugin_dir}/${agents_file}" "${plugin}" >&2
}

# COPYFILE_DISABLE keeps macOS tar from adding `._*` AppleDouble entries beside every file;
# --no-xattrs keeps it from writing extended attributes (com.apple.provenance) as pax headers.
function make_tarball() {
  local plugin="${1}" plugin_dir="${2}"
  COPYFILE_DISABLE=1 tar --no-xattrs -czf "${DIST_DIR}/$(tarball "${plugin}")" -C "${stage}" "${plugin_dir}"
  gpg --yes --detach-sign --armor "${DIST_DIR}/$(tarball "${plugin}")"
}

function main() {
  resolve_names
  mkdir -p "${DIST_DIR}"
  clean_outputs
  # A failed build leaves no output of its version; only signed tarballs outlive the script.
  trap 'command rm -rf "${stage}"; command rm -f "${outputs[@]}"' EXIT
  for plugin in "${plugins[@]}"; do
    plugin_dir="$("${PROJECT_ROOT}/devtools/scripts/_harness-value.sh" "${plugin}" mage project-harness-dir)"
    stage_plugin "${plugin}" "${plugin_dir}"
    make_tarball "${plugin}" "${plugin_dir}"
  done
  trap 'command rm -rf "${stage}"' EXIT
  for plugin in "${plugins[@]}"; do
    printf 'mage-dist: %s %s\n' "${DIST_DIR}/$(tarball "${plugin}")" "${DIST_DIR}/$(tarball "${plugin}").asc"
  done
}

main
