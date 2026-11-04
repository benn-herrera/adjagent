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
installs into `<target>/DIR` instead, and `--subdir=` into the target itself. A target that is itself
a harness directory is installed into directly.

## What an install writes

A project install writes, inside the harness directory (`~/projects/foo/.claude/`):

- `agents/` and `commands/`: every agent and slash command of the base set
  ([Definition sets](definition-sets.md)).
- `skills/adjagent/SKILL.md` and `skills/docdicer/SKILL.md`, and the docdicer tools package beside
  the second, `skills/docdicer/tools/`: the `docdicer` script, a `.gitignore` holding `.venv/`, and
  `runner-snippets/docdicer.just` and `docdicer.mk`, which no install includes for you
  ([Definition sets](definition-sets.md)).
  Under mage the `adjagent` skill is omitted; the docdicer skill and its tools are written.
- The harness's own files, copied unchanged and unstamped: a guardrail for claude and opencode, none
  for mage ([Guardrail](guardrail.md)).
- With the kb set, the `kbase` skill and the rest of what [Knowledge base](knowledge-base.md)
  lists.

Claude Code reads agent definitions from `.claude/agents/`, slash commands from `.claude/commands/`
and skills from `.claude/skills/`. Test suites and caches stay behind.

`tools/docdicer --install` builds `tools/.venv` and installs docdicer into it; it needs `python3`
3.9 or later with its venv module, `git`, and the network. An install does not run it unprompted, with one
exception: an install that changes anything replaces the whole tools package, `tools/.venv`
included, and where that venv existed it then runs `tools/docdicer --install` to rebuild it. If that
run fails, the install says so in one line naming the command; its exit status and its other writes
are unaffected.

## User-level installs

A home-directory target is a user-level install: `adjagent install ~ --harness=claude` (or
`opencode`) renders the definitions into `~/.claude` (`~/.config/opencode`) and writes nothing else:
no guardrail, no tools package, no kb-tools, no MCP entry, no include line. The docdicer skill is
installed without its script, and says so when asked to run it. Add `--install-global-agents-file`
to install the harness agents file there too ([Agents file](agents-file.md)); on a project install
the flag is ignored.

## Mage

`adjagent install <plugins-parent> --harness=mage` creates `<plugins-parent>/adjagent`. The names and
paths inside the plugin are unchanged: the surfaces sit at its top level, with the manifest at
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
tree until you remove it.

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
grouped as created, changed and removed, each path relative to the project root, and exits 0:

```text
dry run, nothing written — the install would change these files under /home/me/foo:
created:
  .claude/agents/architect.md
  .claude/skills/docdicer/tools/docdicer
changed:
  .claude/agents/python-coder.md
removed:
  .claude/agents/retired-agent.md
```

Where the install would replace `tools/.venv`, the dry run adds a line saying so, and that the
install would rebuild it with `tools/docdicer --install`, which needs the network.

What the install would leave alone or skip, such as a settings file it cannot edit safely or a
guardrail hook it skips, is printed on stderr with the reason. That happens on an up-to-date run and
a dry run as on a changing one.

`adjagent install-agents-file` takes `--dry-run` too ([Agents file](agents-file.md)). Printed paths
and refusals name the real target, never the scratch copy. A symlinked surface or package
destination is refused on a dry run as on an install. A symlink or non-directory on the path to a
target, such as the directory above a settings file, is judged by the install itself; a dry run may
not foresee it.

## Refusals

An install refuses, writing nothing, to:

- overwrite a file at one of its paths that carries no banner of this project's, such as your own
  `agents/python-coder.md`;
- write below a symlink or a non-directory on the way to one of its targets.

The refusal names each such path; move or remove them and install again. A harness settings file
that is not UTF-8, or whose `hooks` or `PreToolUse` has the wrong shape (`null` included), refuses
the install the same way ([Guardrail](guardrail.md)). A target that is a literal `~` is refused with
a hint that the shell did not expand it.

## What a re-install removes

A re-install removes each file under `agents/`, `commands/` and `skills/` that it did not write and
that carries this project's generated banner, naming each, and removes the trees an earlier version
installed. A file without a banner is never touched. A plain `adjagent install` into a directory
holding no kb install writes nothing of the kb set and removes each file of one it finds as stale
([Knowledge base](knowledge-base.md)).
