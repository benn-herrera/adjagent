## Agents File

The repository publishes a recommended agents file as one agents-file definition, rendered per
supported harness. Its content depends on the harness, the plugin and where it is installed, never on
`--family` or a tier map. Its title names `Global` in a user harness directory, and otherwise the
name of the directory it is installed in.

The installed content is one **agents-file block**, from a begin marker line
`<!-- vvv-adjagent <plugin> <version> … adjagent-vvv -->` to an end marker line
`<!-- ^^^-adjagent … adjagent-^^^ -->`. A file holds one block, and the plugin on the begin marker
says whose it is. `install-agents-file` into a user harness directory leaves a project's copy in
place; the next project install removes it. A
**redirect file** is a one-line `@AGENTS.md` under another name a harness reads.

`adjagent install-agents-file PLUGIN DIR` installs that plugin's agents file into the directory the
operator names — the harness's user harness directory or a project's own — and is the only way the
agents-file block first reaches a user harness directory, or changes the plugin a global block
belongs to. `install` also writes it, under the same rules as `install-agents-file`, in two cases:

- for mage installed below its project root, whose agents file belongs in its harness directory,
  inside that plugin's own directory;
- on every claude or opencode project install, which keeps the agents-file block in exactly one
  place:
  - if the global agents file holds any adjagent marker line, the install keeps it current
    there, as the plugin its begin marker names, and removes any project copy, reporting what it
    removed and why. A block whose begin marker names no plugin is kept as the installing plugin's.
    A global block of the other plugin stays that plugin's: no install reports it, refuses on it or
    reconciles it. Only the block goes from the project: every other byte of the project's
    `AGENTS.md` stays, one rolling backup is made, and the file stays even if emptied. A global
    agents file whose marker lines are not one ordered pair refuses the project install with
    nothing written.
  - if the global agents file holds no marker line, the install keeps the installing plugin's block
    current in the project's `AGENTS.md`, creating it if absent.

  The block never goes into a redirect file. Once the global agents file holds the block, project installs
  keep it there.

For any other install it never writes the agents file.

Both plugins' blocks name the `development` skill. Under mage the block's scratch rule names
`.mage-temp/`. `install-agents-file` installs no skill, so a harness directory that holds only the agents file
lacks the skill it names.

Agent directives live in `AGENTS.md`. Installed into the harness's user harness directory, the file
takes the name that harness reads there — `CLAUDE.md` for Claude Code, `AGENTS.md` for opencode —
and nothing else is written. Mage has no user harness directory: its agents file is `CLAUDE.md`
wherever it is installed, and it never reaches the `AGENTS.md` redirect rule below. Installed
anywhere else, it is `AGENTS.md`; a harness that reads another name gets that file as the one-line
redirect file `@AGENTS.md`, created when absent and left alone when already present. A file of that other
name holding anything else is refused with nothing written: moving its content into `AGENTS.md` is
the operator's act, never the install's. On a project install this governs only the branch that
keeps the block in the project's `AGENTS.md`; the branch that keeps it in the global agents file never
reads or writes the project's file of that other name.

The installed file carries the repository's content as the agents-file block, recognised by the
fixed ends of its marker lines so a block any earlier revision wrote is still found; installation
replaces that block and keeps every other byte of the file as the operator's, writes an absent file
whole, appends the block at the end of a file with no marker line, every existing byte kept, and
refuses with nothing written a file with any other marker lines than one ordered pair. A
destination whose only content is one `@<path>` import is a redirect followed one hop, within the
named directory, and never rewritten itself; a longer chain, or a redirect target outside that
directory, is refused with nothing written.

The begin marker line carries the version of adjagent that last changed the block's content. Content
identical but for the marker lines writes nothing, whatever the version stamp, and the stamp stays.
Differing content is rewritten and stamped with the installing version, unless the existing stamp is
a later release than the installing one: then the block is left and the install reports "not
downgraded" with both versions. A block with no stamp, or one that is not a release version, is
rewritten when its content differs. A change that would alter only the marker lines is never made.

Edits made inside the block are not preserved. A write that changes the file keeps one rolling
backup of the prior content beside it; identical output writes nothing, so installing twice changes
nothing. `install-agents-file` says so: where the run would change nothing it reports the agents
file up to date and touches no file, a backup and a redirect file included. With `--dry-run` it
prints whether the agents file, and any redirect file it would create, would be created or changed,
writes nothing and exits 0; its paths are relative to the directory named. Run from a checkout,
two writes are refused while the generator's sources carry uncommitted changes:
`install-agents-file` into a harness's user harness directory, and a project install's write of the
block into the global agents file. Where the commit state cannot be read, those writes are
refused too. No other project write is refused: the project's
`AGENTS.md` and its redirect are not, nor is `install-agents-file` into a project directory, a mage
plugin below a project included. An installed package has no uncommitted state and is not refused
(Package and Command).
