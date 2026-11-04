# docdicer targets. This file is installed at
# <harness-dir>/skills/docdicer/tools/runner-snippets/ — <harness-dir> being
# the project's .claude or .opencode — and is included from the consuming
# project's Makefile by one line (never copied into it):
#
#     -include <harness-relpath>/skills/docdicer/tools/runner-snippets/docdicer.mk
#
# A consumer running just instead imports `docdicer.just` from the same directory
# with `import?` (just >= 1.33).
#
# The non-fatal `-include` form is deliberate: if the installed tree is absent —
# not yet installed, or removed — the consumer's Makefile keeps working and only
# these targets go missing.
#
# The launcher, tools/docdicer, sits one directory up from this file, so it is
# found from the snippet's own path in MAKEFILE_LIST, never from the project
# root. It is POSIX sh and runs docdicer from a venv beside it; until
# `tools/docdicer --install` has built that venv, every target prints how to
# install and fails.
#
# The targets run from the consumer's repo root, where make runs, so the default
# roots below are relative to it. Plain POSIX recipe lines — no SHELL override;
# existing recipes keep their own shell. Variables are overridable on the command
# line or in the environment, and unquoted, so they split on spaces.
#
# Targets:
#   docdicer:      run docdicer with DOCDICER_ARGS: make docdicer DOCDICER_ARGS='dice-doc big.md out/'
#   docdicer-check:   check links and #anchors under DOCDICER_ROOTS, then that every document under DOCDICER_TREE is listed and reachable
#
# The link-check target is named `docdicer-check`, so it cannot collide
# with a consumer's own `check-links`.

DOCDICER_LAUNCHER := $(dir $(lastword $(MAKEFILE_LIST)))../docdicer
DOCDICER_ARGS ?=
DOCDICER_ROOTS ?= PROJECT_DOCS *.md
DOCDICER_TREE ?= PROJECT_DOCS

.PHONY: docdicer docdicer-check

docdicer:
	@"$(DOCDICER_LAUNCHER)" $(DOCDICER_ARGS)

docdicer-check:
	@"$(DOCDICER_LAUNCHER)" check-links $(DOCDICER_ROOTS) && "$(DOCDICER_LAUNCHER)" check-tree $(DOCDICER_TREE)
