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

The test suite needs `bun` and `perl` on `PATH`. The guardrail parity
test (`tests/test_guardrail.py`) runs one case table through both guardrails, each case under every
guardrail its `harness` field allows, and fails, not skips, without `bun`. The two guardrails change
together ([CONVENTIONS](../PROJECT_DOCS/CONVENTIONS/code-definitions-and-install/guardrails-change-together.md)).

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
- `just render [slug]` renders the full install product, kb set included, into `rendered/<slug>/`
  (slug defaults to `latest`), plus the harness agents file under `rendered/<slug>/harness/<name>/`:
  `CLAUDE.md` by default, or another harness's with `--harness=NAME`. Under mage it lands at the slot
  root instead, `rendered/<slug>/CLAUDE.md` beside `.mcp.json`, with no `harness/` directory and no
  `Makefile`: the slot is installed with `--subdir=`, so the plugin's root is the slot itself. A slug
  starting with `reference` is refused.
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
adjagent/                 the generator and every definition, run as `python3 -m adjagent`
  clauses.py              shared text: named string constants, small functions for slotted text
  definitions/            one module per definition, or per set that shares text and ships together
  harnesses/              one module per harness (claude, mage, opencode), each defining HARNESS
    resources/            one directory per harness: the files it ships, copied into the install's
                          harness directory as they stand (opencode/plugins/guardrail.ts,
                          claude/hooks/guardrail.pl)
  families/               one module per model family, each defining FAMILY
  kb-tools/               shipped KB runner fragments (runner-snippets/kb.just, kb.mk), delivered by
                          a kb install only as skills/kbase/kb-tools/
  docdicer-tools/         the docdicer launcher script, its .gitignore and runner fragments
                          (runner-snippets/docdicer.just, docdicer.mk), delivered by every project
                          install as skills/docdicer/tools/
pyproject.toml            the package's build configuration: setuptools, the version read from
                          `adjagent.__version__`, the console script `adjagent`
docs/                     the pages the README links to
dist/                     gitignored: what `just mage-dist` and `just build` write
devtools/                 repository-maintenance tooling; render_diff.py compares two rendered slots,
                          scripts/ holds the shell scripts behind the justfile recipes
agent-sandboxing/         setup for running a coding agent as an unprivileged local user
PROJECT_DOCS/             the contract trees (THESIS, SPEC, ARCHITECTURE, CONVENTIONS), one
                          `entry-point.md` per volume; the root `*.md` files are pointers to them
rendered/                 gitignored: `just render [slug]` puts a render here per slot
ROADMAP_PLANS/            tracked home for planned work not yet ready to execute
```

`agents/`, `commands/` and `skills/` are not directories in this repository. They are the three
deployed surfaces of the product, produced into `<project>/.claude/` by an install or into
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
text with holes, read top to bottom as the file it renders.

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

`just mage-dist` writes two files to `dist/`: `adjagent-mage-v<version>.tgz` and its detached `.asc`
signature. What a consumer does with them is in the [README](../README.md#mage-plugin-release); the
contract is [SPEC](../PROJECT_DOCS/SPEC/mage-plugin-distribution.md).

The build needs `gpg` holding your signing key as its default secret key; it signs with that key and
pins no fingerprint, so a rotated key needs no code change. It removes the previous outputs and its
`stage/`, and builds from the working tree as it stands, with no git check. A build that fails,
signing included, leaves neither output and no `stage/`.

To release:

1. Bump `__version__` in `adjagent/__init__.py`, update the `v<version>` examples in README, and
   commit them ([CONVENTIONS](../PROJECT_DOCS/CONVENTIONS/code-definitions-and-install/version-has-one-home.md)).
2. `just test`.
3. `just mage-dist`.
4. `just tag`, which creates the local signed tag `v<version>` and pushes nothing; push it yourself.
   It needs a gpg secret key and a TTY.
5. Create the release `v<version>` on GitHub and upload the two files. The recipe uploads, tags and
   pushes nothing.
6. Smoke check: from an empty scratch directory, download the uploaded tarball and its `.asc` from
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
definition's module (Working in this repo). A rendered definition carries a two-line banner inside its
frontmatter: a generated-from line naming its definition module and stating that the file is not for
local edit, and a tuning line recording the family, seat, tier map and harness it was rendered for. A
skill's supporting file has no frontmatter, so it carries the same two lines as HTML comments on its first
two lines. There is no content hash; a project that tracks the rendered output sees drift in its
`git diff`, and one that does not loses any local edit to the next install.
