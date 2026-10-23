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
# Assumed consumer layout: the repo root (where just runs) contains kb-root/,
# and this fragment sits beside the installed `kbase` executable under
# <harness-dir>/skills/kbase/kb-tools/. kbase finds the KB from the working
# directory, so these recipes run from the repo root.
#
# The binary is found from this fragment's own location: the snippets
# directory's parent is the installed kb-tools directory, and kbase sits
# there (`kbase.exe` on Windows). The path is absolute, so it resolves to the
# installed executable however the consumer invokes just.
#
# Recipe names carry a `kb-` prefix, so they cannot collide with a project's
# own verify/refresh/stats. Plain recipe lines, no `set shell` — nothing here
# needs bash.
#
# Recipes:
#   kb-verify          verify KB link integrity and claim-graph metadata
#   kb-refresh         refresh mechanically maintained KB metadata
#   kb-stats           print KB claim-graph stats

KB_TOOLS_DIR := parent_directory(source_directory())
KBASE := KB_TOOLS_DIR + "/kbase" + (if os_family() == "windows" { ".exe" } else { "" })

[doc("verify KB link integrity and claim-graph metadata")]
kb-verify:
    @"{{KBASE}}" verify

[doc("refresh mechanically maintained KB metadata")]
kb-refresh:
    "{{KBASE}}" refresh

[doc("print KB claim-graph stats")]
kb-stats:
    "{{KBASE}}" stats
