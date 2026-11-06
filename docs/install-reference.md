# Install reference

The rules behind `adjagent install`: where it writes, what it writes, what it leaves alone and when
it refuses. The route that puts adjagent into a project is in the [README](../README.md#quick-start-guide).

`adjagent` and `python3 -m adjagent` are the same command. In a clone of this repository the `just`
recipes map to `adjagent` verbs: `just install` is `adjagent install`, `just install-with-kb` is
`adjagent install --with-kb`, and `just install-agents-file` is `adjagent install-agents-file`.
`just render` is not `adjagent render`: it takes a slug and forwards its `--*` flags to
`adjagent install`. Every `--*` flag after the target forwards verbatim, so tuning the render is one
more flag ([Model tuning](model-tuning.md)). Installed from a wheel, the checks that protect a clone
do not apply: there is no repository to refuse as an install root, and no uncommitted state to refuse
the agents file for.

## Choosing the target

The target must be an existing directory. The harness is `--harness=NAME` when given; otherwise the
one harness directory inside the target (`.claude/` or `.opencode/`); otherwise the one the target
itself is the directory of (`.claude`, `.opencode`, `.config/opencode`, or `Mage/Skills` for mage).
A target holding both `.claude/` and `.opencode/`, or neither and not itself a harness directory, is
refused until you pass `--harness`.

`--harness=opencode` installs into `.opencode/`, each harness's project directory. `--subdir=DIR`
makes `<target>/DIR` the harness directory instead, and `--subdir=` the target itself; under claude
the plugin then lands at `<DIR>/skills/adjagent`. A target that is itself a harness directory is
installed into directly.

## What an install writes

Under claude the set is one Claude Code plugin named `adjagent`, written to `skills/adjagent/` inside
the harness directory (`~/projects/foo/.claude/skills/adjagent/`), with its manifest at
`.claude-plugin/plugin.json`. Its agents and commands are invoked as `adjagent:<name>`. Mage and
opencode write straight into their harness directory, and mage's agents and commands carry the same
`adjagent:` prefix. A project install writes, inside that directory (the plugin, under claude):

- `agents/` and `commands/`: every agent and slash command of the base set
  ([Definition sets](definition-sets.md)).
- `skills/adjagent/SKILL.md`, `skills/docdicer/SKILL.md` and `skills/dev-process/SKILL.md` with its
  four files under `skills/dev-process/references/`, and the docdicer tools package beside the
  docdicer skill, `skills/docdicer/tools/`: the `docdicer` script, a `.gitignore` holding `.venv/`,
  and `runner-snippets/docdicer.just` and `docdicer.mk`, which no install includes for you
  ([Definition sets](definition-sets.md)).
  Under mage the `adjagent` skill is omitted; the docdicer and dev-process skills and the docdicer
  tools are written.
- The harness's own files, copied unchanged and unstamped: a guardrail for claude and opencode, none
  for mage ([Guardrail](guardrail.md)).
- With the kb set, the `kbase` skill and the rest of what [Knowledge base](knowledge-base.md)
  lists.

Claude Code reads the plugin's `agents/`, `commands/` and `skills/` from
`.claude/skills/adjagent/`. Test suites and caches stay behind.

A project plugin loads only when the session starts at the project root, after Claude Code's trust
dialog ([Claude Code plugin loading](https://code.claude.com/docs/en/plugins/loading), "Check why a
repository plugin didn't load"). A claude install that writes the plugin prints: "If the new agents
are not available after using `adjagent install`, use `/reload-plugins` to rescan the agent list."

`tools/docdicer --install` builds `tools/.venv` and installs docdicer into it; it needs `python3`
3.9 or later with its venv module, `git`, and the network. An install does not run it unprompted, with one
exception: an install that changes anything replaces the whole tools package, `tools/.venv`
included, and where that venv existed it then runs `tools/docdicer --install` to rebuild it. If that
run fails, the install says so in one line naming the command; its exit status and its other writes
are unaffected.

### Plugin does not load

Symptom: after the install and a restart or `/reload-plugins`, `adjagent:<name>` agents or commands
are missing. Causes and remedies, per [Claude Code plugin loading](https://code.claude.com/docs/en/plugins/loading):

- **Managed settings skip skills-directory plugins.** An organization's managed settings can stop
  Claude Code loading plugins from a `skills/` directory. Remedy: ask the administrator to allow
  it; nothing in the install changes this.
- **The `kbase` server is unapproved.** On a kb install the plugin's `kbase` MCP server needs
  per-server approval before its tools appear. Remedy: approve it when Claude Code asks.
- **Something else failed.** Open `/plugin` and read the Errors tab for the plugin's load error.
- **A user-level `adjagent` plugin shadows the project's.** See [below](#a-user-level-plugin-shadows-the-projects).

## User-level installs

A home-directory target is a user-level install: `adjagent install ~ --harness=claude` (or
`opencode`) renders the definitions into `~/.claude/skills/adjagent/` (`~/.config/opencode`), with
the plugin manifest under claude, and writes nothing else but the kb set's MCP entry: under claude,
with `--with-kb`, the user-level plugin's own `.mcp.json`, and no user settings file. No guardrail, no tools package, no
kb-tools, no include line. The docdicer skill is
installed without its script, and says so when asked to run it. Add `--install-global-agents-file`
to install the harness agents file in `~/.claude` too, beside the plugin
([Agents file](agents-file.md)); on a project install the flag is ignored. A claude or opencode
project install keeps the agents-file block current in one place, your global agents file where it
holds the block and otherwise the project's `AGENTS.md` ([Agents file](agents-file.md#where-a-project-install-puts-it)).

### A user-level plugin shadows the project's

Claude Code loads one plugin per name, and the user-level `adjagent` wins. Symptom: a project
install prints that its plugin "is shadowed by" `~/.claude/skills/adjagent`, and the project's tuning,
version and `kbase` server do not load. Remedy: remove the user-level plugin, or work from it
alone. A user-level install prints the converse, that it takes precedence over every project's.
Neither install is refused.

## Upgrading from the flat layout

The plugin form first ships in 0.15.0; 0.14.0 and earlier wrote the set directly
under `.claude/` (`.claude/agents/`, `.claude/skills/docdicer/tools/`). Run the install over it and
expect these changes, in the order you meet them:

1. **Invocation.** Agents and commands are now invoked as `adjagent:<name>`. Autocomplete may still
   offer the bare name; type the prefixed one.
2. **Start, trust, reload.** The plugin loads only for a session started at the project root, after
   the trust dialog. A newly trusted project needs `/reload-plugins` or a restart before the
   plugin's components register. A session that began before the first plugin install keeps its old
   bare-named agents loaded, even though the install deleted their files: restart it once. After
   that, `/reload-plugins` picks up every later install. If the plugin still does not appear, see
   [Plugin does not load](#plugin-does-not-load).
3. **Settings and hook.** The install removes its own entry from `.claude/settings.json`, on a kb
   install its `kbase` entry from `.mcp.json`, and `.claude/hooks/guardrail.pl`; the plugin's own
   `hooks/hooks.json` registers the new hook. Your other entries stay. What is left alone and why:
   [Guardrail](guardrail.md#claude).
4. **Include line (kb install).** The install rewrites the existing runner include line in place to
   the plugin's path; it adds no second line. The `.gitignore` line for `.mcp.json` is no longer
   needed, because the project's `.mcp.json` no longer carries the `kbase` entry.
5. **Agents file.** The install keeps the agents-file block current in one place: your global file
   where it already holds the block, otherwise the project's `AGENTS.md`, plus a `CLAUDE.md` that
   holds only `@AGENTS.md`. The block names `adjagent:` definitions. A `CLAUDE.md` with other
   content is refused ([Refusals](#refusals)); details in [Agents file](agents-file.md).

The install also removes the generated files of the flat layout, each folder that leaves empty
(`.claude/agents/` and `.claude/commands/` when they held nothing of yours), and the old package
folders, printing `removed retired package destination <path>` for each, and rebuilds a docdicer
`tools/.venv` it found at either place. A user-level install removes no package folder.

## Mage

`adjagent install <plugins-parent> --harness=mage` creates `<plugins-parent>/adjagent`. Inside that
plugin the layout is the claude plugin's: the surfaces sit at its top level, with the manifest at
`.claude-plugin/plugin.json` beside them, rendered rather than copied. Mage ships no hook, always
installs the kb set, and writes no include line and no `Makefile`: a plugin is not a repo project.
The install writes the agents file as `<plugin>/CLAUDE.md`, so a normal install needs no second step.

## An installed tree is an artifact

The installed tree is not for local edit. To change a definition, vendor the whole repository, or
fork it and open a pull request; adjagent merges nothing local. A consumer's own needs go in its
`CONVENTIONS.md` or `AGENTS.md` ([README, Customizing](../README.md#customizing-the-set)). Every
rendered file's first banner line says so. Re-running the install overwrites the tree and removes definitions this project no longer
produces, so a local edit is replaced with no diff to show it. A project that tracks the tree reviews
what changed in its `git diff`; one that does not has the install's report (how many files it wrote
and each path it pruned) and the version its runner pins.

A harness's shipped file is replaced on each install, unless its install-time run fails
([Guardrail](guardrail.md)), and is never pruned, so one this project stops shipping stays in your
tree until you remove it. The one exception is the flat layout's `.claude/hooks/guardrail.pl`, which
a claude project install removes when it writes the plugin's replacement.

## Re-installing and `--dry-run`

An install first runs into a scratch copy of the paths it manages and compares the copy with the
target. Where nothing would differ, in bytes or mode, and nothing would be created or removed, it
says so, exits 0 and touches nothing: no file, no `tools/`, no `tools/.venv`, no re-run.

```text
up to date: /home/me/foo/.claude — nothing written
```

Changing `--harness`, `--family`, the model maps or `--with-kb` changes bytes, so that install
proceeds. A `.venv` directory is not install output and is outside the comparison.

`--dry-run` runs the same comparison and writes nothing. It prints what the install would change,
grouped as created, changed and removed, each path relative to the project root (absolute where
the path is outside it), and exits 0. A
folder the install would remove is listed under removed with a trailing `/`:

```text
dry run, nothing written — the install would change these files under /home/me/foo:
created:
  .claude/skills/adjagent/agents/architect.md
  .claude/skills/adjagent/skills/docdicer/tools/docdicer
changed:
  .claude/skills/adjagent/agents/python-coder.md
removed:
  .claude/skills/adjagent/agents/retired-agent.md
```

Where the install would replace `tools/.venv`, the dry run adds a line saying so, and that the
install would rebuild it with `tools/docdicer --install`, which needs the network.

What the install would leave alone or skip, such as a settings file it cannot edit safely or a
guardrail hook it skips, is printed on stderr with the reason. That happens on an up-to-date run and
a dry run as on a changing one.

`adjagent install-agents-file` takes `--dry-run` too ([Agents file](agents-file.md)). Printed paths
and refusals name the real target, never the scratch copy. A dry run foresees the refusals an
install makes for a dangling symlink ([Refusals](#refusals)). It does not foresee one case: where a
regular file stands in place of the directory an MCP settings file goes in (`.opencode` as a file),
the dry run shows the settings file created, but the install reports the obstacle and leaves it.

## Refusals

An install refuses, writing nothing, to:

- overwrite a file at one of its paths that carries no banner of this project's, such as your own
  `agents/python-coder.md`;
- write below a non-directory on the way to one of its targets, or through a dangling symlink on the
  way to one, or at one whose named path sits in a directory that does not exist;
- keep the block in a project whose `CLAUDE.md` holds anything but the one-line `@AGENTS.md`
  redirect. Remedy: move that content into `AGENTS.md` and replace `CLAUDE.md` with `@AGENTS.md`;
- write an agents file (the project's `AGENTS.md`, or your global one) that holds marker lines other
  than one begin line followed by one end line. Remedy: leave exactly one ordered pair around the
  block, or delete the stray marker lines ([Agents file](agents-file.md#what-it-replaces)).

The refusal names each such path; move or remove them and install again. A symlink anywhere else
is the file or directory it names: the install writes through it, and a dangling one at a target has
what it names created. Removing a symlink removes the link, never what it names. A harness MCP settings file
the install writes into that is not UTF-8, or has the wrong shape where the entry goes (`null`
included), refuses the install the same way. Cleaning an earlier install's entries out of a
settings file never refuses ([Guardrail](guardrail.md)). A target that is a literal `~` is refused with
a hint that the shell did not expand it.

## What a re-install removes

A re-install removes each file under `agents/`, `commands/` and `skills/` that it did not write and
that carries this project's generated banner, naming each, and removes the trees an earlier version
installed. A file without a banner is never touched. A plain `adjagent install` into a directory
holding no kb install writes nothing of the kb set and removes each file of one it finds as stale
([Knowledge base](knowledge-base.md)).
