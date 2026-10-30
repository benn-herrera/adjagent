#!/usr/bin/env bash
# `mage-dist`'s body. Builds the mage plugin from the working tree as it stands and signs the
# tarball. Writes two files to DIST_DIR (default ${PROJECT_ROOT}/dist): the tarball, which holds one
# top-level `adjagent/` directory, and its detached armored signature. No git check is made.
# Nothing is uploaded.
set -euo pipefail
: "${PROJECT_ROOT:?PROJECT_ROOT is empty or unset — run this script through its justfile recipe}"
: "${GEN:?GEN is empty or unset — run this script through its justfile recipe}"

DIST_DIR="${DIST_DIR:-${PROJECT_ROOT}/dist}"

function resolve_names() {
  ver="$(PYTHONPATH="${PROJECT_ROOT}" python3 -m "${GEN}" version)"
  if [[ ! "${ver}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    printf 'mage-dist: version %q is not <major>.<minor>.<patch>; nothing was removed or written.\n' "${ver}" >&2
    exit 1
  fi
  agents_file="$("${PROJECT_ROOT}/devtools/scripts/_harness-value.sh" mage agents-file)"
  plugin_dir="$("${PROJECT_ROOT}/devtools/scripts/_harness-value.sh" mage project-harness-dir)"
  tgz="adjagent-mage-v${ver}.tgz"
  tgz_asc="${tgz}.asc"
  stage="${DIST_DIR}/stage"
}

# Runs once validation has passed: no earlier refusal removes anything.
function clean_outputs() {
  command rm -rf "${stage}"
  command rm -f "${DIST_DIR}/${tgz}" "${DIST_DIR}/${tgz_asc}"
}

# `install.sh` refuses a target that does not exist. The agents file comes from the renderer, as the
# slot render's does: the install-agents-file path refuses while generator sources are uncommitted.
function stage_plugin() {
  mkdir -p "${stage}/${plugin_dir}"
  "${PROJECT_ROOT}/devtools/scripts/install.sh" "${stage}/${plugin_dir}" \
    --subdir= --harness=mage >&2
  "${PROJECT_ROOT}/devtools/scripts/render-agents-file.sh" mage "${stage}/${plugin_dir}/${agents_file}" >&2
}

# COPYFILE_DISABLE keeps macOS tar from adding `._*` AppleDouble entries beside every file;
# --no-xattrs keeps it from writing extended attributes (com.apple.provenance) as pax headers.
function make_tarball() {
  COPYFILE_DISABLE=1 tar --no-xattrs -czf "${DIST_DIR}/${tgz}" -C "${stage}" "${plugin_dir}"
  gpg --yes --detach-sign --armor "${DIST_DIR}/${tgz}"
}

function main() {
  resolve_names
  mkdir -p "${DIST_DIR}"
  clean_outputs
  # A failed build leaves neither output of its version; only a signed tarball outlives the script.
  trap 'command rm -rf "${stage}"; command rm -f "${DIST_DIR}/${tgz}" "${DIST_DIR}/${tgz_asc}"' EXIT
  stage_plugin
  make_tarball
  trap 'command rm -rf "${stage}"' EXIT
  printf 'mage-dist: %s %s\n' "${DIST_DIR}/${tgz}" "${DIST_DIR}/${tgz_asc}"
}

main
