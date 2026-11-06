# Adjagent

Adjagent generates a multi-capability set of agents, commands and skills (coding and platform
specialists, knowledge-base tooling and more) and installs it into your project with `adjagent install`.
Every shared span of text is written once and every definition is rendered from it, tuned per model
family, so the installed set agrees with itself.

## Requirements and Supported Platforms

- `python3` 3.9 or later with its `venv` module.
- `git` on `PATH`: pip installs adjagent from a git tag.
- `perl` with core `JSON::PP`, optional: the claude guardrail needs it. Without it the install skips
  that hook and installs everything else ([Guardrail](docs/guardrail.md)).
- The kb set runs on macOS or Linux only; native Windows is unsupported for it. It needs kbase, which
  you install, among its other requirements ([Knowledge base](docs/knowledge-base.md#requirements)).

Adjagent installs for three harnesses: claude (one plugin, `.claude/skills/adjagent/`, whose agents run as `adjagent:<name>`), opencode (`.opencode/`) and mage (a plugin).

## Quick Start Guide

Add the recipe for your project's runner. It installs adjagent, pinned to `AGENTS_VER`, into the
project's `.venv/` (the project's existing one, or one it creates), then installs the agent set into the
project for both harnesses and the operator-level agents file for each.

The install writes in two places besides the installed trees:

- **The project root.** `AGENTS.md` holds the operator working rules as one marked block, and under
  claude `CLAUDE.md` is created as the one-line `@AGENTS.md` redirect. A `CLAUDE.md` holding anything
  else is refused with nothing written ([Refusals](docs/install-reference.md#refusals)). A write that
  changes an agents file keeps one rolling `backup.<name>` beside it, such as `backup.AGENTS.md`.
- **Your home directory.** The last two lines of the recipe write `~/.claude/CLAUDE.md` and
  `~/.config/opencode/AGENTS.md`. They replace only the block between adjagent's marker lines, or
  append the block to a file that has none, and keep the rest of each file, with the same backup.

The first run therefore keeps the block in the project's `AGENTS.md`, since your home files hold none
yet, and then adds it to the home files. Every later run finds the block there, keeps it current
there and removes the project's copy, leaving the rest of `AGENTS.md`. A run that would change nothing
writes nothing ([Agents file](docs/agents-file.md)). A project that uses one harness drops the other
harness's `install` line and `install-agents-file` line.

Under claude the set is a plugin: invoke its agents and commands as `adjagent:<name>`, and run
`/reload-plugins` (or restart Claude Code) after an install for new definitions to register.

Justfile:

```just
AGENTS_VER := "v0.15.0"
AGENTS_VENV := ".venv"
# installs the pinned adjagent into the project's venv, then installs the agent set
agents:
  [ -x "{{AGENTS_VENV}}/bin/python" ] || python3 -m venv "{{AGENTS_VENV}}"
  [ "v$("{{AGENTS_VENV}}/bin/adjagent" --version 2>/dev/null)" = "{{AGENTS_VER}}" ] || "{{AGENTS_VENV}}/bin/python" -m pip install "git+https://github.com/benn-herrera/adjagent@{{AGENTS_VER}}"
  "{{AGENTS_VENV}}/bin/adjagent" install . --harness=claude
  "{{AGENTS_VENV}}/bin/adjagent" install . --harness=opencode
  "{{AGENTS_VENV}}/bin/adjagent" install-agents-file ~/.claude
  "{{AGENTS_VENV}}/bin/adjagent" install-agents-file ~/.config/opencode
```

Makefile:

```make
AGENTS_VER := v0.15.0
AGENTS_VENV := .venv

.PHONY: agents
agents:
	[ -x "$(AGENTS_VENV)/bin/python" ] || python3 -m venv "$(AGENTS_VENV)"
	[ "v$$("$(AGENTS_VENV)/bin/adjagent" --version 2>/dev/null)" = "$(AGENTS_VER)" ] || "$(AGENTS_VENV)/bin/python" -m pip install "git+https://github.com/benn-herrera/adjagent@$(AGENTS_VER)"
	"$(AGENTS_VENV)/bin/adjagent" install . --harness=claude
	"$(AGENTS_VENV)/bin/adjagent" install . --harness=opencode
	"$(AGENTS_VENV)/bin/adjagent" install-agents-file ~/.claude
	"$(AGENTS_VENV)/bin/adjagent" install-agents-file ~/.config/opencode
```

Run `just agents` or `make agents`. The recipe never recreates or clears an existing `.venv`, and runs
pip only when the venv's adjagent is not the pinned version. Then add the installed trees to the
project's `.gitignore`:

```text
.claude/
.opencode/
```

The project's `AGENTS.md` and `CLAUDE.md` are not installed trees: the install may write them (above),
so decide whether to commit them.

The `.venv/` entry a Python project conventionally ignores covers the venv; add it if the project
ignores nothing there. The docdicer tools' own venv needs no entry: its `.gitignore` is installed
with it.

To update, change `AGENTS_VER` to the new release tag and run the recipe again. Everything it
installs is documented in the [install reference](docs/install-reference.md).

To add the knowledge-base set, add `--with-kb` to the two `install .` lines and install kbase first ([Knowledge base](docs/knowledge-base.md)).

## Previewing and re-installing

`--dry-run` prints what an install would create, change and remove, grouped and relative to the
project root (a path outside it prints absolute), and writes nothing:

```sh
.venv/bin/adjagent install . --harness=claude --dry-run
```

An install that would change nothing says so, exits 0 and touches nothing. Rules and sample output:
[Install reference](docs/install-reference.md#re-installing-and---dry-run).

## Running adjagent by hand

To run `adjagent` yourself, for a one-off install or a preview, install it with pipx or into a venv
of your own. A bare `pip install` outside a venv is refused on Homebrew and most distro Pythons
(`externally-managed-environment`), and Apple's `/usr/bin/python3` puts the command in
`~/Library/Python/3.9/bin`, which is not on `PATH`.

```sh
pipx install "git+https://github.com/benn-herrera/adjagent@v0.15.0"
pipx ensurepath   # puts pipx's bin directory on PATH; open a new shell afterwards
adjagent --help
adjagent install ~/projects/foo
```

Or, with a venv:

```sh
python3 -m venv ~/.venvs/adjagent
~/.venvs/adjagent/bin/pip install "git+https://github.com/benn-herrera/adjagent@v0.15.0"
~/.venvs/adjagent/bin/adjagent install ~/projects/foo
```

A project's own pin belongs in its runner recipe, above. Cloning this repository and running
`just install ~/projects/foo` from its root is the same install ([Development](docs/development.md)).

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

The mage plugin is published as a release: a tarball and its detached signature. The tarball holds the
plugin only; the plugin's `kbase` MCP command is the bare `kbase`, so you install kbase yourself
([Knowledge base](docs/knowledge-base.md#requirements)). Contract:
[SPEC](PROJECT_DOCS/SPEC/mage-plugin-distribution.md).

1. Download `adjagent-mage-v<version>.tgz` from the release `v<version>` of
   [benn-herrera/adjagent](https://github.com/benn-herrera/adjagent/releases), and optionally its
   `adjagent-mage-v<version>.tgz.asc`.
2. Optionally check the tarball against the signature. Fetch the release signer's public key over WKD
   (the developer's key is at <https://keyoxide.org/wkd/benn@bennherrera.dev>), then verify:

   ```sh
   gpg --auto-key-locate wkd --locate-external-keys benn@bennherrera.dev
   gpg --verify adjagent-mage-v<version>.tgz.asc adjagent-mage-v<version>.tgz
   ```

3. Unpack it into Mage's skills directory, removing any earlier copy first:

   ```sh
   rm -rf ~/Mage/Skills/adjagent
   tar -xzf adjagent-mage-v<version>.tgz -C ~/Mage/Skills/
   ```

   The tarball has one top-level `adjagent/` directory, so this leaves `~/Mage/Skills/adjagent`.
4. Install kbase if you have not. Native Windows is unsupported for the kb set, which a mage plugin
   always carries.
5. Restart Mage so it starts the plugin's `kbase` MCP server; the plugin's entry finds `kbase` on
   `PATH`. Do the same after installing or upgrading kbase while Mage is running.

## More documentation

- [Install reference](docs/install-reference.md): target and harness resolution, user-level installs,
  what an install writes, refusals.
- [Guardrail](docs/guardrail.md): the hooks that block shell writes behind the edit tools.
- [Harness agents file](docs/agents-file.md): the operator-level working rules.
- [Model tuning](docs/model-tuning.md): families, overlay anchors and tier maps.
- [Definition sets](docs/definition-sets.md): the agents, commands and skills.
- [Knowledge base](docs/knowledge-base.md): the kb set and its toolchain.
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
build and documentation checks, or by the optional kb set; none is bundled.

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
  kb set; a host program you install ([Knowledge base](docs/knowledge-base.md#requirements)).
- **Graphviz** `dot` (Graphviz authors, Eclipse Public License; the installed 16.1.0's `COPYING` is
  version 2.0): optional, renders the kb set's claim graph diagrams as SVG; a host program you
  install.
