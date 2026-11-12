## Agents File

The agents file is rendered from the agents-file definition
(`devpro/definitions/harness_agents_file.py`), a definition of the agents-file kind. Its body is
the whole file as a fresh install holds it: the title carrying the scope-name placeholder, then the
agents-file block from the begin marker line to the end marker line.
`render.render_agents_file(harness, plugin, scope=...)` fills it for the harness bound to the plugin,
under the default family's own tiers, with no model-shape check. The `development` bullet is an optional
reference to `development` in its own paragraph, and both plugins ship it, so both blocks carry it.
The scratch rule and the memory file's name are the harness's `scratch_rule` and `memory_file`
(Rendering, Placeholders); mage's scratch rule names `.mage-temp/`. `agents_file` passes
`GLOBAL_SCOPE` for a user harness directory and otherwise the directory's name.

`devpro/agents_file.py` implements the install SPEC.md specifies. It finds the agents-file block
by the stripped ends of the marker lines (`agents_file.BEGIN`, `agents_file.END`, devpro's alone), replaces it with the rendered agents-file block, and
writes every other byte back as read; a file with no marker line gets the rendered agents-file
block appended instead. Every check runs before the first write. `checked_agents_file` makes the
checks of the destination and carries no commit-state check. The git-status refusal over
`devpro/` is `agents_file.refuse_uncommitted`, applied by the callers only where the destination
is the agents file in a user harness directory, so a project directory is never refused.

`install` uses it in two places. For a harness-directory plugin (mage) installed below its project root,
it writes into the harness directory (`_installs_agents_file`). On every project install of a
nested plugin (`_is_project_install_of_a_nested_plugin`: claude and
opencode) it keeps the agents-file block current in one place (`checked_followed_agents_file`,
`write_followed_agents_file`). Each runs its checks (`checked_agents_file`,
`checked_followed_agents_file`) among the install's own pre-write checks and writes after its
rendered definitions, so a refusal leaves the install unwritten. It calls `refuse_uncommitted` only
where the placement lands in the global agents file, so the plugin below a project and the
project's `AGENTS.md` are not refused. Where the file's text is identical to what the destination
holds, `write_agents_file` writes nothing, so no backup is made.

**Placement.** The block is kept in one of the global agents file and the project file, never both,
because both load into one session and no shared clause appears twice in one prompt (SPEC.md,
Rendering). `checked_followed_agents_file` takes the global agents file in `global_dir`,
`harness.user_dir` (`Path(user_harness_dir).expanduser()`, so `HOME` decides), unless the caller
passes a scratch copy. Where that file, or the file a redirect there names, holds any marker line
(`agents_file.is_marker_line`),
the agents-file block is kept current there and `_checked_project_copy_removal` plans the removal
of the agents-file block from the project's `AGENTS.md` (a redirect there followed). Otherwise `checked_agents_file` keeps the
agents-file block in the project's `AGENTS.md`, with the redirect file for a harness that reads
another name. A project install's preflight reads the global agents file through the same
decision (`_install_managed_paths`), so its directory is a managed base and `--dry-run` names those
paths whole.

**The plugin on the marker.** The begin marker line reads `vvv-devpro <plugin> <version> …`: the
plugin is `@!plg-name!@` (`clauses.PLUGIN_NAME`), the version `@!agf-version!@`. A file holds one
block, because two blocks with different markers would deliver the shared rules twice to every
session that reads the file (SPEC.md, Rendering). `agents_file._block_plugin` reads the first word
after the marker's opening as a plugin name, and `_release` the word after it. A begin line whose
first word is no plugin's name is a block of no plugin, with no release. On a project install
`checked_followed_agents_file` keeps a global block current as the plugin `_held_plugin` reads from its
begin line (`install-agents-file --plugin=<plugin>` into the user harness directory is what changes it), and a
block of no plugin as the installing plugin's. The block of no plugin differs in content from the
plugin's, so it is rewritten under the existing rule for a stamp that is not a release version. Mage
writes the plugin's block into `<plugin>/CLAUDE.md` in its own directory, so no conflict arises.

**Version stamp.** The begin marker line carries `@!agf-version!@`, filled by `render.filled_text` from
`devpro.__version__` for the agents file alone. `checked_agents_file` compares the existing block with
the rendered one, marker lines excluded, and decides by `_release` (dot-separated digits, `None` for
anything else). A kept block's report travels in `AgentsFileWrite.left`. The marker lines are
recognised by their fixed ends, so a stamped, an unstamped and a non-version-stamped line all parse.

The `install-agents-file` verb is reached through `agents_file.preflighted_agents_file_install`, the
agents-file counterpart of the install preflight (Install, Renders and copies).
After the directory check and the git-status refusal, which applies only when
`install_target.user_dir_harnesses(directory)` names a harness (it matches absolute user harness
directories, so mage's relative `.` never matches), a first `checked_agents_file` call, which
writes nothing, yields the `path`, `destination`, `backup` and `native` of the run. Those paths,
relative to the directory, are the managed set of `preflight.run_preflighted`, whose scratch copy
takes the directory's basename. The real `install_agents_file` runs on the scratch copy with
`real_directory` set to the real directory, which `checked_agents_file` reads for the
user-harness-directory test and for the scope name the file is titled with, since a scratch copy
would answer both differently. Its outcomes are `run_preflighted`'s.

