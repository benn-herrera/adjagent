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

The hook is `.claude/hooks/guardrail.pl`. It needs `perl` on `PATH` with core `JSON::PP` when a
session runs it. The install runs it once to check; without perl or the module, or if the run takes
more than a few seconds, it skips the hook, reports the reason in one line and installs everything
else. A script and entry from an earlier install are left in place and named.

The install adds one `PreToolUse` entry for Bash and the file tools (Read, Write, Edit,
NotebookEdit, Grep, Glob) to `.claude/settings.json`, the file Claude Code reads whatever `--subdir`
is; an entry an earlier install wrote for Bash alone is replaced by it. The entry runs the script
under `$CLAUDE_PROJECT_DIR` only if it is a readable file. Where it is missing, for example because
you committed `settings.json` but not `.claude/hooks/`, a call prints
`guardrail hook: no readable script at <path>` and goes ahead, rather than being blocked.

The settings file is edited in place:

- An existing file keeps every other byte, including your own hooks, and a re-install replaces that
  one entry in place. Only an entry written by an install is replaced, so a hook of yours that runs
  some other `guardrail.pl` is left alone.
- A project has one entry: installing under a different `--subdir` replaces it.
- A settings file with comments, or with more than one of our entries, or a settings path that is a
  symlink or sits behind one, or is not a regular file, is reported with the entry printed for you to
  merge by hand and is left untouched.
- A settings file that is not UTF-8, or whose `hooks` or `PreToolUse` has the wrong shape (`null`
  included), refuses the install with nothing written, as does a harness directory whose path holds a
  `"`, `$`, backtick or `\`.

## Opencode

The guardrail is a plugin, `.opencode/plugins/guardrail.ts`, copied as it stands. It registers
itself; the install writes no settings entry for it.
