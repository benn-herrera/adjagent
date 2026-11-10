# docdicer recipes. This file is installed at
# <harness-relpath>/skills/docdicer/tools/runner-snippets/ — <harness-relpath>
# being the devpro plugin's install directory relative to the project root:
# .claude/skills/devpro under claude, .opencode/plugins/devpro under opencode —
# and is imported from the consuming project's justfile by one line (never
# copied into it):
#
#     import? '<harness-relpath>/skills/docdicer/tools/runner-snippets/docdicer.just'
#
# A consumer running make instead includes `docdicer.mk` from the same directory
# with `-include`.
#
# `import?` requires just >= 1.33; the optional form is deliberate: if the
# installed tree is absent — not yet installed, or removed — the consumer's
# justfile keeps working and only these recipes go missing.
#
# The launcher, tools/docdicer, sits one directory up from this file, so it is
# found from the snippet's own location, never from the project root. It is
# a bash script and runs docdicer from a venv beside it; until `tools/docdicer
# --install` has built that venv, every recipe prints how to install and fails.
#
# The link-check recipe is named `docdicer-check`, so it cannot collide
# with a consumer's own `check-links`; just refuses a duplicate from an import.
#
# The recipes run from the consumer's repo root, where just runs, so the
# default roots below are relative to it. Plain recipe lines, no `set shell`.

docdicer_launcher := source_directory() / ".." / "docdicer"

[doc("run docdicer with the given arguments: just docdicer dice-doc big.md out/")]
[positional-arguments]
docdicer *args:
    @"{{docdicer_launcher}}" "$@"

[doc("check every relative link and #anchor under the roots (default PROJECT_DOCS and the top-level *.md files), then that every document under the tree (default PROJECT_DOCS) is listed by its parent and reachable from its entry point; exit 1 on a broken link or an orphan")]
docdicer-check tree="PROJECT_DOCS" *roots="PROJECT_DOCS *.md":
    @"{{docdicer_launcher}}" check-links {{roots}} && "{{docdicer_launcher}}" check-tree "{{tree}}"
