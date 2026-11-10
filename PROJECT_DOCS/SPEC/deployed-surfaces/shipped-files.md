### Shipped files

A **shipped package** is plain code, never rendered and so never carrying a generated banner,
installed at its **package destination**, a fixed directory under the install directory. Its
installed copy is stamped where Installed tree says: the installed banner, not the generated
banner. A package ships with the definition it belongs to, and only where that definition ships
(Plugins). The devpro plugin delivers the **docdicer tools package** at its package destination under
the install directory, `skills/docdicer/tools/`: inside the `docdicer` skill's own directory. It
also delivers the **development scripts package**, `skills/development/scripts/`, inside the
`development` skill's own directory (below), under mage as under claude and opencode. The kbase
plugin delivers the kb-tools package (below). A user-level install delivers none (SPEC.md, Deployed
Surfaces, Install destination). The docdicer package holds four files:
- `docdicer`, a `bash` script, executable, carrying the installed banner below its shebang
- `.gitignore`, holding `.venv/` and carrying no banner
- `runner-snippets/docdicer.just` and `runner-snippets/docdicer.mk`, runner snippets for a
  consuming project to include, each carrying the installed banner at its top. No install writes a
  runner include line for them; a project opts in by adding one itself.

The script's behavior, run as `tools/docdicer` from the skill's directory:
- `--install` installs into `tools/.venv` the docdicer version the script names. It keeps a
  `tools/.venv` whose python runs and brings its pip current; it builds the venv, with current pip,
  where there is none or its python no longer runs. Where `python3` 3.9 or later is not on the host,
  it names the remedy and exits non-zero
- with no `tools/.venv` and any other arguments, it says how to install and exits non-zero
- otherwise its arguments pass to docdicer unchanged

An install that changes anything replaces the package whole, `tools/.venv` included. Where
`tools/.venv` existed before that install, the install afterwards runs `tools/docdicer --install`,
the **tool install**, so the installed docdicer stays matched to the script. A failure of that run
is reported in one line naming the command; the install's exit status and the rest of its writes
are unaffected. An up-to-date run (Write Safety) runs nothing. A `.venv` directly under a package
destination is not install output.

The development scripts package holds one file, `cold-read.sh`, a `bash` script, executable,
carrying the installed banner below its shebang. A **cold read** is one agent reading one brief
with no tools and none of the project's instruction files in context. The script is run as
`scripts/cold-read.sh <agent> <brief-file> [<output-file>]` from the skill's directory:
- The reply is written to the output file, by default beside the brief, named
  `<brief name without .md>-<agent, ":" as "-">.md`, and the script prints that path. Exit status 2
  is a usage error; 1 is a refusal or a failed harness run, which leaves no output file.
- The reader runs with no tools and loads none of the project's instruction files, while the
  operator's global agents file, under claude `~/.claude/CLAUDE.md`, still loads. It works in a
  fresh directory that is empty under claude and, under opencode, holds only the named agent's
  file with every tool denied, composed from that agent's record in the plugin's registry and its
  body file; the session is not added to the operator's history.
- That directory is a mode 0700 child of the directory the environment variable
  `ADJAGENT_COLD_READ_DIR` names, and is removed when the script exits, on failure and on
  interruption included. The script refuses, naming the cause and creating nothing, where the
  variable is not set, does not name an existing directory, names a directory inside the project
  root, or names one with an instruction file (`CLAUDE.md`, `AGENTS.md` or another the harnesses
  load) at or above it, other than in the operator's own `~/.claude/`; it names that file.
- An agent the installed set does not hold fails the run with no output; under claude the script
  says the agent did not load and passes on the available agents claude named.
- Where the environment variable `ADJAGENT_COLD_READ_MODEL` is set and not empty, the reader runs on
  that model (under claude a model name or alias, under opencode `provider/model`); otherwise on the
  model the harness gives the agent. A model the harness rejects fails the run with no output.
- Under opencode a brief whose first character is `-` is refused.
- It refuses where the calling session is the other harness's, naming both and saying to run the
  calling harness's own copy of the skill, and where it sits under no harness directory named
  `.claude` or `.opencode`, so under mage and in this repository's source tree. It runs under claude
  and opencode only.

The kb-tools package is a shipped package installed at its own stated destination:
`skills/kbase/kb-tools/`, inside the `kbase` skill's own directory, holding only the runner
snippets, and not an importable package either, read by the consuming project through the runner
include line. The snippets run `kbase` from `PATH`. Every target the snippets define is named
`kb-<name>`. No package is a definition: a package under a
skill's directory is neither its skill entry file nor one of its supporting files, the development
scripts package and the docdicer tools package included.

