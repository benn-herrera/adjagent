## Harness Agents File

The repository publishes a recommended operator agents file as one definition, rendered per
supported harness. Its first arrival in live configuration is an explicit act, into a directory the
operator names — the harness's user-global directory or a project's own. `install` also writes it,
through the same mechanism, in three cases:

- for a plugin harness (mage) installed below its project root, whose agents file belongs in the
  plugin directory, which is its harness directory;
- for a user-level harness directory given `--install-global-agents-file`, where the file goes into
  the harness directory and never inside claude's plugin below it;
- on every claude or opencode project install, which keeps the block in exactly one place:
  - if the user-global agents file holds the adjagent block, the install keeps it current there and
    removes any project copy, reporting what it removed and why. Only the span goes: every other byte
    of the project's `AGENTS.md` stays, one rolling backup is made, and the file stays even if
    emptied.
  - if the global file holds no block, the install keeps the block current in the project's
    `AGENTS.md`, creating it if absent.

  The block never goes into a pointer file. Once the global file holds the block, project installs
  keep it there; `--install-global-agents-file` and `install-agents-file` into the user-global
  directory are how it first gets there.

For any other install it never writes the agents file.

Agent directives live in `AGENTS.md`. Installed into the harness's user-global directory, the file
takes the name that harness reads there — `CLAUDE.md` for Claude Code and mage, `AGENTS.md` for
opencode — and nothing else is written. For mage every destination is its own directory, so it
writes `CLAUDE.md` there and never reaches the `AGENTS.md` redirect rule below. Installed anywhere
else, it is `AGENTS.md`; a harness that reads another name gets that file as the one-line redirect
`@AGENTS.md`, created when absent and left alone when already present. A file of that other name
holding anything else is refused with nothing written: moving its content into `AGENTS.md` is the
operator's act, never the install's. On a project install this governs only the branch that keeps
the block in the project's `AGENTS.md`; the branch that keeps it in the global file never reads or
writes the project's file of that other name.

The installed file carries the repository's content as **one delimited block**, from its begin
marker line through its end marker line, recognised by their fixed ends so a block any earlier
revision wrote is still found; installation replaces that span and keeps every other byte of the
file as the operator's, writes an absent file whole, appends the block at the end of a file with no
marker line, every existing byte kept, and refuses with nothing written a file with any other
marker lines than one ordered pair. A destination whose only content is one `@<path>` import is a
redirect followed one hop, within the named directory, and never rewritten itself; a longer chain,
or a target outside that directory, is refused with nothing written.

The begin marker line carries the version of adjagent that last changed the block's content. An
update compares the block with the marker lines excluded. Identical content writes nothing, whatever
the stamp, and the stamp stays. Differing content is rewritten and stamped with the installing
version, unless the existing stamp is a later release than the installing one: then the block is left
and the install reports "not downgraded" with both versions. A block with no stamp, or one that is not
a release version, is rewritten when its content differs. A change that would alter only the marker lines is never made.

Edits made inside the block are not preserved. A write that changes the file keeps one rolling
backup of the prior content beside it; identical output writes nothing, so installing twice changes
nothing. `install-agents-file` says so: where the run would change nothing it reports the agents file
up to date and touches no file, a backup and a redirect included. With `--dry-run` it prints whether
the agents file, and any redirect file it would create, would be created or changed, writes nothing
and exits 0; its paths are relative to the directory named. Run from a clone, three writes are refused
while the generator's sources carry uncommitted changes, because they alter live operator
configuration: `install-agents-file` into a harness's user-global directory, the agents-file write
of a user-level `install`, and a project install's write of the block into the user-global agents
file. No other project write is refused: the project's `AGENTS.md` and its redirect are not, nor is
`install-agents-file` into a project directory, a mage plugin below a project included. An installed package has no uncommitted state and
is not refused (Package and Command).
Publishing an improvement is a manual edit to the agents-file definition.

The repository's published copy is never symlinked into live configuration, so a write to this
repository can never silently rewrite live operator configuration.
