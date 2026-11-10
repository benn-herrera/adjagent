# KB maintenance targets. This file is installed at
# <harness-relpath>/skills/kbase/kb-tools/runner-snippets/ — <harness-relpath>
# being the kbase plugin's install directory relative to the project root:
# .claude/skills/kbase under claude, .opencode/plugins/kbase under opencode — and is
# included from the consuming project's Makefile by one installed line (never
# copied into it):
#
#     -include <harness-relpath>/skills/kbase/kb-tools/runner-snippets/kb.mk
#
# A consumer running just instead gets the `import?` line pointing at
# `<harness-relpath>/skills/kbase/kb-tools/runner-snippets/kb.just` (just >= 1.33).
#
# The line is written by `adjagent install kbase`, run from the consumer root — not
# by anything in this tree. The non-fatal `-include` form is deliberate: if
# the installed tree is absent — not yet installed, or removed — the
# consumer's Makefile keeps working and only these KB targets go missing.
#
# Assumed consumer layout: the repo root (where make runs) contains kb-root/.
# kbase finds the KB from the working directory, so these targets run from
# the repo root.
#
# The targets run `kbase` from PATH; the user installs it themselves — the kbase skill's
# references/installing.md walks through it.
#
# Target names carry a `kb-` prefix, so they cannot collide with a project's
# own verify/stats. Plain POSIX recipe lines — no SHELL override;
# existing recipes keep their own shell.
#
# Targets:
#   kb-help:            show help on kb make targets
#   kb-init:            create a new, empty KB. refuses if kb-root exists
#   kb-verify:          verify KB link integrity and claim-graph metadata
#   kb-update-format:   convert the KB to the current format and re-derive its pages and sheets; needs a clean kb-root
#   kb-stats:           print KB claim-graph stats
#   kb-score:           run an inference scoring pass over the KB
#   kb-export-latex:    generate a LaTeX file set from the KB

# KB
KBASE := kbase

.PHONY: kb-help kb-init kb-verify kb-update-format kb-stats kb-score kb-export-latex

kb-help:
	@grep '^#   kb-' "$(lastword $(MAKEFILE_LIST))" | sed 's:^#: :'

kb-init:
	$(KBASE) init

kb-verify:
	@$(KBASE) verify

kb-update-format:
	$(KBASE) update-format

kb-stats:
	$(KBASE) stats

kb-score:
	$(KBASE) score

kb-export-latex:
	$(KBASE) export-latex
