# ARCHITECTURE – Adjagent

How the generation system, and the agent/command set it ships, are built to satisfy SPEC.md. Cites
SPEC's requirements rather than restating them.

## Repo Layout

```
kb_tools/               shipped package — portable KB toolchain — stdlib-only python package + kb_cmd/ query package, its contract docs, tests, runner-include fragments; installed to .claude/agents/kb_tools/, and locates its harness directory from its own path (kb_tools/install_location.py) (SHIPPED_PACKAGES, adjagent/install.py)
liaison_tools/          shipped package — shell/python helpers shared by guest-liaison.md and mad-guest-liaison.md; installed to .claude/agents/liaison_tools/
rendered/               gitignored build product — this repo's own render tree, the conventional target for inspecting or PR-diffing a render (justfile RENDERED); created on demand
adjagent/               the generator package, run as python3 -m adjagent — definitions as Python values rendered into a named output root; the package docstring lists its modules
devtools/               repository-maintenance tooling — project space, never installed; imported from the repository root as `devtools.*`
  dupe_sweep/           the duplication sweep, run as `python3 -m devtools.dupe_sweep` — enumerates one-idea-two-places candidates over kb_tools/ (justfile `sweep-python`)
    __init__.py         package docstring (what the sweep is for, its passes, candidates not verdicts)
    __main__.py         the `-m` entry
    corpus.py           the corpus read from git, never a directory walk; the sweep's error
    clustering.py       units, containment scoring, shingle-blocked clustering, union-find grouping
    normalization.py    text to lower-cased words, markers dropped
    python_corpus.py    what the python pass reads: kb_tools/ less tests/ and _vendor/, parsed
    shapes.py           one concept, two implementations: function structural shapes
    constants.py        one constant, two definitions: module-level literals and their candidates
    doc_sentences.py    one rule, two homes: docstring and comment sentences
    report.py           headers, candidate lists, the file-pair tally
    passes.py           the `python` pass and its defaults
    cli.py              argparse surface and dispatch
  tests/                the dupe_sweep test suite, including its import-structure test (`just test dupe_sweep`)
tests/                  the root test suite, `adjagent` and the repository-wide checks, run as the `adjagent` surface (`just test adjagent`) — project space, never installed
```

The two deployed surfaces are absent from this listing because they are absent from the repository
(SPEC.md, Deployed Surfaces).

## Install Consumption Model

`just install` wraps `python3 -m adjagent install <project>/<subdir>`: it renders every
definition, replaces each shipped package's destination whole with a copy that carries a one-line
`!INSTALLED!` banner, and writes the renders over what is there (`adjagent/install.py`).
Afterwards it removes each file under `agents/` or `commands/` that this run did not write and whose
frontmatter opens with a `!GENERATED!` banner. There is no hash, backup or refusal; the consumer's
git is the record.

## Template System

Definitions compose in Python: one module per definition under `adjagent/definitions/` holding
imports, string constants and `DEFINITIONS`, shared text as constants in `adjagent/clauses.py`,
render-time holes filled once by `render.filled_body`. The package and module docstrings hold the
mechanism until this section is rewritten.

## Banner and Backup Mechanism

A rendered file carries two frontmatter banner lines: `# !GENERATED! from <definition module>` with
the edit rule, and `!TUNING!`. A copied package file of a `#`-comment type carries one
`# !INSTALLED! from <source>` line; nothing carries a hash, and nothing is backed up but the agents
file's rolling `backup.<name>`.

## Verification, and Why There Is No Verification Verb

There is no `check` verb, and adding one back is a decision to be argued rather than an omission to
be filled. A render is the only thing that knows what a template produces, so a verb that
re-rendered a tree and compared would be asking the producer whether it agrees with itself: a
rendering defect reaches both sides and the report reads clean. What such a verb could genuinely
detect — staleness of a build product — a free re-render fixes.

`render-diff` replaces every `!GENERATED!` and `!INSTALLED!` banner with one constant line before
comparing, and `tests/test_adjagent.py` holds the package's properties and source rules where
`tests/test_gen_defs.py` did. Every verb exits 0 on success and 2 on a refusal; there is no verdict
code.

## Sanctioned Invocation

