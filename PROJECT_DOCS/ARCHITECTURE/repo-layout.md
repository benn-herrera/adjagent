## Repo Layout

```
PROJECT_DOCS/           the contract trees — THESIS, SPEC, ARCHITECTURE, CONVENTIONS — as small leaf files, one `entry-point.md` per volume; the root `THESIS.md`, `SPEC.md`, `ARCHITECTURE.md` and `CONVENTIONS.md` are pointers to them, not sources; checked by `just check-links`
docs/                   the human-facing pages README links to — installing, mage plugin release, install reference, guardrail, agents file, model tuning, definition sets, knowledge base, development — indexed by `docs/index.md`, with `docs/images/` holding the README's screenshot; checked by `just check-links`
agent-sandboxing/       setup for running a coding agent as an unprivileged local user — never installed
pyproject.toml          the package's build configuration — setuptools, the version read from `adjagent.__version__`, the package-data globs, the `adjagent` console script (Packaging)
dist/                   gitignored build product — what `just mage-dist` writes: the mage plugin tarball and its detached signature for each plugin, plus `stage/` while a build runs, removed when it ends (`DIST_DIR`, devtools/scripts/mage-dist.sh); and what `just build` writes: the wheel and sdist; created on demand
rendered/               gitignored build product — this repo's own rendered tree, one slot per rendering, each holding one slot project per plugin (`rendered/<slug>/devpro/`, `rendered/<slug>/kbase/`), and the four `reference*` slots, one per harness plus gemma, `render-diff` compares against (justfile RENDERED); created on demand
adjagent/               the generator package, run as python3 -m adjagent — definitions as Python values rendered into a named output root; the package docstring lists its modules
  plugin.py             the `Plugin` type: a name and either the definition names it ships or the ones it leaves out, with `ships(name)` (Rendering, Harnesses and families)
  plugins/              one module per plugin, each defining `PLUGIN` and nothing else — `devpro.py` and `kbase.py`; which definitions each ships is SPEC.md, Deployed Surfaces, Plugins (CONVENTIONS.md, Plugin membership has one home)
  kb-tools/             shipped package, owned by `kbase` and so delivered only by the kbase plugin — the runner snippets (kb.just, kb.mk) an install writes the consuming project's include line for, which run `kbase` from `PATH`; nothing importable; installed under <install-dir>/skills/kbase/kb-tools/, inside the kbase skill's own directory (KB_TOOLS_DIR, adjagent/install_base.py)
  preflight.py          the install preflight — the unchanged install run into a scratch copy of the paths it manages and compared with the real paths, behind the up-to-date report and `--dry-run` (Install, Renders and copies)
  docdicer-tools/       shipped package, owned by `docdicer` and so delivered by every project install of devpro — the `docdicer` bash launcher, which builds and runs a docdicer venv beside itself, a `.gitignore` holding `.venv/`, and the runner snippets (docdicer.just, docdicer.mk) that no install writes an include line for; nothing importable; installed under <install-dir>/skills/docdicer/tools/, inside the docdicer skill's own directory (DOCDICER_TOOLS_PACKAGE, adjagent/install.py)
  development-tools/    shipped package, owned by `development` and so delivered by every project install of either plugin — `cold-read.sh`, a bash script that runs one agent on one brief with no tools; nothing importable; installed under <install-dir>/skills/development/scripts/, inside the development skill's own directory (DEVELOPMENT_SCRIPTS_PACKAGE, adjagent/install.py)
  harnesses/resources/  one directory per harness, named for it — the harness resources that harness ships, copied into the plugin's install directory as they stand and never rendered (HARNESS_RESOURCES_SOURCE, adjagent/install.py); `opencode/index.ts` (the plugin entry) and `opencode/guardrail.ts`, and `claude/hooks/guardrail.pl`, and no `__init__.py`, so `load` still reads one harness per module; mage ships none
devtools/               repository-maintenance tooling — never installed; imported from the adjagent project root as `devtools.*`
  scripts/              the shell scripts behind the justfile recipes (justfile)
  render_diff.py        the text comparison of two rendered slots (justfile `render-diff`); reads rendered output only and never imports the generator
  clause_join_sites.py  the list of definition-body units that join a `clauses.*` interpolation to the module's own text (justfile `clause-join-sites`); splits units with `render_diff.py`'s line classification, `line_kinds`
  dupe_sweep/           the duplication sweep, run as `python3 -m devtools.dupe_sweep` — enumerates one-idea-two-places candidates over the owned python trees (justfile `sweep-python`)
    __init__.py         package docstring (what the sweep is for, its passes, candidates not verdicts)
    __main__.py         the `-m` entry
    corpus.py           the corpus read from git, never a directory walk; the sweep's error
    clustering.py       units, containment scoring, shingle-blocked clustering, union-find grouping
    normalization.py    text to lower-cased words, `@!…!@` placeholders dropped
    python_corpus.py    what the python pass reads: `CODE_PREFIXES` — adjagent, devtools — less `CODE_UNSWEPT`, parsed
    shapes.py           one concept, two implementations: function structural shapes
    constants.py        one constant, two definitions: module-level literals and their candidates
    doc_sentences.py    one rule, two homes: docstring and comment sentences
    report.py           headers, candidate lists, the file-pair tally
    passes.py           the `python` pass and its defaults
    cli.py              argparse surface and dispatch
  tests/                the dupe_sweep test suite, including its import-structure test (`just test dupe_sweep`)
tests/                  the root test suite, `adjagent` and the repository-wide checks, run as the `adjagent` test surface (`just test adjagent`) — never installed
  stubs/                the stub `gpg` that `tests/test_mage_dist.py` puts first on `PATH` — no key, no real keyring — and which answers only the signing call
```

The three deployed surfaces are absent from this listing: no rendered definition is checked in, so
there is no copy to serve from, compare against or drift from; each is rendered to order into the
output root an invocation names.

