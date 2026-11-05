## Write Safety

An install overwrites every definition it renders where the target is absent or carries a generated
banner: the `!GENERATED!` line inside a frontmatter block, or the comment form a skill's supporting
file opens with. A harness-rendered file is ours when it holds the marker that file states about
itself, and any other file at that path refuses like any foreign target. Any other file at a target
— one a project wrote itself, a directory, a symlink — refuses the install with nothing written,
naming each such path. So does a symlink, or anything but
a directory, on the path from ROOT to such a target, since a write would pass through it or fail
there; what stands at or above ROOT is the operator's own and is not examined. It removes — naming each in its
report — every file under a deployed surface of the harness directory that it did not write and that
carries a generated banner, and with them any directory that leaves empty; a file with neither banner
is never touched. Under claude the surfaces walked are the harness directory's, not the plugin's
alone, so the generated files an earlier version wrote straight into the harness directory go.
A claude project install also removes whole, naming each, the package folders that earlier layout
left outside the plugin, `skills/docdicer/tools/` and `skills/kbase/kb-tools/`, unless a symlink
stands on the way, which is named and left; a user-level install removes none.
A shipped package's destination is replaced whole, `skills/kbase/kb-tools/` included: a `kbase`
executable and signature an earlier version installed there do not survive a kb install. The
docdicer tools destination is replaced the same way, a `.venv` under it included. A
file a harness ships is replaced whole on each install when the file already at its path carries
`!INSTALLED! … adjagent` in its first ten lines; any other file there refuses the install the same
way. It is never removed: the copy is one-way and no mirror, so a file this repository stops
shipping stays in the consuming project until that project removes it, outside the reach of every
prune. A harness-rendered file takes the same two rules: replaced whole on each install where it
holds the marker it states, and never removed, since prune walks the three surfaces only.
A claude install also edits a file the project owns, `.claude/settings.json`, to register the
guardrail hook: bytes outside the hook's own entry are kept, an earlier install's entry is replaced
in place, and the project's other hooks are never touched. An element is the hook's own only when
its command is exactly the one an install writes, so a hook of the project's that names some other
`guardrail.pl` stays the project's. One settings file serves the project whatever the harness
directory, so an install under a different `--subdir` replaces the entry of the first: a project
has one guardrail. A file it cannot edit safely — one with comments, more than one entry of ours, or
ours sharing an element with another command — is reported with the entry printed, and left alone.
So is a settings path that is a symlink, dangling or not, that lies behind a symlink or a
non-directory, or that is not a regular file; the report names which. A settings file that is not
UTF-8, or holds a `hooks` that is not an object (`null` included) or a `PreToolUse` that is not an
array, refuses the install with nothing written, as does a harness directory whose path holds a
`"`, `$`, backtick or `\` where the hook is to be registered, the entry being unable to name it. A
kb install's `kbase` settings file is held to the same, wherever it lives — under claude and mage it
sits at the plugin root, inside ROOT: left alone where a symlink or non-regular file stands in the way,
refused where it is not UTF-8 or nests a non-object, `null` included, where the entry goes. A hook
skipped for a failed install-time run leaves the settings file and any script or entry an earlier
install wrote where they stand, and the report names those that are the install's own. An install's report names each
path it pruned; where the consuming project tracks the installed set, its git is the record of what an
install changed.

An install that would change nothing reports the target up to date, exits 0 and touches nothing: no
file written, no mode or modification time changed, no package destination replaced, no
`tools/.venv` rebuilt and no `--install` re-run. "Nothing" is judged on the result: every file the
install would write is already byte-identical and mode-identical, and none would be created or
removed. Changing `--harness`, `--family`, the model map or `--with-kb` changes bytes, so that install
proceeds. A `.venv` directory is not install output and is outside the comparison, so its presence
alone never makes an install proceed. No version marker or stamp file decides this.

`--dry-run` runs the same judgment and writes nothing, in the target or elsewhere that outlives the
run. It prints what the install would change, grouped as created, changed and removed, each path
relative to the project root, and exits 0; where nothing would change it says the target is up to
date. Where the install would replace a docdicer `tools/.venv`, the dry run also says so and that
the install would rebuild it with `--install`, which needs the network. Every path it prints and
every refusal it reports names the real target. What the install would leave alone or skip, with the
reason, is reported on stderr on an up-to-date run and a dry run as on a changing one. It reports the
refusals it can foresee, a symlinked surface or package destination among them; a symlink or
non-directory on the path to a target, such as the directory above a settings file, is judged by the
install itself and a dry run may not foresee it.

