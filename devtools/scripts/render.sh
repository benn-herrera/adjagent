#!/usr/bin/env bash
# `render`'s body. A slot is rebuilt on demand and never read back as input to itself, so no slot
# is ever mistaken for a baseline. The working sequence is to do the work, `just render`, then
# `just render-diff` against the reference slots.
#
# This scan mirrors install.sh's own leading-flag scan: the first argument that is not a `--` flag,
# wherever it sits, is the slug (default `latest`) rather than a fixed positional parameter, so
# `just render --family=gemma-4` tunes the `latest` slot instead of mistaking the flag for a slug.
# `--subdir=` is fixed ahead of the forwarded flags in `_render-slot`, so the render always lands
# directly under the slot with no .claude nest.
#
# The flags that produced a slot are recorded in it as RENDER-FLAGS.txt, so a `render-diff` between
# two slots rendered under different tunings shows why they differ instead of reading as unexplained
# drift. A comparison's flag sets belong to the invocations that produced each side, never to what
# an operator recalls between them.
#
# The slot also holds the harness agents file for one harness, written through the
# render-agents-file script: at harness/<name>/<the harness's agents-file name>, or — for a harness
# whose own files sit at its root — at <agents-file> beside the slot's `.mcp.json`. `--harness=NAME`
# (default claude) is the one flag this script reads as well as forwards, in any position — the
# agents file and the install's definitions render under the same harness — and it is recorded in
# RENDER-FLAGS.txt like any other flag given. The file's name is read from the harness ahead of
# anything else, so an unknown harness fails before the slot is touched.
#
# The slot is removed and rebuilt on every render. A slug starting with `reference` is refused with
# nothing touched: those slots are the pre-1.0 oracle until stage 6 re-renders them.
#
# A slot is rendered with the kb set as well as the base product — the kb definitions, the kb-tools
# package, and the slot's own MCP entry (the slot is its own project root) — so a `render-diff`
# compares the kb half too. A plugin's slot (`mage`) carries no runner include line and no
# `Makefile`, its harness writing neither.
set -euo pipefail
: "${PROJECT_ROOT:?PROJECT_ROOT is empty or unset — run this script through its justfile recipe}"

slug="latest"
args=()
have_slug=""
for arg in "$@"; do
    if [[ -z "${have_slug}" && "${arg}" != --* ]]; then
        slug="${arg}"
        have_slug=1
    else
        args+=("${arg}")
    fi
done
if [[ "${slug}" == reference* ]]; then
    printf '%s\n' "error: slot '${slug}' is protected — a slug starting with 'reference' is the pre-1.0 oracle, which render never renders" >&2
    exit 1
fi
"${PROJECT_ROOT}/devtools/scripts/_render-slot.sh" "${slug}" ${args[@]+"${args[@]}"}
