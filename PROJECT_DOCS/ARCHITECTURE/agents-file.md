## Agents File

The harness agents file is a definition of the agents-file kind
(`adjagent/definitions/harness_agents_file.py`). Its body is the whole file as a fresh install holds
it: the title carrying the scope-name hole, then the span from the begin marker line to the end
marker line. `render.render_agents_file(harness, scope=...)` fills it under the default family's own
tiers whatever the invocation's tuning, with no model-shape check. Its text is a function of the harness and the scope alone. The scope is `Global` in the harness's user directory and otherwise the
directory's name.

`adjagent/agents_file.py` implements the install SPEC.md specifies. It finds the span by the
stripped ends of the marker lines, replaces it with the rendered span, and writes every other byte
back as read; a file with no marker line gets the rendered span appended instead. Every check runs before the first
write. `checked_agents_file` makes the checks of the destination and carries no commit-state check.
The git-status refusal over `adjagent/` is `agents_file.refuse_uncommitted`, applied by the callers
only where the destination is live operator configuration, so a project directory is never refused.

`install` uses it in three places. For a standalone plugin (mage) installed below its project root,
and for a user-level install given `--install-global-agents-file`, it writes into the harness
directory, never into claude's plugin inside it (`_installs_agents_file`). On every project install of
a harness that is not a standalone plugin (`_keeps_the_block_current`: claude and opencode) it keeps
the block current in one place (`checked_followed_agents_file`, `write_followed_agents_file`).
Each runs its checks (`checked_agents_file`, `checked_followed_agents_file`) among the install's own
pre-write checks and writes after its renders, so a refusal leaves the install unwritten. It calls
`refuse_uncommitted` when the install is user-level and when the placement lands in the user-global
agents file, so the plugin below a project and the project's `AGENTS.md` are not refused. Where the
file's text is identical to what the destination holds, `write_agents_file` writes nothing, so no
backup is made.

**Placement.** `checked_followed_agents_file` takes the user-global agents file in `global_dir`,
`user_dir(harness)` (`Path(harness.user_harness_dir).expanduser()`, so `HOME` decides), unless the
caller passes a scratch copy. Where that file, or the file a redirect there names, holds any marker
line, the block is kept current there and `_checked_project_copy_removal` plans the removal of the
span from the project's `AGENTS.md` (a redirect there followed): every other byte kept, rolling
backup, the file kept even when left empty, and a report of what was removed and why. That branch never
reads the project's native file (`CLAUDE.md`). Otherwise `checked_agents_file` keeps the block in the
project's `AGENTS.md`, with the native redirect for a harness that reads another name. A project
install's preflight reads the global file through the same decision (`_install_managed_paths`), so the
global file's directory is a managed base and `--dry-run` names those paths whole.

**Version stamp.** The begin marker line carries `@!agf-version!@`, filled by `render.filled_text` from
`adjagent.__version__` for the agents file alone. `checked_agents_file` compares the existing block with
the rendered one, marker lines excluded, and decides by `_release` (dot-separated digits, `None` for
anything else): identical content keeps the existing text; differing content is rewritten unless the
existing stamp parses and is later than the installing one, in which case the text is kept and
`AgentsFileWrite.left` carries the "not downgraded" report. The marker lines are recognised by their
fixed ends, so a stamped, an unstamped and a non-version-stamped line all parse.

**Symlinks.** On the agents-file paths (the global file, the project `AGENTS.md`, the `CLAUDE.md`
redirect and the backup) a symlink is the file it names: `_refuse_unless_file_or_absent` refuses only
what exists and is not a file, so a dangling link counts as absent and writing it creates its target.
The write opens the path, so the link stays. The redirect-target containment test in `_followed`
compares paths without resolving them, so a link below the directory stands for its target.

The `install-agents-file` verb is reached through `agents_file.preflighted_agents_file_install`, the
agents-file counterpart of the install preflight (Install Consumption Model, Renders and copies).
After the directory check and the git-status refusal, which applies only when
`install_target.user_dir_harnesses(directory)` names a harness (it matches absolute user directories,
so mage's relative `.` never matches), a first `checked_agents_file` call, which writes nothing, yields the `path`, `destination`, `backup` and `native` of the run. Those paths,
relative to the directory, are the managed set of `preflight.run_preflighted`, whose scratch copy
takes the directory's basename. The real `install_agents_file` runs on the copy with
`real_directory` set to the real directory, which `checked_agents_file` reads for the
user-directory test and for the scope name the file is titled with, since a copy would answer both
differently. Its outcomes are the install's: a run that would change nothing reports the directory
up to date and writes nothing; `--dry-run` prints what would be created or changed, relative to the
directory, and writes nothing; otherwise the install runs.

