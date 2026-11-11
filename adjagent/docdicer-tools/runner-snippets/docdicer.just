# docdicer recipes. This file is installed at
# <harness-relpath>/skills/docdicer/tools/runner-snippets/ — <harness-relpath>
# being either plugin's install directory relative to the project root:
# .claude/skills/<plugin> under claude, .opencode/plugins/<plugin> under
# opencode — and is imported from the consuming project's justfile by one
# installed line (never copied into it):
#
#     import? '<harness-relpath>/skills/docdicer/tools/runner-snippets/docdicer.just'
#
# A consumer running make instead gets the `-include` line pointing at
# `docdicer.mk` in the same directory.
#
# The line is written by a project install of either plugin, run from the
# consumer root — not by anything in this tree.
#
# `import?` requires just >= 1.33; the optional form is deliberate: if the
# installed tree is absent — not yet installed, or removed — the consumer's
# justfile keeps working and only these recipes go missing.
#
# The launcher, tools/docdicer, sits one directory up from this file, so it is
# found from the snippet's own location, never from the project root. It is
# a bash script and runs docdicer from a venv beside it, which it builds, and
# installs docdicer into, on first use.
#
# Plain recipe lines, no `set shell`.

docdicer_launcher := source_directory() / ".." / "docdicer"

[doc("show help on docdicer just recipes")]
docdicer-help:
    @just --justfile "{{justfile()}}" --list | grep -E '^[ \t]+docdicer-'

[doc("run docdicer with the given arguments: just docdicer dice-doc big.md out/")]
[positional-arguments]
docdicer *args:
    @"{{docdicer_launcher}}" "${@}"

[doc("run docdicer's check for ACTIVE_PLAN kanban format compliance")]
docdicer-check-plan:
  @"{{docdicer_launcher}}" check-plan

[doc("run docdicer kanban board for this project (blocks with running http server)")]
docdicer-kanban:
  @"{{docdicer_launcher}}" kanban
