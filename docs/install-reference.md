# Install reference

The rules behind `adjagent install`: where it writes, what it writes, what it leaves alone and when
it refuses. The route that puts adjagent into a project is in the [README](../README.md#quick-start-guide).

`adjagent` and `PYTHONPATH=<clone> python3 -m adjagent` (from a checkout) are the same command. In a
checkout, the `just` recipes are maintainer conveniences that map to `adjagent` verbs: `just install`
is `adjagent install`, and `just install-agents-file` is `adjagent install-agents-file`. `just
render` is not `adjagent render`: it takes a slug and forwards its `--*` flags to `adjagent
install`, once for each plugin. Every `--*` flag after the target forwards verbatim, so tuning the
render is one more flag ([Model tuning](model-tuning.md)). Run from an installed package, the check
that protects a checkout does not apply: there is no uncommitted state to refuse the agents file for.

## Choosing the plugin and the target

`adjagent install PLUGIN TARGET` takes the plugin first: `devpro` or `kbase`, with no default
([What each holds](installing.md#plugins)). Everything below is per plugin: each has its own install
directory, so installing one never changes the other's.

The target must be an existing directory. The harness is `--harness=NAME` when given; otherwise the
one harness directory inside the target (`.claude/` or `.opencode/`); otherwise the one the target
itself is the directory of (`.claude`, `.opencode`, `.config/opencode`, or `Mage/Skills` for mage).
A target holding both `.claude/` and `.opencode/`, or neither and not itself a harness directory, is
refused until you pass `--harness`.

`--harness=opencode` installs into `.opencode/`, opencode's project harness directory. `--subdir=DIR`
makes `<target>/DIR` the harness directory instead, and `--subdir=` the target itself; the plugin's
install directory then lands inside it. `DIR` names a directory
inside the target: an absolute path, or one whose `..` segments leave the target, is refused with
nothing written. A target that is itself a harness directory is
installed into directly.

## What an install writes

The plugin is written to its own install directory below the harness directory:

| harness | install directory | invoked as |
|---|---|---|
| claude | `<harness-dir>/skills/<plugin>/`, one Claude Code plugin | `<plugin>:<name>` |
| opencode | `<harness-dir>/plugins/<plugin>/`, one plugin directory | `<plugin>-<name>` |
| mage | `<harness-dir>`, which is `<plugin>/` of a project, or `<plugins-parent>/<plugin>` | `<plugin>:<name>` |

A project install writes, inside the install directory:

- `agents/` and `commands/`: every agent and slash command the plugin holds
  ([Definition sets](definition-sets.md)). Under opencode these files have no frontmatter; the
  plugin's metadata is in `registry.json`, below.
- `skills/<name>/SKILL.md` for each skill the plugin holds, and each skill's supporting files.
- The packages that ship with a skill, in that skill's own directory (devpro):
  - the docdicer tools package, `skills/docdicer/tools/`: the `docdicer` script, a `.gitignore`
    holding `.venv/`, and `runner-snippets/docdicer.just` and `docdicer.mk`, which no install
    includes for you ([Definition sets](definition-sets.md));
  - `skills/development/scripts/cold-read.sh`, in the development skill's directory: a bash
    script, executable, that has one agent read one brief with no tools ([Running a cold
    read](#running-a-cold-read)). Under mage the script refuses to run.
- The harness-rendered files: the plugin manifest `.claude-plugin/plugin.json` (claude and mage),
  and for the kbase plugin `.mcp.json` (claude and mage), rendered whole. Under opencode
  `registry.json`, the registry: one record per agent, command and skill, and the `kbase` MCP server
  for the kbase plugin.
- The harness resources, copied unchanged and unstamped: a guardrail for claude and opencode, none
  for mage ([Guardrail](guardrail.md)). Under opencode these are `index.ts`, the entry that
  registers the plugin from `registry.json` and the Markdown files it lists, and `guardrail.ts`, which
  the entry runs.
- For the kbase plugin, the `kbase` skill and the rest of what [Knowledge base](knowledge-base.md)
  lists.

Under mage the `adjagent` skill is omitted. Claude Code reads the plugin's `agents/`, `commands/`
and `skills/` from `.claude/skills/<plugin>/`. Test suites and caches stay behind.

A project plugin loads only when the session starts at the project root, after Claude Code's trust
dialog ([Claude Code plugin loading](https://code.claude.com/docs/en/plugins/loading), "Check why a
repository plugin didn't load"). A claude install that writes the plugin prints: "If the new agents
are not available after using `adjagent install`, `/reload-plugins` rescans the agent list."

`tools/docdicer --install` installs docdicer into `tools/.venv`, building the venv where it is
missing or its python no longer runs, and otherwise keeping it and updating its pip; it needs `python3`
3.9 or later with its venv module, `git`, and the network. An install does not run it unprompted, with one
exception: an install that changes anything replaces the whole tools package, `tools/.venv`
included, and where that venv existed it then runs `tools/docdicer --install` to rebuild it. If that
run fails, the install says so in one line naming the command; its exit status and its other writes
are unaffected.

### Running a cold read

`cold-read.sh <agent> <brief-file> [<output-file>]`, run from the development skill's directory
(`.claude/skills/devpro/skills/development/` under claude, `.opencode/plugins/devpro/skills/development/`
under opencode), has the named agent read the brief with no tools and none of the project's
instruction files in context. The agent is named `<plugin>:<name>`, such as `devpro:architect`; under
opencode the colon reads as the hyphen of the registered id, `devpro-architect`. Your global agents
file still loads. It prints the
path of the reply, by default beside the brief as `<brief name>-<agent>.md` with `:` written as `-`.
It runs under claude and opencode only, and from the copy under the harness you are calling it from.
Under opencode it composes the agent's file in its fresh directory from the agent's record in
`registry.json` and its body file.

It needs `ADJAGENT_COLD_READ_DIR`: an existing directory outside the project, with no `CLAUDE.md`,
`AGENTS.md` or other instruction file at or above it (your own `~/.claude/` is exempt). Each run
works in a fresh private child of it, which the script removes on exit. Where the variable is unset
or the directory unsuitable, the script says why, naming the file where one is the cause, and
creates nothing.

To pin the reader's model, set `ADJAGENT_COLD_READ_MODEL`: a model name or alias under claude
(`opus`), `provider/model` under opencode. Unset, the reader gets the model the harness gives the
agent.

Under opencode a cold read is not yet reliable: each run's fresh directory is one opencode's service
has not run a session in, and there a model a provider plugin discovers is reported unavailable,
so the run fails or falls back to opencode's own free models.

### Plugin does not load

Symptom: after the install and a restart or `/reload-plugins`, `<plugin>:<name>` agents or commands
are missing. Causes and remedies, per [Claude Code plugin loading](https://code.claude.com/docs/en/plugins/loading):

- **Managed settings skip skills-directory plugins.** An organization's managed settings can stop
  Claude Code loading plugins from a `skills/` directory. Remedy: ask the administrator to allow
  it; nothing in the install changes this.
- **The `kbase` server is unapproved.** After an install of the kbase plugin, its `kbase` MCP
  server needs per-server approval before its tools appear. Remedy: approve it when Claude Code asks.
- **Something else failed.** Open `/plugin` and read the Errors tab for the plugin's load error.
- **A user-level plugin of the same name shadows the project's.** See [below](#a-user-level-plugin-shadows-the-projects).

## User-level installs

A home-directory target is a user-level install: `adjagent install devpro ~ --harness=claude` (or
`opencode`) renders the plugin's definitions into `~/.claude/skills/devpro/`
(`~/.config/opencode/plugins/devpro/`), with the manifest under claude and
`registry.json` under opencode, and writes nothing else but:

- under claude, for the kbase plugin, its own `.mcp.json`;
- under opencode, the entry `index.ts`, without which the plugin cannot register. A user-level kbase
  plugin under opencode therefore registers the `kbase` MCP server too, from `registry.json`.

No user settings file is written. No guardrail, no docdicer tools or development script, no
kb-tools, no include line. The docdicer skill is
installed without its script, and says so when asked to run it. `adjagent install-agents-file devpro ~/.claude`
installs that plugin's harness agents file there ([Agents file](agents-file.md)). A claude or opencode
project install keeps the agents-file block current in one place, your global agents file where it
holds the block and otherwise the project's `AGENTS.md` ([Agents file](agents-file.md#where-a-project-install-puts-it)).

### A user-level plugin shadows the project's

Claude Code loads one plugin per name, and the user-level one wins. Symptom: a project
install prints that its plugin "is shadowed by" `~/.claude/skills/<plugin>`, and the project's tuning,
version and `kbase` server do not load. Remedy: remove the user-level plugin, or work from it
alone. A user-level install prints the converse, that it takes precedence over every project's of
the same name. Neither install is refused. Only claude reports this.

## Mage

`adjagent install <plugin> <plugins-parent> --harness=mage` creates `<plugins-parent>/<plugin>`. Inside
that plugin the layout is the claude plugin's: the surfaces sit at its top level, with the manifest at
`.claude-plugin/plugin.json` beside them, rendered rather than copied. Mage ships no hook, and the
kbase plugin writes no include line and no `Makefile`: a plugin is not a repo project.
The install writes the agents file as `<plugin>/CLAUDE.md`, so a normal install needs no second step.

## An installed tree is an artifact

The installed tree is not for local edit. To change a definition, vendor the whole repository, or
fork it and open a pull request; adjagent merges nothing local. A consumer's own needs go in its
`CONVENTIONS.md` or `AGENTS.md` ([Installing, Customizing](installing.md#customizing-the-set)). Every
rendered file's first banner line says so. Re-running the install overwrites the tree and removes definitions this project no longer
produces, so a local edit is replaced with no diff to show it. A project that tracks the tree reviews
what changed in its `git diff`; one that does not has the install's report (how many files it wrote
and each path it pruned) and the version its runner pins.

A harness resource is replaced on each install, unless its install-time run fails
([Guardrail](guardrail.md)), and is never pruned, so one this project stops shipping stays in your
tree until you remove it.

## Re-installing and `--dry-run`

An install first runs into a scratch copy of the paths it manages and compares the copy with the
target. Where nothing would differ, in bytes or mode, and nothing would be created or removed, it
says so, exits 0 and touches nothing: no file, no `tools/`, no `tools/.venv`, no re-run.

```text
up to date: /home/me/foo/.claude — nothing written
```

Changing `--harness`, `--family` or the model maps changes bytes, so that install
proceeds. A different plugin is a different install directory, not a change of bytes in one. A
`.venv` directory is not install output and is outside the comparison.

`--dry-run` runs the same comparison and writes nothing. It prints what the install would change,
grouped as created, changed and removed, each path relative to the project root (absolute where
the path is outside it), and exits 0. A
folder the install would remove is listed under removed with a trailing `/`:

```text
dry run, nothing written — the install would change these files under /home/me/foo:
created:
  .claude/skills/devpro/agents/architect.md
  .claude/skills/devpro/skills/docdicer/tools/docdicer
changed:
  .claude/skills/devpro/agents/python-coder.md
removed:
  .claude/skills/devpro/agents/retired-agent.md
```

Where the install would replace `tools/.venv`, the dry run adds a line saying so, and that the
install would rebuild it with `tools/docdicer --install`, which needs the network.

What the install would leave alone or skip, such as a guardrail hook it skips, is printed on stderr
with the reason. That happens on an up-to-date run and
a dry run as on a changing one.

`adjagent install-agents-file` takes `--dry-run` too ([Agents file](agents-file.md)). Printed paths
and refusals name the real target, never the scratch copy. A dry run foresees the refusals an
install makes ([Refusals](#refusals)).

## Refusals

An install refuses, writing nothing, to:

- overwrite a file at one of its paths that carries no banner of this project's, such as your own
  `agents/python-coder.md`;
- keep the block in a project whose `CLAUDE.md` holds anything but the one-line `@AGENTS.md`
  redirect. Remedy: move that content into `AGENTS.md` and replace `CLAUDE.md` with `@AGENTS.md`;
- write an agents file (the project's `AGENTS.md`, or your global agents file) that holds marker lines other
  than one begin line followed by one end line. Remedy: leave exactly one ordered pair around the
  block, or delete the stray marker lines ([Agents file](agents-file.md#what-it-replaces)).

The refusal names each such path; move or remove them and install again. A target that starts
with a literal `~` is refused with a hint that the shell did not expand it. A plugin that names a
definition that does not exist refuses every render.

## What a re-install removes

A re-install removes each file under the install directory's `agents/`, `commands/` and `skills/`
that it did not write and that carries this project's generated banner, naming each. It looks
nowhere else, so another plugin's install directory is never touched. A file without a banner is
never touched.

## Upgrading from 0.15.0 and earlier

Nothing reads, rewrites or removes what an earlier adjagent version wrote. The files to remove by
hand, and the one search to run in the project, are listed in [Installing, Upgrading from 0.15.0 and
earlier](installing.md#upgrading-from-0150-and-earlier).