`just install`, `just render` and `just install-agents-file <dir> [harness]` reach
`python3 -m adjagent` (`render` through `install` and the stable private
`render-agents-file HARNESS OUT` recipe). The agents-file install replaces the span from the begin
marker line to the end marker line, keeps every other byte, and writes a project's directives to
`AGENTS.md` with a claude `CLAUDE.md` holding `@AGENTS.md`; it follows a destination that is a lone
`@<path>` one hop, and refuses while `adjagent/` has uncommitted changes (`adjagent/agents_file.py`).

## Subsystem Map

Every entry below is rendered from the definition module under `adjagent/definitions/` named for its
output path; a chunk named here is the `clauses.py` constant of the same name in UPPER_SNAKE, and an
overlay anchor is spelled `fam-<key>`.

- **Coder family** — generalist-coder, language coders (c, cpp, go, python, rust), shell-dsl-coder,
  platform experts (android/ios/linux/macos/web/windows-app-expert, linux-kernel-driver-expert),
  architect, and — sharing the coding-review domain — security-reviewer, tech-writer, and
  tech-writer-reviewer.
- **MAD set + `agents/mad/`** — mad-review-referee, mad-design-referee, mad-alignment-assessor, the
  four model-pinned participants (mad-participant-fable/opus/sonnet/haiku), and mad-guest-liaison
  sit directly under `agents/` as dispatchable definitions. What the set reads rather than
  dispatches goes into `agents/mad/`, outside the dispatch namespace:
  `agents/mad/participant-contract.md` (the body the four participants share and a guest model
  receives as its system prompt), and the design referee's own methodology topic set, read at
  dispatch, `agents/mad/design-topics/`. A topic renders bannered like any other output, and a
  referee writes the run's own banner-free copy of it into the run directory before dispatching —
  one strip at the point the brief is assembled, so no seat reads generator metadata and a
  banner-format change reaches one chunk (`mad-topic-transport`).
- **kb set + kb_tools** — kb-claim-scorer, kb-maintainer, kb-docent. The `kb-orientation` chunk
  carrying the system model (two graphs, the leaf/summary contract, authored-vs-derived metadata,
  the cast) with a per-definition `role=` clause goes to the two seats that work a finished KB —
  kb-docent and kb-maintainer; the build seat, kb-claim-scorer, is told what its own job needs and
  reaches the rest through its dispatch. All three are project-portable — per-project facts live in
  the consuming project's `kb-root/AGENTS.md`, under every harness. `kb_tools/` is the toolchain the
  set drives: tools self-anchor by walking up from cwd to `.git` and requiring `kb-root/` beside it,
  read which harness directory they are installed under (and so the scratch directory, PYTHONPATH
  entry and include line they spell) off their own path, detect the consumer's runner for
  remediation hints, and install their runner targets via
  `python3 -m kb_tools.kb_util install-targets` (one non-fatal include line pulling `runner-snippets/kb.mk` or `kb.just`);
  the consumer surface is `kb-verify`/`kb-refresh`/`kb-stats` — `kb-`-prefixed so it cannot collide
  with a consuming project's own targets — and the tool self-tests run under this repo's
  `just test`.
- **Liaisons + liaison_tools** — guest-liaison.md (general-purpose) and mad-guest-liaison.md
  (MAD-only) share `liaison_tools/`'s helpers (`post-openai.py`, `msg-util.py`) for the wire
  protocol and the messages-file format; each strips a definition's frontmatter for itself with a
  `sed` range, the operation being one line. `relay-driver.py` — the corpus-relay eval instrument —
  composes those same helpers (`post-openai.py` as sole transport, `msg-util.py` as sole
  messages-file mutator) into a scripted READ/LIST/GREP retrieval-eval loop.
- **Specialists** — applied-mathematician, biz-dev-strategist, economic-historian, literature-scout,
  marketing-comms-expert, ml-engineer, prompt-engineer, prose-architect, theoretical-economist:
  single-purpose, invoked directly rather than as part of a coding or MAD pipeline.
  applied-mathematician carries the `fam.ask-vs-stipulate` overlay anchor; `fam.gap-aversion` sits
  on kb-claim-scorer.
