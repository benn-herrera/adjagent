#!/usr/bin/env bash
# `tag`'s body: a tag names a commit whose own files carry the number it is tagged with, so this
# refuses while `adjagent/` is uncommitted — the same reasoning
# `agents_file.uncommitted_sources` applies to publishing the agents file, and the lines it prints
# are that check's own. The number is read from the `version` verb rather than restated here,
# `adjagent/version.py` holding the one copy. The tag is lightweight, as every tag in this
# repository is, and nothing is pushed: the operator pushes.
set -euo pipefail
: "${PROJECT_ROOT:?PROJECT_ROOT is empty or unset — run this script through its justfile recipe}"
: "${GEN:?GEN is empty or unset — run this script through its justfile recipe}"

# The `adjagent` pathspec below is relative to the working directory, so the
# repository root is named rather than assumed.
cd "${PROJECT_ROOT}"
dirty="$(git status --porcelain -- adjagent)"
if [[ -n "${dirty}" ]]; then
    printf '%s\n' "error: adjagent/ has uncommitted changes — a tag must name a commit whose files carry the version it is tagged with:" >&2
    printf '%s\n' "${dirty}" >&2
    exit 1
fi
version="$(PYTHONPATH="${PROJECT_ROOT}" python3 -m "${GEN}" version)"
# An empty reading would tag the commit `v` instead of failing, and a wrong
# tag is the one thing this recipe can produce that nothing else corrects.
if [[ -z "${version}" ]]; then
    printf '%s\n' "error: 'python3 -m ${GEN} version' printed nothing — nothing tagged" >&2
    exit 1
fi
tag="v${version}"
if git rev-parse --verify --quiet "refs/tags/${tag}" > /dev/null; then
    printf '%s\n' "error: tag '${tag}' already exists — bump adjagent/version.py before tagging again" >&2
    exit 1
fi
GPG_TTY=$(tty) git tag -s "${tag}" -m"release ${tag}"
git tag -v "${tag}"
