## Write Safety

An install overwrites every rendered definition where the destination is absent or carries a
generated banner: the `!GENERATED!` line inside the frontmatter, or the comment form a supporting
file opens with, which every rendered file does under opencode. A generated banner names a source
under `devpro/` (`!GENERATED! from devpro/…`). A harness-rendered file is ours when it holds its ownership marker, and any other
file at that path refuses like any foreign file. Any other file at a destination — one a project
wrote itself, or a directory — refuses the install with nothing written, naming each such path. A
rendered file or harness resource a release before 0.17.0 wrote names its source under the
generator's earlier name, so it is foreign: at a destination it refuses the install, and prune
leaves it.

The install removes — naming each in its install report — every file under a deployed surface of
its install directory, and of no other directory, that it did not write and that carries a generated
banner, and with them any
directory that leaves empty; this removal takes no file that lacks a generated banner. The install
directory itself is never removed, and a directory that was already empty stays. A package
destination is replaced whole, `skills/kbase/kb-tools/` included, except a `.venv` directly under it,
which stays. The development scripts package and the docdicer tools package are replaced the same way.
A harness resource is replaced whole on each
install when the file already at its path carries `!INSTALLED! … devpro` in its first ten lines;
any other file there refuses the install the same way. It is not removed by prune: a harness
resource this repository stops shipping stays until the consuming project removes it. A
harness-rendered file takes the first two rules: replaced whole on each install where it holds its
ownership marker, and not removed, since prune walks the three deployed surfaces only. The install
report names each path it pruned. A changing install's report ends with one line counting the
rendered files and the copied files; harness resources are counted as copied. An install keeps no
backup of a file it overwrites or removes. The agents file's one rolling backup (Agents File) is
the only one.

No install writes `.claude/settings*`, `opencode.json` or `opencode.jsonc`. A guardrail skipped for a
failed install-time probe leaves any script or registration an earlier install wrote where it
stands; the report names those that are the install's own.

An up-to-date run reports `up to date: <harness-dir> — nothing written`, exits 0 and touches
nothing: no file
written, no mode or modification time changed, no package destination replaced and no `tools/.venv`
removed. "Nothing" is judged on the result: every file the install would
write is already byte-identical and mode-identical, and none would be created or removed. Changing
`--harness`, `--family` or the tier map changes bytes, so that install proceeds. A different plugin
is a different install directory, not a change of bytes in one. A `.venv` directory is not install
output and is outside the comparison, so its presence alone never makes an install proceed.

`--dry-run` runs the same judgment and writes nothing, in the target or elsewhere that outlives the
run. It prints what the install would change, grouped as created, changed and removed, each path
relative to the project root, or absolute for a file outside it, such as the global agents file, and
exits 0; where nothing would change it says the harness directory is up to date. A directory the
install would remove is listed with a trailing `/`. Every path it prints and every refusal it reports
names the path. What the install would leave alone or skip, with the reason, is reported on stderr
on an up-to-date run and a dry run as on a changing one. It reports the refusals it can foresee.

