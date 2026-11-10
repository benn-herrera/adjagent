# Adjagent

Adjagent generates two plugins of agents and skills, `devpro` (coding and platform
specialists and more) and `kbase` (knowledge-base tooling), and installs one into your project
with `adjagent install`.
Every shared span of text is written once and every definition is rendered from it, tuned per model
family, so the installed set agrees with itself.

## Requirements and Supported Platforms

- `python3` 3.9 or later with its `venv` module.
- `git` on `PATH`: pip installs adjagent from a git tag.
- `perl` with core `JSON::PP`, optional: the claude guardrail needs it. Without it the install skips
  that hook and installs everything else ([Guardrail](docs/guardrail.md)).
- The kbase plugin runs on macOS or Linux only; native Windows is unsupported for it. It needs kbase,
  which you install, among its other requirements ([Knowledge base](docs/knowledge-base.md#requirements)).
- The kbase plugin's runner include line needs `just` 1.33 or later, if the project's runner is a
  justfile.

Adjagent installs each plugin for three harnesses: claude (`.claude/skills/<plugin>/`, whose agents
run as `<plugin>:<name>`), opencode (a directory at `.opencode/plugins/<plugin>/`, whose agents
register as `<plugin>-<name>`) and mage (a directory of its own).

## Quick Start Guide

Add the recipe for your project's runner. It installs adjagent, pinned to `ADJAGENT_VER`, into the
project's `.venv/` (the project's existing one, or one it creates), then installs the `devpro` plugin
into the project for both harnesses ([Plugins](#plugins) says what each plugin holds).

A project that uses one harness drops the other harness's `install` line.

Justfile:

```just
ADJAGENT_VER := "0.16.0"
VENV := justfile_dir() / ".venv"
PYTHON := "\"" + VENV + "/bin/python" + "\""
ADJAGENT := "\"" + VENV + "/bin/adjagent" + "\""
agents:
  #!/usr/bin/env bash
  set -euo pipefail
  [[ -x {{PYTHON}} ]] || python3 -m venv "{{VENV}}"
  [[ -x {{ADJAGENT}} && "$({{ADJAGENT}} --version)" == "{{ADJAGENT_VER}}" ]] || \
    {{PYTHON}} -m pip install "git+https://github.com/benn-herrera/adjagent@v{{ADJAGENT_VER}}"
  {{ADJAGENT}} install devpro . --harness=claude
  {{ADJAGENT}} install devpro . --harness=opencode
```

Makefile:

```make
SHELL := /bin/bash
ADJAGENT_VER := 0.16.0
VENV := .venv
PYTHON := $(VENV)/bin/python
ADJAGENT := $(VENV)/bin/adjagent
.PHONY: agents
agents:
	[[ -x "$(PYTHON)" ]] || python3 -m venv "$(VENV)"
	[[ -x "$(ADJAGENT)" && "$$("$(ADJAGENT)" --version)" == "$(ADJAGENT_VER)" ]] || \
	  "$(PYTHON)" -m pip install "git+https://github.com/benn-herrera/adjagent@v$(ADJAGENT_VER)"
	"$(ADJAGENT)" install devpro . --harness=claude
	"$(ADJAGENT)" install devpro . --harness=opencode
```

Run `just agents` or `make agents`. The recipe never recreates or clears an existing `.venv`, and runs
pip only when the venv's adjagent is not the pinned version.

Under claude, invoke the plugin's agents and skills as `devpro:<name>`, and run
`/reload-plugins` (or restart Claude Code) after an install for new definitions to register.

Besides the installed trees, the install keeps the operator working rules as one marked block in one
place: your global agents file (`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`) if it already
holds the block, otherwise the project's `AGENTS.md`, where under claude `CLAUDE.md` is created as the
one-line `@AGENTS.md` redirect. A `CLAUDE.md` holding anything else is refused with nothing written
([Refusals](docs/install-reference.md#refusals)). Only the block is replaced, and the rest of each file
is kept; a write that changes an agents file keeps one rolling `backup.<name>` beside it, such as
`backup.AGENTS.md`. A run that would change nothing writes nothing ([Agents file](docs/agents-file.md)).

Add the installed trees to the project's `.gitignore`:

```text
.claude/
.opencode/
```

The project's `AGENTS.md` and `CLAUDE.md` are not installed trees: the install may write them (above),
so decide whether to commit them.

The `.venv/` entry a Python project conventionally ignores covers the venv; add it if the project
ignores nothing there. The docdicer tools' own venv needs no entry: its `.gitignore` is installed
with it.

To update, change `ADJAGENT_VER` to the new release's version and run the recipe again. Everything it
installs is documented in the [install reference](docs/install-reference.md).

To install the knowledge-base plugin, run `adjagent install kbase . --harness=claude` (or
`--harness=opencode`) and install kbase first ([Knowledge base](docs/knowledge-base.md)).

## Plugins

An install delivers one plugin, named as its first argument: `adjagent install PLUGIN TARGET`. There is
no default.

- **devpro** is the coding, platform and specialist agents and their skills.
- **kbase** is the `kbase` skill with the kb-tools runner snippets and the `kbase` MCP server entry,
  and the definitions a knowledge-base project works with. It needs the kbase program on your
  machine ([Knowledge base](docs/knowledge-base.md)).

[SPEC](PROJECT_DOCS/SPEC/deployed-surfaces/plugins.md) (SPEC.md, Deployed Surfaces, Plugins) lists
each plugin's members. Installing both in one place gives duplicate agents under different
names. [Definition sets](docs/definition-sets.md) describes the definitions.

## Upgrading from 0.15.0 and earlier

An install never reads, rewrites or removes what an earlier version wrote, so remove these by hand
from each project, and from `~/.claude`, `~/.config/opencode` and `~/Mage/Skills` where you installed
at user level:

- `.claude/skills/adjagent/`, the earlier claude plugin.
- The unprefixed files in `.opencode/agents/`, `.opencode/commands/` and `.opencode/skills/` that
  carry the generated banner (a `!GENERATED!` comment on their first lines), and the earlier
  packages inside `.opencode/skills/`: `docdicer/tools/` (its `.venv/` included),
  `dev-process/scripts/` and `kbase/kb-tools/`.
- `.opencode/plugins/guardrail.ts`.
- The `kbase` entry in `opencode.json` or `opencode.jsonc`, under `.opencode/` or the project root.
- `~/Mage/Skills/adjagent/`, the earlier mage plugin.
- In a project that will not install the kbase plugin: the line in its `justfile` or `Makefile` that
  imports or includes `kb.just` / `kb.mk` from `runner-snippets/`. Installing the kbase plugin rewrites
  that line itself.

Then install the plugin you want. Text outside this repository that names the earlier process skill
is not rewritten either. In each project, search for it and name the skill bare, "the `development`
skill (devpro)", which each harness resolves to its own spelling:

```sh
grep -rln 'dev-process' --include='*.md' --exclude-dir=.claude --exclude-dir=.opencode .
```

The excluded directories hold installed trees, which the next install replaces.

## Previewing and re-installing

`--dry-run` prints what an install would create, change and remove, grouped and relative to the
project root (a path outside it prints absolute), and writes nothing:

```sh
.venv/bin/adjagent install devpro . --harness=claude --dry-run
```

An install that would change nothing says so, exits 0 and touches nothing. Rules and sample output:
[Install reference](docs/install-reference.md#re-installing-and---dry-run).

## Running adjagent by hand

To run `adjagent` yourself, for a one-off install or a preview, install it with pipx or into a venv
of your own. A bare `pip install` outside a venv is refused on Homebrew and most distro Pythons
(`externally-managed-environment`), and Apple's `/usr/bin/python3` puts the command in
`~/Library/Python/3.9/bin`, which is not on `PATH`.

```sh
pipx install "git+https://github.com/benn-herrera/adjagent@v0.16.0"
pipx ensurepath   # puts pipx's bin directory on PATH; open a new shell afterwards
adjagent --help
adjagent install devpro ~/projects/foo
```

Or, with a venv:

```sh
python3 -m venv ~/.venvs/adjagent
~/.venvs/adjagent/bin/pip install "git+https://github.com/benn-herrera/adjagent@v0.16.0"
~/.venvs/adjagent/bin/adjagent install devpro ~/projects/foo
```

A project's own pin belongs in its runner recipe, above. From a checkout of this repository the same
command runs as `PYTHONPATH=<clone> python3 -m adjagent install devpro ~/projects/foo`, with the same result
([Development](docs/development.md)).

## Customizing the set

The installed definitions and the installed adjagent package are never edited: the next install
overwrites the definitions, and the next update overwrites the package.

- **A project's own conventions** go in its `CONVENTIONS.md` or `AGENTS.md`, which the agents read and
  no install writes.
- **A persistent change to the definitions** means one of two routes. Vendor the whole repository
  as an organization-hosted copy, edit the definitions there and install from it; that copy is yours to
  maintain from then on. Or fork adjagent and open a pull request.

Adjagent merges nothing local into the set it generates. The `adjagent` skill that the install delivers
tells a session the same rule.

## Mage plugin release

The mage plugin is published as a release: one tarball and detached signature per plugin. Unpack
one; `<plugin>` below is `devpro` or `kbase` ([Plugins](#plugins)). The tarballs hold the plugin only;
the kbase plugin's `kbase` MCP command is the bare `kbase`, so you install kbase yourself
([Knowledge base](docs/knowledge-base.md#requirements)). Contract:
[SPEC](PROJECT_DOCS/SPEC/mage-release.md).

1. Download `adjagent-mage-<plugin>-v<version>.tgz` from the release `v<version>` of
   [benn-herrera/adjagent](https://github.com/benn-herrera/adjagent/releases), and optionally its
   `adjagent-mage-<plugin>-v<version>.tgz.asc`.
2. Optionally check the tarball against the signature. Fetch the release signer's public key over WKD
   (the developer's key is at <https://keyoxide.org/wkd/benn@bennherrera.dev>), then verify:

   ```sh
   gpg --auto-key-locate wkd --locate-external-keys benn@bennherrera.dev
   gpg --verify adjagent-mage-<plugin>-v<version>.tgz.asc adjagent-mage-<plugin>-v<version>.tgz
   ```

3. Unpack it into Mage's skills directory, removing any earlier copy first:

   ```sh
   rm -rf ~/Mage/Skills/<plugin>
   tar -xzf adjagent-mage-<plugin>-v<version>.tgz -C ~/Mage/Skills/
   ```

   The tarball has one top-level `<plugin>/` directory, so this leaves `~/Mage/Skills/<plugin>`.
4. For the kbase plugin, install kbase if you have not. Native Windows is unsupported for it.
5. For the kbase plugin, restart Mage so it starts the `kbase` MCP server; the plugin's entry
   finds `kbase` on `PATH`. Do the same after installing or upgrading kbase while Mage is running.

## More documentation

- [Install reference](docs/install-reference.md): target and harness resolution, the install
  directory of each plugin, user-level installs, what an install writes, refusals.
- [Guardrail](docs/guardrail.md): the hooks that block shell writes behind the edit tools.
- [Agents file](docs/agents-file.md): the operator-level working rules.
- [Model tuning](docs/model-tuning.md): families, anchors and tier maps.
- [Definition sets](docs/definition-sets.md): the agents and skills of each plugin.
- [Knowledge base](docs/knowledge-base.md): the kbase plugin and its toolchain.
- [Development](docs/development.md): building, testing, layout, releasing, authoring a family.
- [Agent sandboxing](agent-sandboxing/README.md): a checklist for running an agent harness as a
  separate, unprivileged local user. It is accident protection, not hack-proofing.
- [docs index](docs/index.md), and the project's contract documents under `PROJECT_DOCS/`:
  [THESIS](PROJECT_DOCS/entry-point.md), [SPEC](PROJECT_DOCS/SPEC/entry-point.md),
  [ARCHITECTURE](PROJECT_DOCS/ARCHITECTURE/entry-point.md),
  [CONVENTIONS](PROJECT_DOCS/CONVENTIONS/entry-point.md).

## Third Party Acknowledgements

What adjagent installs into a project (`agents/`, `commands/`, `skills/`) is stdlib-only Python and
shell with no third-party dependencies. Everything below is used by this repository's development,
build and documentation checks, or by the optional kbase plugin; none is bundled.

- **pytest** (the pytest developers, MIT): runs the test suite; installed into this repository's
  `.venv` by `just test`.
- **black** (Łukasz Langa and contributors, MIT): formats the Python source; installed into `.venv`
  by `just test` and run by `just format-python`.
- **isort** (Timothy Crosley and contributors, MIT): sorts Python imports; installed and run the same
  way.
- **flake8** (Tarek Ziadé and contributors, Python Code Quality Authority, MIT): lints the Python
  source; installed and run the same way.
- **setuptools** (Python Packaging Authority, MIT): the build backend `pyproject.toml` names;
  installed into `.venv`.
- **build** (Python Packaging Authority, MIT): the frontend `just build` runs; installed into
  `.venv`.
- **docdicer** (Benn Herrera, MIT): the link and tree checks behind `just check-links`, installed into
  `.venv` from its git tag. The installed `tools/docdicer` script installs it from the same tag
  into a venv beside the script when you ask it to.
- **pandoc** (John MacFarlane and contributors, GPL-2.0-or-later): converts LaTeX to Markdown for the
  kbase plugin; a host program you install ([Knowledge base](docs/knowledge-base.md#requirements)).
- **Graphviz** `dot` (Graphviz authors, Eclipse Public License; the installed 16.1.0's `COPYING` is
  version 2.0): optional, renders the kbase plugin's claim graph diagrams as SVG; a host program you
  install.
- **kbase** (Benn Herrera, MIT): the Go binary the kbase plugin's runner snippets and MCP entry drive; a
  host program you install ([Knowledge base](docs/knowledge-base.md#the-toolchain)).
- **@opencode/plugin** (the opencode project, MIT): the module the opencode plugin
  entry, `index.ts`, imports `Plugin` from to register the plugin; opencode supplies it, and nothing
  here bundles it.
- **perl** (Larry Wall and the Perl 5 porters, Artistic License or GPL, at your choice): runs the
  claude guardrail hook at session time, and the guardrail's tests; a host program you install.
- **bun** (Oven, MIT): runs the opencode guardrail's and plugin entry's TypeScript cases in
  `just test`; a host program you install.
