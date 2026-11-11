# docdicer targets. This file is installed at
# <harness-relpath>/skills/docdicer/tools/runner-snippets/ — <harness-relpath>
# being either plugin's install directory relative to the project root:
# .claude/skills/<plugin> under claude, .opencode/plugins/<plugin> under
# opencode — and is included from the consuming project's Makefile by one
# installed line (never copied into it):
#
#     -include <harness-relpath>/skills/docdicer/tools/runner-snippets/docdicer.mk
#
# A consumer running just instead gets the `import?` line (just >= 1.33)
# pointing at `docdicer.just` in the same directory.
#
# The line is written by a project install of either plugin, run from the
# consumer root — not by anything in this tree.
#
# The non-fatal `-include` form is deliberate: if the installed tree is absent —
# not yet installed, or removed — the consumer's Makefile keeps working and only
# these targets go missing.
#
# The launcher, tools/docdicer, sits one directory up from this file, so it is
# found from the snippet's own path in MAKEFILE_LIST, never from the project
# root. It is a bash script and runs docdicer from a venv beside it, which it
# builds, and installs docdicer into, on first use.
#
# Plain POSIX recipe lines — no SHELL override; existing recipes keep their own
# shell. DOCDICER_ARGS is overridable on the command line or in the environment,
# and unquoted, so it splits on spaces.
#
# Targets:
#   docdicer:         run docdicer with DOCDICER_ARGS: make docdicer DOCDICER_ARGS='dice-doc big.md out/'
#   docdicer-check-plan: run docdicer's check for ACTIVE_PLAN kanban format compliance
#   docdicer-kanban:  run docdicer kanban board for this project (blocks with running http server)
#   docdicer-help:    show help for docdicer targets

DOCDICER_LAUNCHER := $(dir $(lastword $(MAKEFILE_LIST)))../docdicer
DOCDICER_ARGS ?=

.PHONY: docdicer docdicer-check-plan docdicer-help docdicer-kanban

docdicer-help:
	@grep '^#   docdicer-' "$(lastword $(MAKEFILE_LIST))" | sed 's:^#: :'

docdicer:
	@"$(DOCDICER_LAUNCHER)" $(DOCDICER_ARGS)

docdicer-check-plan:
	@"$(DOCDICER_LAUNCHER)" check-plan

docdicer-kanban:
	@"$(DOCDICER_LAUNCHER)" kanban
