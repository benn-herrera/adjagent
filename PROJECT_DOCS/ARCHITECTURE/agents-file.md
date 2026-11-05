## Agents File

The harness agents file is a definition of the agents-file kind
(`adjagent/definitions/harness_agents_file.py`). Its body is the whole file as a fresh install holds
it: the title carrying the scope-name hole, then the span from the begin marker line to the end
marker line. `render.render_agents_file(harness, scope=...)` fills it under the default family's own
tiers whatever the invocation's tuning, with no model-shape check. Its text is a function of the harness and the scope alone. The scope is `Global` in the harness's user directory and otherwise the
directory's name.

`adjagent/agents_file.py` implements the install SPEC.md specifies. It finds the span by the
stripped ends of the marker lines, replaces it with the rendered span, and writes every other byte
back as read. Every check, including the git-status refusal over `adjagent/`, runs before the first
write.

`install` uses it twice: for a plugin installed below its project root, and for a user-level install
given `--install-global-agents-file`. It runs the checks (`checked_agents_file`) among its own
pre-write checks and writes the file (`write_agents_file`) after its renders, so a refusal
leaves the install unwritten. Where the file's text is identical to what the destination holds,
`write_agents_file` writes nothing, so no backup is made.

The `install-agents-file` verb is reached through `agents_file.preflighted_agents_file_install`, the
agents-file counterpart of the install preflight (Install Consumption Model, Renders and copies).
After the directory check, a first `checked_agents_file` call, which writes nothing and carries the
git-status refusal, yields the `path`, `destination`, `backup` and `native` of the run. Those paths,
relative to the directory, are the managed set of `preflight.run_preflighted`, whose scratch copy
takes the directory's basename. The real `install_agents_file` runs on the copy with
`real_directory` set to the real directory, which `checked_agents_file` reads for the
user-directory test and for the scope name the file is titled with, since a copy would answer both
differently. Its outcomes are the install's: a run that would change nothing reports the directory
up to date and writes nothing; `--dry-run` prints what would be created or changed, relative to the
directory, and writes nothing; otherwise the install runs.

