# Development

For working on this repository itself: the generator, its definitions and the shipped tool packages.
To install the product into a project, see the [README](../README.md).

## Build and test

Beyond the install requirements, this repository needs:

- `just` 1.27.0 or later, the first release with the `[doc]` recipe attribute the justfile uses
  ([just changelog](https://github.com/casey/just/blob/master/CHANGELOG.md), 1.27.0).
- `bash`, the shell the justfile sets for its recipes.
- The network on the first `just test`, which provisions `.venv`; docdicer installs from its git tag,
  so `git` is needed there too.

The test suite needs `bun`, `perl` and `kbase` (0.11.0 or later) on `PATH`. The kbase surface test
(`tests/test_kbase_surface.py`) needs `kbase` and fails, not skips, without it;
[Knowledge base](knowledge-base.md#requirements) gives the install. The guardrail parity test
(`tests/test_guardrail.py`) runs one case table through both guardrails, each case under every
guardrail its `harness` field allows, and fails, not skips, without `bun`. The two guardrails change
together ([CONVENTIONS](../PROJECT_DOCS/CONVENTIONS/code-definitions-and-install/guardrails-change-together.md)).
The opencode plugin entry (`tests/test_opencode_entry.py`) runs under `bun` the same way, against a
stub plugin context, so it fails, not skips, without it. The plugin membership and install cases are
in `tests/test_plugins.py` and `tests/test_adjagent_install.py`.

```sh
git clone https://github.com/benn-herrera/adjagent && cd adjagent
just test
```

`just test` runs the full tooling test suite: the `adjagent`, `dupe_sweep`, `docs` and `wheel`
surfaces, auto-provisioning a `.venv`. The `docs` surface is `just check-links`, which checks every
relative link and anchor in `PROJECT_DOCS/`, `docs/` and the top-level `*.md` files. The `wheel`
surface is `just check-wheel`. The `.venv` prefers `/usr/bin/python3` on macOS, the Xcode
command-line tools' Python 3.9.6, so `just test` there checks the Python 3.9 floor; elsewhere it runs
on whatever `python3` is installed. Using the repository directly does not require Python 3.9.

Other targets:

- `just test-changed [base]` is the edit gate, run after a change. It runs only the surfaces the uncommitted
  tree (plus, given `base`, the commits since it) touches, and says which paths chose each.
- `just render [slug]` renders the full install product of both plugins into `rendered/<slug>/`
  (slug defaults to `latest`), one slot project per plugin: `rendered/<slug>/devpro/` and
  `rendered/<slug>/kbase/`. Each slot project holds the plugin's harness agents file under
  `<plugin>/harness/<name>/`: `CLAUDE.md` by default, or another harness's with `--harness=NAME`.
  Under mage it lands at the slot project instead, `<plugin>/CLAUDE.md` (beside `.mcp.json` in kbase),
  with no `harness/` directory and no `Makefile`: each plugin is installed with `--subdir=`, so the
  install directory is the slot project itself. Under claude the slot project is the harness directory
  and holds the plugin at `<plugin>/skills/<plugin>/`, with `.claude-plugin/plugin.json` inside it (and
  `.mcp.json` in kbase) and no `agents/` at the slot project. Under opencode the plugin directory is
  `<plugin>/plugins/<plugin>/`. A claude or opencode slot project also holds the project's `AGENTS.md`
  and, under claude, the `CLAUDE.md` redirect (`@AGENTS.md`). A slug starting with `reference` is
  refused.
- A slot renders under a scratch `HOME` that is empty and removed afterward, so the install finds no
  global agents file and writes the block into the slot's `AGENTS.md`, never into the real
  `~/.claude` or `~/.config/opencode`. `just check-wheel` runs under a scratch home the same way.
- `just render-diff [a] [b]` compares two slots (reference-claude against latest by default) by text, with
  each file's banner replaced by one constant line, and reports differences without failing on them.
- `just retake-reference` re-takes the baseline slots `render-diff` compares against. Run it only
  after a content change is accepted.
- `just build` builds the wheel and sdist into `dist/` with the `.venv`'s setuptools, offline and with
  no git check. `just check-wheel [python]` builds, then installs the wheel into a throwaway venv and
  checks that its package data equals the tree and that the installed `adjagent` runs and installs the
  same product as the checkout.

## Repository layout

```text
adjagent/                 the generator and every definition, run from a checkout as `PYTHONPATH=<clone> python3 -m adjagent`
  clauses.py              shared text: named string constants, small functions for slotted text
  definitions/            one module per definition, or per set that shares text and ships together
  harnesses/              one module per harness (claude, mage, opencode), each defining HARNESS
    resources/            one directory per harness: the files it ships, copied as they stand into
                          the install directory (opencode/index.ts and opencode/guardrail.ts,
                          claude/hooks/guardrail.pl); the install directory is where the install
                          writes: the plugin's directory under claude and opencode, the
                          harness directory under mage
  families/               one module per model family, each defining FAMILY
  plugins/                one module per plugin, each defining PLUGIN: devpro and kbase; SPEC.md,
                          Deployed Surfaces, Plugins lists each plugin's members
  kb-tools/               shipped KB runner fragments (runner-snippets/kb.just, kb.mk), delivered with
                          the kbase skill, so by the kbase plugin only, as skills/kbase/kb-tools/
  docdicer-tools/         the docdicer launcher script, its .gitignore and runner fragments
                          (runner-snippets/docdicer.just, docdicer.mk), delivered with the docdicer
                          skill, so by devpro only, as skills/docdicer/tools/
  development-tools/      the cold-read.sh script, delivered with the development skill, so by both
                          plugins, as skills/development/scripts/
pyproject.toml            the package's build configuration: setuptools, the version read from
                          `adjagent.__version__`, the console script `adjagent`
docs/                     the pages the README links to; images/ holds the README's screenshot
dist/                     gitignored: what `just mage-dist` and `just build` write
devtools/                 repository-maintenance tooling; render_diff.py compares two rendered slots,
                          scripts/ holds the shell scripts behind the justfile recipes
agent-sandboxing/         setup for running a coding agent as an unprivileged local user
PROJECT_DOCS/             the contract trees (THESIS, SPEC, ARCHITECTURE, CONVENTIONS), one
                          `entry-point.md` per volume; the root `*.md` files are pointers to them
rendered/                 gitignored: `just render [slug]` puts a render here per slot
ROADMAP_PLANS/            tracked home for parked work: designs and plans not under way
```

`agents/`, `commands/` and `skills/` are not directories in this repository. They are the three
deployed surfaces of the product, produced into `<project>/.claude/skills/<plugin>/` by
an install or into
`rendered/` by `just render`. A definition module registers by existing in `definitions/`; its `kind`
and `folder` decide where it lands, and a skill's `files` add the supporting files beneath its own
directory. The full layout is in
[ARCHITECTURE](../PROJECT_DOCS/ARCHITECTURE/repo-layout.md).

Project documents, one tree each: [THESIS](../PROJECT_DOCS/entry-point.md) (purpose and intent),
[SPEC](../PROJECT_DOCS/SPEC/entry-point.md) (observable contract),
[ARCHITECTURE](../PROJECT_DOCS/ARCHITECTURE/entry-point.md) (how the mechanism works) and
[CONVENTIONS](../PROJECT_DOCS/CONVENTIONS/entry-point.md) (house rules). `ROADMAP.md` tracks open
follow-on work, outside that set.

## Working in this repo

A definition is `adjagent/definitions/<name>.py`: a `DEFINITIONS` tuple whose `body` is the rendered
text with placeholders, read top to bottom as the file it renders.

- A definition's own prose is in its module. Shared text is a named constant in
  `adjagent/clauses.py`, or a private constant of a group module whose definitions ship together.
- To change what shared text says for every definition, edit the constant; to change it for one, edit
  that definition's module.
- To see what a change does, run `just render`, then `just render-diff`. An unknown placeholder fails
  at render; a definition module holding anything but imports, string constants and `DEFINITIONS`
  fails the suite.
- The edit gate is `just test-changed`; the checkpoint gate is `just test`.

How to add a definition: [CONVENTIONS](../PROJECT_DOCS/CONVENTIONS/adding-definitions/index.md).

## Releasing the mage plugin

`just mage-dist` writes four files to `dist/`: for each plugin `adjagent-mage-<plugin>-v<version>.tgz`
and its detached `.asc` signature. What a consumer does with them is in the
[Mage plugin release](mage-release.md); the contract is [SPEC](../PROJECT_DOCS/SPEC/mage-release.md).

The build needs `gpg` holding your signing key as its default secret key; it signs with that key and
pins no fingerprint, so a rotated key needs no code change. It removes the previous outputs and its
`stage/`, and builds from the working tree as it stands, with no git check. A build that fails,
signing included, leaves no output of the version for either plugin and no `stage/`.

To release:

1. Bump `__version__` in `adjagent/__init__.py`, update the `v<version>` examples in README and `docs/installing.md`, and
   commit them ([CONVENTIONS](../PROJECT_DOCS/CONVENTIONS/code-definitions-and-install/version-has-one-home.md)).
2. `just test`.
3. `just mage-dist`.
4. `just tag`, which creates the local signed tag `v<version>` and pushes nothing; push it yourself.
   It needs a gpg secret key and a TTY.
5. Create the release `v<version>` on GitHub and upload the four files. The recipe uploads, tags and
   pushes nothing.
6. Smoke check: from an empty scratch directory, download one uploaded tarball and its `.asc` from
   the release, `gpg --verify` the one against the other, and list the tarball (`tar -tzf`).

## Authoring a family

A family is a module under `adjagent/families/` defining `FAMILY`; the fields, and how tiers, member
overrides and `--model-tier-map` interact, are in the docstring of `adjagent/family.py`.

The mechanism is a response to a real phenomenon: agent definitions tend to accumulate defensive
language that's keyed to the *specific* model they were tested against. Defensive clauses that
*protect* one model can *smother* another: same clause, opposite effect, no error event. (Example:
probe data from 2026-04-29 showed Gemma 4 31B-it silently filling axiom gaps with textbook
conventions, while Gemini 3.1 Pro spontaneously surfaced the same gaps. A "do not fill gaps" clause
helps the first model and slows the second.)

The operating rule when porting an agent definition to a new model: **strip first, observe, patch.**
Run the base definitions with the new model on a known-shape probe set. Watch for failure modes; only
then author an anchor and an overlay targeted at the failure modes you actually observed. Anchors are
never pre-sprinkled speculatively. Heavy scaffolding hides the model's true tendencies; you can't
engineer for failure modes you never see.

When adding defensive clauses, record *what tendency the clause was added to correct, against which
model*. Without that record, future maintainers can't distinguish "still load-bearing" from "residue
from a model we don't use anymore." Comment overlays like code: not what the overlay says, but why and
against which observed behavior it was added.

The earlier delivery vehicle, a parallel per-model definition file (for example
`applied-mathematician-strict.md`, a gap-aversion variant built for running the math agent on Gemma 4),
was retired 2026-08-21; the anchor mechanism replaces whole-definition forks.

## Generated definitions

Every definition in [Definition sets](definition-sets.md) is **generated**. There are no
hand-maintained definitions and nothing to edit directly in a rendered tree; the source is the
definition's module (Working in this repo). Under claude and mage a rendered definition carries a
two-line banner inside its frontmatter: a generated-from line naming its definition module and
stating that the file is not for local edit, and a tuning line recording the family, tier, tier map
and harness it was rendered for. A skill's supporting file has no frontmatter, so it carries the same
two lines as HTML comments on its first two lines, and so does every rendered file under opencode,
whose metadata is in the plugin's `registry.json`. There is no content hash; a project that tracks the rendered output sees drift in its
`git diff`, and one that does not loses any local edit to the next install.
