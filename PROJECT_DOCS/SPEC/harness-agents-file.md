## Harness Agents File

The repository publishes a recommended operator agents file as one definition, rendered per
supported harness. It is installed only by explicit act, into a directory the operator names — the
harness's user-global directory or a project's own. `install` installs it in two cases, through
the same mechanism: for a plugin harness (mage) installed below its project root,
whose agents file belongs in the plugin directory at ROOT, and for a user-level ROOT given
`--install-global-agents-file`; for any other harness it never does.

Agent directives live in `AGENTS.md`. Installed into the harness's user-global directory, the file
takes the name that harness reads there — `CLAUDE.md` for Claude Code and mage, `AGENTS.md` for
opencode — and nothing else is written. For mage every destination is its own directory, so it
writes `CLAUDE.md` there and never reaches the `AGENTS.md` redirect rule below. Installed anywhere
else, it is `AGENTS.md`; a harness that reads another name gets that file as the one-line redirect
`@AGENTS.md`, created when absent and left alone when already present. A file of that other name
holding anything else is refused with nothing written: moving its content into `AGENTS.md` is the
operator's act, never the install's.

The installed file carries the repository's content as **one delimited block**, from its begin
marker line through its end marker line, recognised by their fixed ends so a block any earlier
revision wrote is still found; installation replaces that span and keeps every other byte of the
file as the operator's, writes an absent file whole, appends the block at the end of a file with no
marker line, every existing byte kept, and refuses with nothing written a file with any other
marker lines than one ordered pair. A destination whose only content is one `@<path>` import is a
redirect followed one hop, within the named directory, and never rewritten itself; a longer chain,
or a target outside that directory, is refused with nothing written.

Edits made inside the block are not preserved. A write that changes the file keeps one rolling
backup of the prior content beside it; identical output writes nothing, so installing twice changes
nothing. `install-agents-file` says so: where the run would change nothing it reports the agents file
up to date and touches no file, a backup and a redirect included. With `--dry-run` it prints whether
the agents file, and any redirect file it would create, would be created or changed, writes nothing
and exits 0; its paths are relative to the directory named. Run from a clone, two writes are refused
while the generator's sources carry uncommitted changes, because they alter live operator
configuration: `install-agents-file` into a harness's user-global directory, and the agents-file write
of a user-level `install`. No project install is refused, nor is `install-agents-file` into a project
directory, a mage plugin below a project included. An installed package has no uncommitted state and
is not refused (Package and Command).
Publishing an improvement is a manual edit to the agents-file definition.

Neither direction is a symlink, so a write to this repository can never silently rewrite live
operator configuration. The install writes a regular file, and refuses a symlink in place of the
file or its backup.