A **harness resource** is a file a harness ships, such as a guardrail script or opencode's plugin entry,
copied as it stands and never rendered. A harness also writes harness-rendered files into the
install directory — the plugin manifest `.claude-plugin/plugin.json`, one value shared by claude and
mage, version included, `.mcp.json` under claude and mage where `kbase` ships, rendered whole
with the `kbase` server alone, `registry.json` under opencode, and under claude the guardrail
registration `hooks/hooks.json` (below) — which are rendered, not copied, carry no banner, and are
replaced whole. `registry.json` is opencode's **registry**: the plugin's name and version and one record
per agent, command and skill — id, body file, description, and for an agent its mode, model, color
and permissions — and the `kbase` MCP server where `kbase` ships. An install copies the harness
resources into the install directory, except a user-level install, which copies only opencode's
entry, and save a file conditional on the install-time probe (below), so a resource lands at the
path it holds below the install directory: opencode's at `<install-dir>/index.ts`, the plugin entry, and
`<install-dir>/guardrail.ts`, and claude's at `<install-dir>/hooks/guardrail.pl` (mage ships none):
in the install directory, outside its three deployed surfaces. Each keeps its bytes and its mode:
the install stamps nothing on them. Every such file carries an installed banner
(`!INSTALLED! … adjagent`) in its first ten lines — the guardrails' name this repository and forbid
edits. A harness shipping none copies nothing, which is not an error.

Opencode loads the plugin directory and registers its agents, skills, commands and, where
`kbase` ships, the `kbase` MCP server under the registry's ids. A change to the install directory
is picked up without restarting opencode. The plugin entry is written for opencode v2.2.6 and is the
same file for both plugins; ARCHITECTURE.md, Install, Opencode entry holds how it works. A resource may be conditional on the probe: claude's guardrail is
delivered only when one run of the script on the installing machine succeeds within a few seconds,
and is otherwise skipped, with the reason reported and the rest of the install unaffected. The
guardrail catches common mistakes; it is not a security boundary, and does not contain an agent
that sets out to evade it. Both guardrails are to block the same calls but one spelling, which only
the claude guardrail reads: a path word of a shell command that, its surrounding quote stripped,
opens with `$CLAUDE_PROJECT_DIR` or `${CLAUDE_PROJECT_DIR}` followed by `/` or the word's end is
read as the rest of the word under the project root; where that variable is unset or empty, the word
is read literally. File-tool arguments are read literally, and no other variable is read.

Their mutation check blocks shell commands that change a file behind the edit tools, such as
in-place `sed`, `perl` or `ruby` edits, shell redirections, `tee`, `cp` or `mv` onto an existing
file, and inline scripts that write, and allows writes into the scratch directories: `.claude-temp`
under claude and `.opencode-temp` under opencode, each under the project root. A relative
destination is judged lexically against the working directory of the call. A heredoc's body is data:
no check reads it, unless the heredoc feeds a script: a shell's (`bash`, `sh`, `zsh`) body is read
by every check, an interpreter's (`python3 -`, `perl`, `ruby`, `node`) only by the inline-script
write check. Its own command line is read like any other. This check blocks with `Blocked: <reason>` and a pointer to the edit tools.

Their `.index/` check is active only where the install directory holds the kbase skill's skill entry
file, which they look for on every call, so a devpro install is never blocked by it. It blocks a call
that reaches into `<project>/kb-root/.index/`, whose index records kbase's own tools read and
change:
- a shell command with a word naming a path there, existence checks (`stat`, and `test` or `[` with `-e`, `-d` or `-f`) excepted
- a recursive `grep`, `rg`, `find`, `ls -R` or `tree` rooted in `kb-root/` that does not exclude
  `.index`
- a file-tool call whose path lies there: Claude's Read, Write, Edit and NotebookEdit, opencode's
  read, write, edit and patch
- a Grep or Glob rooted in `kb-root/` whose file filter could match an index record

A path reaches `kb-root/.index/` when it does so through `..` segments, relative to the call's
working directory (for opencode's file-tool calls, the project root). A Glob reaches it when its
`path` together with its pattern's leading literal segments does. This check blocks with `Blocked:
<reason>` alone, without the mutation check's pointer to the edit tools. Where both checks would
block a shell command, the block reported is this check's.

Claude's guardrail runs at session time and needs perl with core `JSON::PP`; an install also
registers it as a `PreToolUse` entry for Bash and the file tools (Read, Write, Edit, NotebookEdit,
Grep, Glob) in the plugin's own `hooks/hooks.json`, written beside the script and only where the
install-time probe succeeds; no project settings file is written to register it. The entry runs the
script only where it stands readable: where it is missing, a call reports `guardrail hook: no readable script at <path>`
on stderr and proceeds, and is not blocked. A claude guardrail that fails while running, through a
missing module or an error in the script, reports on stderr and does not block the call.
Opencode's guardrail is run by the plugin entry, which imports `guardrail.ts` from the install
directory: the install writes no settings entry for it. A user-level install copies no
`guardrail.ts`, and the plugin entry then runs none.

