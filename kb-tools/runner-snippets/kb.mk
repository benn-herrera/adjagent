# KB maintenance targets. This file is installed at
# <harness-dir>/adj-tools/kb-tools/runner-snippets/ — <harness-dir> being the
# project's .claude or .opencode — and is included from the consuming
# project's Makefile by one installed line (never copied into it):
#
#     -include <harness-relpath>/adj-tools/kb-tools/runner-snippets/kb.mk
#
# A consumer running just instead gets the `import?` line pointing at
# `<harness-relpath>/adj-tools/kb-tools/runner-snippets/kb.just` (just >= 1.33).
#
# The line is written by `install-with-kb`, run from the consumer root — not
# by anything in this tree. The non-fatal `-include` form is deliberate: if
# the installed tree is absent — not yet installed, or removed — the
# consumer's Makefile keeps working and only these KB targets go missing.
#
# Assumed consumer layout: the repo root (where make runs) contains kb-root/,
# and this fragment sits beside the installed `kbase` executable under
# <harness-dir>/adj-tools/kb-tools/. kbase finds the KB from the working
# directory, so these targets run from the repo root.
#
# The binary is found from this fragment's own location: the snippets
# directory's parent is the installed kb-tools directory, and kbase sits
# there (`kbase.exe` on Windows). The path is absolute — `$(abspath)` makes
# it so, and the assignment is `:=` because the last word of MAKEFILE_LIST is
# this file only while it is being read — so it resolves to the installed
# executable however the consumer invokes make.
#
# Target names carry a `kb-` prefix, so they cannot collide with a project's
# own verify/refresh/stats. Plain POSIX recipe lines — no SHELL override;
# existing recipes keep their own shell.
#
# Targets:
#   kb-verify          verify KB link integrity and claim-graph metadata
#   kb-refresh         refresh mechanically maintained KB metadata
#   kb-stats           print KB claim-graph stats

KB_TOOLS_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))../)
EXE := $(if $(findstring Windows,$(OS)),.exe,)
KBASE := $(KB_TOOLS_DIR)/kbase$(EXE)

.PHONY: kb-verify kb-refresh kb-stats

kb-verify:
	@$(KBASE) verify

kb-refresh:
	$(KBASE) refresh

kb-stats:
	$(KBASE) stats
