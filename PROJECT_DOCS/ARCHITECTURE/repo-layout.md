## Repo Layout

```
PROJECT_DOCS/           the contract trees — THESIS, SPEC, ARCHITECTURE, CONVENTIONS — as small leaf files, one `entry-point.md` per volume; the root `THESIS.md`, `SPEC.md`, `ARCHITECTURE.md` and `CONVENTIONS.md` are pointers to them, not sources; checked by `just check-links`
agent-sandboxing/       setup for running a coding agent as an unprivileged local user — project space, never installed
kb-tools/               shipped package, delivered only by a kb install — the runner-snippets/ fragments (kb.just, kb.mk) an install writes the consumer's include line for, which run `kbase` from `PATH`; nothing importable; installed under <harness-dir>/skills/kbase/kb-tools/, inside the kbase skill's own directory (KB_TOOLS_PACKAGE, adjagent/install.py)
dist/                   gitignored build product — what `just mage-dist` writes: the mage plugin tarball and its detached signature, plus `stage/` while a build runs, removed when it ends (`DIST_DIR`, devtools/scripts/mage-dist.sh); created on demand
rendered/               gitignored build product — this repo's own render tree, one slot per render, and the three `reference*` slots `render-diff` compares against (justfile RENDERED); created on demand
adjagent/               the generator package, run as python3 -m adjagent — definitions as Python values rendered into a named output root; the package docstring lists its modules
  harnesses/resources/  one directory per harness, named for it — the files that harness ships into its project harness directory, copied into ROOT as they stand and never rendered (HARNESS_RESOURCES_SOURCE, adjagent/install.py); `opencode/plugins/guardrail.ts` and `claude/hooks/guardrail.pl` today, and no `__init__.py`, so `load` still reads one harness per module; mage ships none
devtools/               repository-maintenance tooling — project space, never installed; imported from the repository root as `devtools.*`
  scripts/              the shell scripts behind the justfile recipes (justfile)
  render_diff.py        the text comparison of two rendered slots (justfile `render-diff`); reads rendered output only and never imports the generator
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
tests/                  the root test suite, `adjagent` and the repository-wide checks, run as the `adjagent` surface (`just test adjagent`) — project space, never installed
  stubs/                the stub `gpg` that `tests/test_mage_dist.py` puts first on `PATH` — no key, no real keyring — and which answers only the signing call
```

The three deployed surfaces are absent from this listing because they are absent from the repository
(SPEC.md, Deployed Surfaces).

