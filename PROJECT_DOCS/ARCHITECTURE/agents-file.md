## Agents File

The harness agents file is a definition of the agents-file kind
(`adjagent/definitions/harness_agents_file.py`). Its body is the whole file as a fresh install holds
it: the title carrying the scope-name hole, then the span from the begin marker line to the end
marker line. `render.render_agents_file(harness, scope=...)` fills it under the default family's own
tiers whatever the invocation's tuning, with no model-shape check, so its text is a function of the
harness and the scope alone. The scope is `Global` in the harness's user directory and otherwise the
directory's name.

`adjagent/agents_file.py` implements the install SPEC.md specifies. It finds the span by the
stripped ends of the marker lines, replaces it with the rendered span, and writes every other byte
back as read. Every check, including the git-status refusal over `adjagent/`, runs before the first
write.

`install` uses it twice: for a plugin installed below its project root, and for a user-level install
given `--install-global-agents-file`. It runs the checks (`checked_agents_file`) among its own
pre-write checks and writes the file (`write_agents_file`) after its renders, so a refusal
leaves the install unwritten.

