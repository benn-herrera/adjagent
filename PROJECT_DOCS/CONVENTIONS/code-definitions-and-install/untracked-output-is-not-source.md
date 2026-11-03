### Untracked output is not source

An untracked file under `.claude/`, `.opencode/` or `rendered/` is render or install output, not
source. SPEC.md states what an install ships and to which destination (Deployed Surfaces), and
what a re-install replaces (Write Safety); ARCHITECTURE.md's Repo Layout holds the trees each is
sourced from. The next install replaces what it wrote, `skills/kbase/kb-tools/` whole — so a
change belongs at the source, not in the copy. Before an edit brief names a path, `git ls-files <path>` settles
which it is, and the brief names the source. Running definitions point at the copy, which is how a
brief comes to name it.
