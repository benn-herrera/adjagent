### Shipped files

The repository's fourth file class is a **shipped package**: plain code, never rendered and so never
carrying a `!GENERATED!` banner in this repository, its tests beside it where it has them, installed
by explicit mapping to a frozen destination under the install ROOT — frozen because an installed
consumer's own artifacts, such as the runner include line an install writes into the consumer's
justfile or Makefile, name that destination directly
and cannot be asked to notice a source-side rearrangement. Its installed copy is stamped like any
other install emission whose filetype admits a comment: the `!INSTALLED!` banner, not `!GENERATED!`
— a shipped package is source taken as-is, never a render. `SHIPPED_PACKAGES` is the table of those
an install delivers by explicit mapping: each row a repository-top-level package and the destination
under the install ROOT it lands at, beside the three definition surfaces, under `adj-tools/`. It
holds no row today, so no install of this version delivers one. `kb-tools/` is a shipped package
installed at its own stated destination rather than by that table: `skills/kbase/kb-tools/`, inside
the `kbase` skill's own directory and so inside the `skills/` surface — the one package destination
outside `adj-tools/`, a skill carrying its tooling in its own directory — holding only the runner
snippets, and not an importable package either, read by the consumer through the runner include
line. The snippets run `kbase` from `PATH`. No package is a
definition: `adj-tools/` is outside the dispatch namespace entirely, and a package under a skill's
directory is neither its `SKILL.md` nor a supporting file it lists.

A harness's shipped files are the fifth class: copied as they stand, never rendered. A harness also
*renders* files of its own into ROOT — mage's manifest is the one — which are generated, not copied,
carry no banner, and are replaced whole.
An install copies the installing harness's set into ROOT — the harness directory itself — save a
file conditional on a run at install time (below), so a harness file lands at the path it holds
below that directory: opencode's sits at `<harness-dir>/plugins/guardrail.ts` today and claude's at
`<harness-dir>/hooks/guardrail.pl` (mage ships none), beside the surfaces and outside all three.
Each keeps its bytes and its mode: the install stamps nothing on them. Every such file carries an
`!INSTALLED! … adjagent` header in its first ten lines — the guardrail files' name this repository
and forbid edits — as the file's own text, which travels with it. A harness shipping none copies nothing, which
is not an error. A harness file may be conditional on a run at install time: claude's hook is
delivered only when one run of the script on the installing machine succeeds within a few seconds,
and is otherwise skipped, with the reason reported and the rest of the install unaffected. Both
guardrails are to block the same calls but one spelling, which only the claude guardrail reads: a path word
of a shell command that opens with `$CLAUDE_PROJECT_DIR` or `${CLAUDE_PROJECT_DIR}` is read as that
path under the project directory. File-tool arguments are read literally, and no other variable is
read. Their mutation check blocks shell commands that change a file
behind the edit tools, such as in-place `sed`, `perl` or `ruby` edits, redirects, `tee`, `cp` or
`mv` onto an existing file, and inline scripts that write, and allows writes into scratch. A
relative target is judged lexically against the working directory of the call, scratch against the
project directory, and a heredoc's body is not read as shell. Their `.index/` check is active only
where the harness directory holds the kbase skill's `SKILL.md`, which they look for on every call,
so a base install is never refused by it. It refuses a call that reaches into
`<project>/kb-root/.index/`, whose records kbase's own tools read and change:
- a shell command with a word naming a path there, existence checks (`stat`, and `test` or `[` with `-e`, `-d` or `-f`) excepted
- a recursive `grep`, `rg`, `find`, `ls -R` or `tree` rooted in `kb-root/` that does not exclude
  `.index`
- a file-tool call whose path lies there: Claude's Read, Write, Edit and NotebookEdit, opencode's
  read, write, edit and patch
- a Grep or Glob rooted in `kb-root/` whose file filter could match a record

This check follows symlinks, so a link into `.index/` is refused. Claude's runs at session time and
needs perl with core `JSON::PP`; an install also registers it as a `PreToolUse` entry for Bash and the
file tools (Read, Write, Edit, NotebookEdit, Grep, Glob) in the project's `.claude/settings.json`,
whatever the harness directory is, keeping every other byte of that file (Write Safety, below). The
entry runs the script only where it stands readable: where it is missing — a project that commits the
settings file but not the script — a call reports the missing path on stderr and proceeds, and is not
blocked.

