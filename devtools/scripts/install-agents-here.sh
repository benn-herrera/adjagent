#!/usr/bin/env bash
# `install-agents-here`'s body: update this project's own agent installation, base product only —
# the plain `install` verb once per harness. The kb set belongs to a target project, which is what
# `just install-with-kb <that-project>` is for: this repository builds the kb definitions and the
# kb-tools package but does not use them, so nothing here writes skills/kbase/kb-tools/ or a
# project-root MCP entry. No runner include line either: an install never writes
# one into this repository's own justfile. A harness directory that already holds the generated
# skills/kbase/SKILL.md is a kb install even here — the one way this recipe can still install kb. The opencode line overrides the tier map because the default
# family's tier texts name claude models, which opencode refuses.
set -euo pipefail
: "${PROJECT_ROOT:?PROJECT_ROOT is empty or unset — run this script through its justfile recipe}"

"${PROJECT_ROOT}/devtools/scripts/install.sh" "${PROJECT_ROOT}" --harness=claude
"${PROJECT_ROOT}/devtools/scripts/install.sh" "${PROJECT_ROOT}" --harness=opencode --model-tier-map=default
