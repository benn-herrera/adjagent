# Guardrail

Claude and opencode each ship a hook that blocks shell commands which change a file behind the Edit
and Write tools: in-place `sed`, `perl` or `ruby` edits, redirects (`>`, `>>`), `tee`, `cp` and `mv`
onto an existing file, and inline `python`, `node`, `perl` or `ruby` scripts that write. Writes into
`test-data/transient` are allowed, and into `.claude-temp/` under claude or `.opencode-temp/` under
opencode. A relative path is judged against the directory the command runs in, and a heredoc's body
is not read as shell. The hook catches the forms agents habitually use; it is not a boundary against a
command written to evade it. Mage ships none, and a user-level install installs none.

## The `.index/` check

On a kb install, the hook also keeps sessions out of `kb-root/.index/`, where kbase keeps its
records: read them with kbase's `query` tool and change them with its `write` tool. It refuses a
file-tool call on a path there, a shell command naming one, and a recursive search rooted in
`kb-root/` that could reach one; the refusal says how to exclude `.index` from the search. A path is
judged where its symlinks lead. `test -e`, `test -d`, `test -f`, `[ -e … ]` and `stat` on those paths
are allowed. The check is on only while the harness directory holds the kbase skill's `SKILL.md`, and
the hook looks for it on every call, so a base install never sees it.

## Claude

The hook is `guardrail.pl` inside the adjagent plugin, registered in the plugin's own
`hooks/hooks.json` for Bash and the file tools (Read, Write, Edit, NotebookEdit, Grep, Glob). It
needs `perl` on `PATH` with core `JSON::PP` when a session runs it. The install runs it once to
check; without perl or the module, or if the run takes more than a few seconds, it skips the hook and
its registration, reports the reason in one line and installs everything else. A script and
registration from an earlier install are left in place and named.

The registration runs the script only if it is a readable file. Where it is missing, a call prints
`guardrail hook: no readable script at <path>` and goes ahead, rather than being blocked.

Earlier versions registered the hook in your project's `.claude/settings.json` and kept the script at
`.claude/hooks/guardrail.pl`. A project install that installs the new hook cleans those up:

- It removes our entry from `.claude/settings.json`, and on a kb install our `kbase` entry from the
  project's `.mcp.json`. Every other byte stays, including your own hooks; a list or object left
  empty reads `[]` or `{}`. A user-level install removes none, because it never wrote them.
- It removes `.claude/hooks/guardrail.pl` when it carries the `!INSTALLED! ... adjagent` header.
- It removes only an entry whose command is exactly the one an install wrote, so a hook of yours that
  runs some other `guardrail.pl` is left alone.
- An entry sharing an element with a command of yours, or more than one of our entries, is printed
  and left for you to remove by hand.
- A settings file that is not strict JSON (comments, for one), is not UTF-8, has a `hooks`,
  `PreToolUse` or `mcpServers` of the wrong shape (`null` included), sits behind a non-directory,
  or is not a regular file is left untouched, and the cleanup never refuses the install. If it
  still holds our old hook command or `kbase` entry, the install says so, and you remove the entry
  by hand.

## Opencode

The guardrail is a plugin, `.opencode/plugins/guardrail.ts`, copied as it stands. It registers
itself; the install writes no settings entry for it.
