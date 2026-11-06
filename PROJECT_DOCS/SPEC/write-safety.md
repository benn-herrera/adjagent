## Write Safety

An install overwrites every definition it renders where the target is absent or carries a generated
banner: the `!GENERATED!` line inside a frontmatter block, or the comment form a skill's supporting
file opens with. A harness-rendered file is ours when it holds the marker that file states about
itself, and any other file at that path refuses like any foreign target. Any other file at a target
— one a project wrote itself, or a directory — refuses the install with nothing written,
naming each such path. So does anything but a directory on the path from ROOT to such a target,
since a write would fail there; what stands at or above ROOT is the operator's own and is not
examined.

A symlink is the file or directory it names. The install reads and writes through it, and never
refuses, skips or reports a path for being one; removing a symlink removes the link and never what
it names. A dangling link at a write target, file or directory, has what it names created. A
dangling link on the way to a target refuses, as does one at a target whose named path sits in a
directory that does not exist, since nothing can be written through either. The install never
creates a symlink.

The install removes — naming each in its
report — every file under a deployed surface of the harness directory that it did not write and that
carries a generated banner, and with them any directory that leaves empty; a file with neither banner
is never touched. Under claude the surfaces walked are the harness directory's, not the plugin's
alone, so the generated files an earlier version wrote straight into the harness directory go.
A claude project install also removes whole, naming each, the package folders that earlier layout
left outside the plugin, `skills/docdicer/tools/` and `skills/kbase/kb-tools/`; a user-level install removes none.
A shipped package's destination is replaced whole, `skills/kbase/kb-tools/` included: a `kbase`
executable and signature an earlier version installed there do not survive a kb install. The
docdicer tools destination is replaced the same way, a `.venv` under it included. A
file a harness ships is replaced whole on each install when the file already at its path carries
`!INSTALLED! … adjagent` in its first ten lines; any other file there refuses the install the same
way. It is not removed by prune: the copy is one-way and no mirror, so a file this repository
stops shipping stays in the consuming project until that project removes it, outside the reach of
every prune. A
harness-rendered file takes the first two rules: replaced whole on each install where it holds the
marker it states, and not removed, since prune walks the three surfaces only. An install's report
names each path it pruned; where the consuming project tracks the installed set, its git is the
record of what an install changed.

One removal is of a file at a path a retired layout used: a claude project
install removes `<harness-dir>/hooks/guardrail.pl`, the flat layout's guardrail script, when it
carries `!INSTALLED! … adjagent` in its first ten lines and the same install writes the plugin's
replacement, that is, when the guardrail's install-time run succeeds; the directory goes with it
if that leaves it empty. A link at that path to a file carrying that header has the link removed;
one that names nothing removes nothing.
A claude project install also removes, from two files the project owns, the entries an earlier
version registered there: the guardrail hook's element of `.claude/settings.json`, when the
guardrail is registered in the plugin by the same install, and, on a kb install, the `kbase` member
of the project's `.mcp.json`. Bytes outside the removed item are kept, the project's other hooks
and servers are never touched, and a container the removal empties is left as `[]` or `{}`. An item
is ours only when its command is exactly one an earlier install wrote (for `kbase`, the bare
`kbase` or a path ending in it), so a hook of the project's that names some other `guardrail.pl`
stays the project's. A file it cannot edit safely — one holding more than one item of ours, or
ours sharing an element with another command — is reported with the item printed, for the user to
remove by hand, and left alone. Settings files are read as strict JSON: one with comments or
otherwise unparseable, and a settings path that lies behind a non-directory or is not a regular
file, is left alone, and reported only when
its text contains our old guardrail command or our `kbase` entry, as a stranded entry to remove by
hand. Removal never refuses the install: a file that is not UTF-8, is not a JSON object, or holds a
container on the entry's path (`hooks`, `PreToolUse`, `mcpServers`) of the wrong type, `null`
included, is left alone and reported on the same terms. A kb install's `kbase` settings file under claude and mage sits at the plugin root,
inside ROOT, and, being written into, is held to this instead: left alone where a non-directory or
non-regular file stands in the way, refused where it is not UTF-8 or nests a non-object, `null` included, where the entry goes,
or where a dangling link stands on the way to it, or at it with the directory of the path it names absent. A
user-level install removes none of these entries, since it never wrote them. A hook skipped for a
failed install-time run removes neither the guardrail entry nor the flat script, and leaves any
script, registration or entry an earlier install wrote where it stands; the report names those that
are the install's own. The `kbase` member is removed whenever the install writes the kb MCP entry,
whatever became of the hook.

An install that would change nothing reports the target up to date, exits 0 and touches nothing: no
file written, no mode or modification time changed, no package destination replaced, no
`tools/.venv` rebuilt and no `--install` re-run. "Nothing" is judged on the result: every file the
install would write is already byte-identical and mode-identical, and none would be created or
removed. Changing `--harness`, `--family`, the model map or `--with-kb` changes bytes, so that install
proceeds. A `.venv` directory is not install output and is outside the comparison, so its presence
alone never makes an install proceed. No version marker or stamp file decides this.

`--dry-run` runs the same judgment and writes nothing, in the target or elsewhere that outlives the
run. It prints what the install would change, grouped as created, changed and removed, each path
relative to the project root, or absolute for a file outside it, such as the global agents file, and
exits 0; where nothing would change it says the target is up to
date. Where the install would replace a docdicer `tools/.venv`, the dry run also says so and that
the install would rebuild it with `--install`, which needs the network. Every path it prints and
every refusal it reports names the real target. What the install would leave alone or skip, with the
reason, is reported on stderr on an up-to-date run and a dry run as on a changing one. It reports the
refusals it can foresee, a dangling link on the way to a target among them, and the same refusals
for an MCP settings file the install writes into.

