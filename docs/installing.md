# Installing devpro

Everything about putting devpro into a project beyond the justfile recipe in the
[README's Quick Start Guide](../README.md#quick-start-guide): requirements, the plugins, the Makefile
recipe, what to commit, previewing, updating, running devpro by hand, and customizing the set.

## Requirements

- `python3` 3.9 or later with its `venv` module.
- `git` on `PATH`: pip installs devpro from a git tag.
- `perl` with core `JSON::PP`, optional: the claude guardrail needs it. Without it the install skips
  that hook and installs everything else ([Guardrail](guardrail.md)).
- The kbase plugin runs on macOS or Linux only; native Windows is unsupported for it. It needs kbase,
  which you install, among its other requirements ([Knowledge base](knowledge-base.md#requirements)).
- The runner include lines either plugin's project install writes need `just` 1.33 or later, if the
  project's runner is a justfile.

devpro installs each plugin for three harnesses: claude (`.claude/skills/<plugin>/`, whose agents
run as `<plugin>:<name>`), opencode (a directory at `.opencode/plugins/<plugin>/`, whose agents
register as `<plugin>-<name>`) and mage (a directory of its own).

## Plugins

An install delivers one plugin, named by `--plugin=NAME` (default `devpro`): `devpro install TARGET
[--plugin=NAME]`. A positional plugin is refused.

- **devpro** is the coding, platform and specialist agents and their skills.
- **kbase** is the `kbase` skill with the kb-tools runner snippets and the `kbase` MCP server entry,
  the `docdicer` skill with its tools, and the definitions a knowledge-base project works with. It needs the kbase program on your
  machine ([Knowledge base](knowledge-base.md)).

[SPEC's Plugins page](../PROJECT_DOCS/SPEC/deployed-surfaces/plugins.md) lists
each plugin's members. Installing both in one place gives duplicate agents under different
names. [Definition sets](definition-sets.md) describes the definitions.

## Makefile recipe

For a project whose runner is a Makefile, this recipe does what the README's justfile recipe does:

```make
SHELL := /bin/bash
DEVPRO_VER := 0.17.0
VENV := .venv
PYTHON := $(VENV)/bin/python
DEVPRO := $(VENV)/bin/devpro
.PHONY: agents
agents:
	[[ -x "$(PYTHON)" ]] || python3 -m venv --upgrade-deps "$(VENV)"
	[[ -x "$(DEVPRO)" && "$$("$(DEVPRO)" --version)" == "$(DEVPRO_VER)" ]] || \
	  "$(PYTHON)" -m pip install "git+https://github.com/benn-herrera/devpro@v$(DEVPRO_VER)"
	"$(DEVPRO)" install . --harness=claude
	"$(DEVPRO)" install . --harness=opencode
```

Run `make agents`. The recipe never recreates or clears an existing `.venv`, and runs pip only when
the venv's devpro is not the pinned version.

## The agents file

Besides the installed trees, the install keeps the operator working rules as one marked block in one
place: your global agents file (`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`) if it already
holds the block, otherwise the project's `AGENTS.md`, where under claude `CLAUDE.md` is created as the
one-line `@AGENTS.md` redirect. A `CLAUDE.md` holding anything else is refused with nothing written
([Refusals](install-reference.md#refusals)). Only the block is replaced, and the rest of each file
is kept; a write that changes an agents file keeps one rolling `backup.<name>` beside it, such as
`backup.AGENTS.md`. A run that would change nothing writes nothing ([Agents file](agents-file.md)).

## What to commit

The installed trees, the recipe's `.venv/` and `__pycache__/` go in the project's `.gitignore`
([Quick Start Guide](../README.md#quick-start-guide)). The project's `AGENTS.md` and `CLAUDE.md` are
not installed trees: the install may write them (above), so decide whether to commit them.

A project install also writes the docdicer include line into the project's `justfile` or `Makefile`,
creating a `Makefile` where there is neither. That runner file is tracked: commit it
([Runner include lines](install-reference.md#runner-include-lines)).

The docdicer tools' own venv needs no entry: its `.gitignore` is installed with it.

## Installing the kbase plugin

To install the knowledge-base plugin, run `devpro install . --plugin=kbase --harness=claude` (or
`--harness=opencode`) and install kbase first ([Knowledge base](knowledge-base.md)).

## Previewing and re-installing

`--dry-run` prints what an install would create, change and remove, grouped and relative to the
project root (a path outside it prints absolute), and writes nothing:

```sh
.venv/bin/devpro install . --harness=claude --dry-run
```

An install that would change nothing says so, exits 0 and touches nothing. Rules and sample output:
[Install reference](install-reference.md#re-installing-and---dry-run).

## Updating

To update, change `DEVPRO_VER` to the new release's version and run the recipe again. Everything it
installs is documented in the [install reference](install-reference.md).

## Running devpro by hand

To run `devpro` yourself, for a one-off install or a preview, install it with pipx or into a venv
of your own. A bare `pip install` outside a venv is refused on Homebrew and most distro Pythons
(`externally-managed-environment`), and Apple's `/usr/bin/python3` puts the command in
`~/Library/Python/3.9/bin`, which is not on `PATH`.

```sh
pipx install "git+https://github.com/benn-herrera/devpro@v0.17.0"
pipx ensurepath   # puts pipx's bin directory on PATH; open a new shell afterwards
devpro --help
devpro install ~/projects/foo
```

Or, with a venv:

```sh
python3 -m venv ~/.venvs/devpro
~/.venvs/devpro/bin/pip install "git+https://github.com/benn-herrera/devpro@v0.17.0"
~/.venvs/devpro/bin/devpro install ~/projects/foo
```

A project's own pin belongs in its runner recipe ([Quick Start Guide](../README.md#quick-start-guide)).
From a checkout of this repository the same command runs as
`PYTHONPATH=<clone> python3 -m devpro install ~/projects/foo`, with the same result
([Development](development.md)).

## Customizing the set

The installed definitions and the installed devpro package are never edited: the next install
overwrites the definitions, and the next update overwrites the package.

- **A project's own conventions** go in its `CONVENTIONS.md` or `AGENTS.md`, which the agents read and
  no install writes.
- **A persistent change to the definitions** means one of two routes. Vendor the whole repository
  as an organization-hosted copy, edit the definitions there and install from it; that copy is yours to
  maintain from then on. Or fork the devpro project and open a pull request.

devpro merges nothing local into the set it generates. The `install` skill that the install delivers
tells a session the same rule.
