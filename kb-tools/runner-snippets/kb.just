# KB maintenance recipes. This file is installed at
# <harness-dir>/skills/kbase/kb-tools/runner-snippets/ — <harness-dir> being
# the project's .claude or .opencode — and is imported from the consuming
# project's justfile by one installed line (never copied into it):
#
#     import? '<harness-relpath>/skills/kbase/kb-tools/runner-snippets/kb.just'
#
# A consumer running make instead gets the `-include` line pointing at
# `<harness-relpath>/skills/kbase/kb-tools/runner-snippets/kb.mk`.
#
# The line is written by `install-with-kb`, run from the consumer root — not
# by anything in this tree. `import?` requires just >= 1.33; the optional form
# is deliberate: if the installed tree is absent — not yet installed, or
# removed — the consumer's justfile keeps working and only these KB recipes
# go missing.
#
# Assumed consumer layout: the repo root (where just runs) contains kb-root/.
# kbase finds the KB from the working directory, so these recipes run from
# the repo root.
#
# The recipes run `kbase` from PATH; the user installs it themselves — the kbase skill's
# references/installing.md walks through it.
#
# Recipe names carry a `kb-` prefix, so they cannot collide with a project's
# own verify/refresh/stats. Plain recipe lines, no `set shell` — nothing here
# needs bash.

KBASE := "kbase"

[doc("show help on kb just recipes")]
kb-help:
    @just --justfile "{{justfile()}}" --list | grep -E '^[ \t]+kb-'

[doc("create a new, empty KB. refuses if kb-root exists")]
kb-init:
    "{{KBASE}}" init

[doc("verify KB link integrity and claim-graph metadata")]
kb-verify:
    @"{{KBASE}}" verify

[doc("refresh mechanically maintained KB metadata")]
kb-refresh:
    "{{KBASE}}" refresh

[doc("print KB claim-graph stats")]
kb-stats:
    "{{KBASE}}" stats

[doc("run an inference scoring pass over the KB")]
kb-score:
  "{{KBASE}}" score

[doc("generate a LaTeX file set from the KB")]
kb-export-latex:
    "{{KBASE}}" export-latex
