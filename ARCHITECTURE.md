# ARCHITECTURE – Adjagent

How the generation system, and the agent/command set it ships, are built to satisfy SPEC.md. Cites
SPEC's requirements rather than restating them.

## Repo Layout

```
kb_tools/               shipped package — portable KB toolchain — stdlib-only python package + kb_cmd/ query package, its contract docs, tests, runner-include fragments; installed to .claude/agents/kb_tools/, and locates its harness directory from its own path (kb_tools/install_location.py) (SHIPPED_PACKAGES, adjagent/install.py)
liaison_tools/          shipped package — shell/python helpers shared by guest-liaison.md and mad-guest-liaison.md; installed to .claude/agents/liaison_tools/
rendered/               gitignored build product — this repo's own render tree, one slot per render, and the three `reference*` slots `render-diff` compares against (justfile RENDERED); created on demand
adjagent/               the generator package, run as python3 -m adjagent — definitions as Python values rendered into a named output root; the package docstring lists its modules
devtools/               repository-maintenance tooling — project space, never installed; imported from the repository root as `devtools.*`
  render_diff.py        the text comparison of two rendered slots (justfile `render-diff`); reads rendered output only and never imports the generator
  dupe_sweep/           the duplication sweep, run as `python3 -m devtools.dupe_sweep` — enumerates one-idea-two-places candidates over kb_tools/ (justfile `sweep-python`)
    __init__.py         package docstring (what the sweep is for, its passes, candidates not verdicts)
    __main__.py         the `-m` entry
    corpus.py           the corpus read from git, never a directory walk; the sweep's error
    clustering.py       units, containment scoring, shingle-blocked clustering, union-find grouping
    normalization.py    text to lower-cased words, `@!…!@` placeholders dropped
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

`just install` wraps `python3 -m adjagent install <project>/<subdir>` (`adjagent/install.py`). It
refuses, with nothing written, a ROOT that is this repository or inside a shipped package's source.
Otherwise it renders every definition, replaces each shipped package's destination whole
(`SHIPPED_PACKAGES`) with a copy, writes the renders over what is there, and removes each file under
`agents/` or `commands/` that this run did not write, that would ship, and whose frontmatter opens
with a `!GENERATED!` banner, then each directory that leaves empty. A render that fails writes
nothing. There is no hash, backup or refusal of a modified file: the consumer tracks the installed
set, and its git is the record of what an install changed.

The package copy skips a vocabulary of names matched at any depth (test directories, caches,
`.DS_Store`, `.bak` files, the project documents) and carries the executable bit. A copied file of a
`#`-comment type (`.py`, `.sh`, `.toml`, `.mk`, `.just`) takes the installed banner; any other file
is copied byte-verbatim. `just install-agents-here` installs this repository's own `.claude/` and
`.opencode/` through the same verb.

## Composition Model

A definition is its rendered text with holes. A module under `adjagent/definitions/` reads top to
bottom as the file it renders and defines `DEFINITIONS`, a tuple of `Definition` records
(`adjagent/definition.py`): `name`, `body`, `kind`, `folder`, and for an agent `description`,
`tools`, `tier` and optionally `color`. `body` is a string built at import: an f-string over the
module's own triple-quoted text, its own constants, and the constants and text functions of
`adjagent/clauses.py` (imported as `from adjagent import clauses`, written `{clauses.NAME}`). A
module with several outputs has a longer tuple. A module is registered by existing in the package
(`definitions.discover`); an output path produced by two modules is refused, naming both. Where a
module goes and what it is called are in CONVENTIONS.md, "Adding Definitions".

SPEC.md's single-sourcing property holds because of how text is shared, in three cases:

- **Identical in two definitions** is one constant: in `clauses.py` when the definitions are in
  different modules, in the module's private constants when they ship as a set.
- **Identical but for a few words** is a slot constant, a string with `{name}` holes filled by
  `.format` where each definition uses it in its body. Across modules the same shape is a function
  in `clauses.py` taking at most three keyword-only parameters, such as `clauses.kb_orientation`.
- **Different in structure** is written out in each definition. A sentence that belongs to one
  definition and sits among shared text is written inline in that paragraph around the constant;
  no field, class or profile carries it.

Definitions that ship as a set live in one group module (`mad_referees.py`, `mad_design_topics.py`,
`mad_debate.py`, `kb_session.py`), and the text only that set shares is the module's private
constants, so a reader of the module needs nothing behind an import. `clauses.py` holds only text
shared across sets. A private constant cannot name `clauses.*`; shared text that holds a harness
string takes a hole filled at the call site, as `_GUEST_CONTRACT` takes `harness_dir` in
`mad_referees.py`.

### Holes

The renderer fills one closed set of holes, spelled by `vocabulary.hole`: `@!hrn-<key>!@` for the
four harness strings (agents file name, project harness directory, project scratch directory, user
harness directory) and `@!fam-<anchor>!@` for the family overlay anchors a definition exposes
(`gap-aversion`, `ask-vs-stipulate`). The agents file alone also carries `@!agf-<key>!@` for its
scope name and the one model name its coder-dispatch rule cites, which is the default family's
medium tier rendered through the harness. No prose in the repository contains `@!`.

`render.filled_body` fills a body in one pass over its paragraphs and does not rescan what it
filled, so a family's overlay text or a harness string cannot introduce a further hole. A
placeholder-shaped span naming no key is refused, naming the definition and the span. An anchor the
family does not fill leaves nothing, and a paragraph that fills to nothing is dropped with its blank
line. The overlay for an anchor is the family's text for the definition's tier-mapped member, else
the family-wide text, else nothing (`family.py` states the rules for authoring one).

### Kinds

`kind` decides where the definition goes, what frontmatter the harness emits for it, and which
fields it takes. `folder` is the path below the output root for nested outputs, as in
`agents/mad/design-topics/`.

| Kind | Output | Frontmatter | Fields |
|---|---|---|---|
| agent | `agents/<folder>/<name>.md` | the harness's agent fields, the model from `tier` through the tier map | `description`, `tools`, `tier` required; `color` optional |
| document | `agents/<folder>/<name>.md` | the harness's document fields: none under claude, `mode: subagent` and `disable: true` under opencode | none of the agent fields |
| command | `commands/<folder>/<name>.md` | no field lines, and no blank line after the closing fence | none of the agent fields |
| agents file | none | none; renders to a block, see Agents File | none of the agent fields |

Every rendered file opens with the banner (see Banner), and a `Definition` refuses at construction
any field outside its kind's contract.

### Harnesses and families

A harness is a `Harness` dataclass (`adjagent/harness.py`) holding what rendered output differs on
between harnesses: the four hole strings, the tool spellings, the model shape it accepts, and the
frontmatter emitter. A family is a `Family` dataclass (`adjagent/family.py`) holding the tier map
and the overlays by anchor. An instance is one module, in `adjagent/harnesses/` or
`adjagent/families/`, defining `HARNESS` or `FAMILY`, with no class in it. `loading.load` reads the
modules of a package in name order and keys each by its module name with `_` read as `-`
(`gemma_4.py` is `gemma-4`). The constructor is the validator: an instance missing a field, or a
family not staffing exactly the five tiers, fails at import. The `Render` record
(`adjagent/context.py`) carries the harness, the family and the invocation's two tier maps, and
resolves a tier to its rendered model text and an anchor to its overlay.

### Structural rules

Two checks over source and output fix the properties above, and both are tests in the suite
(`just test adjagent`). `render` runs neither: a syntax-tree analysis has no place on a consumer's
machine of unknown Python.

- **Substitution depth is one.** `tests/_structure.py` walks the syntax trees of the definition
  modules and `clauses.py`. A module-level constant is a string literal or an f-string over
  constants in the same module, never a call. The only calls in a definition module are
  `Definition(...)` in `DEFINITIONS` and, inside a `body=` value, `clauses.<name>(...)` and
  `<constant>.format(...)` on a string-literal constant, every argument a literal or a constant. A
  `clauses.py` function takes at most three keyword-only parameters and returns one string over its
  parameters and constants, with no call. A chain of constants cannot defeat the depth, because
  nothing a call returns can be bound to a constant or passed as an argument: slot text is always
  fixed text, and filling it is the last substitution. The same walk confirms a definition module's
  top level holds only imports, string constants and `DEFINITIONS`.
- **A paragraph two outputs share has one source.** `tests/test_adjagent.py` renders every
  definition twice, once as written and once with each `clauses` constant, function and private
  constant standing as a sentinel, and fails on a paragraph or list item that survives both in two
  outputs: it was written out rather than taken from a constant.

### History

Before 1.0 definitions were Markdown templates with a marker grammar, namespaces and a chunk table,
expanded by a separate generator. It was replaced because every author and reviewer had to learn a
grammar a language already supplies as calls, scope and modules, and because the grammar owned the
boundaries between paragraphs and so left artefacts in the text.

## Banner

A rendered file carries two banner lines in its frontmatter: `# !GENERATED! from
adjagent/definitions/<module>.py`, with the edit rule and where change requests go, and
`# !TUNING!`, which records the family, the definition's seat and member, the tier map, the alias
map where one was given, the tiers the family tunes nothing for (`stock`), and the harness. A
copied package file of a `#`-comment type carries one `# !INSTALLED! from <source>` line with the
same edit rule, below its shebang where it has one. Nothing carries a hash, and the only backup is
the agents file's rolling `backup.<name>`.

## Verification, and Why There Is No Verification Verb

There is no `check` verb, and adding one back is a decision to be argued rather than an omission to
be filled. A render is the only thing that knows what a definition produces, so a verb that
re-rendered a tree and compared would be asking the producer whether it agrees with itself: a
rendering defect reaches both sides and the report reads clean. What such a verb could genuinely
detect — staleness of a build product — a free re-render fixes.

The comparison is `just render-diff`, which reads rendered output only. It replaces each banner
block with one constant line and collapses whitespace inside a paragraph outside fenced code;
headings, list items, table rows, fenced blocks and frontmatter stay exact
(`devtools/render_diff.py` states the rules). `just render <slug>` renders into `rendered/<slug>/`
and refuses a slug starting with `reference`. Those three slots (claude, opencode, and the gemma-4
family, which fills the overlay anchors) are the baseline, written only by `just retake-reference`,
so a `render-diff` after a change reports that change and nothing the baseline already held.

`tests/test_adjagent.py` holds the package's properties: each kind's frontmatter against literal
lines, every definition under `agents/` extracting frontmatter-free and every participant extracting
to the contract document, placeholder filling and refusal, overlay resolution, the line cap on a
rendered agent, and the structural rules (Composition Model). `tests/test_adjagent_install.py` holds
the install and agents-file cases. Every verb of the generator exits 0 on success and 2 on a
refusal; there is no verdict code.

## Sanctioned Invocation

`just install`, `just render`, `just retake-reference` and `just install-agents-file <dir>
[harness]` reach `python3 -m adjagent`: `render` and `retake-reference` through `install` and the
stable private `render-agents-file HARNESS OUT` recipe, which a later revision calls inside a
worktree of an earlier one, so its name and two arguments do not change incompatibly. Recipes read a
harness's values through `python3 -m adjagent harness NAME KEY`, never from a copy of them.

## Agents File

The harness agents file is a definition of the agents-file kind
(`adjagent/definitions/harness_agents_file.py`). Its body is the whole file as a fresh install holds
it: the title carrying the scope-name hole, then the span from the begin marker line to the end
marker line. `render.render_agents_file(harness, scope=...)` fills it under the default family's own
tiers whatever the invocation's tuning, with no model-shape check, so its text is a function of the
harness and the scope alone. The scope is `Global` in the harness's user directory and otherwise the
directory's name.

`adjagent/agents_file.py` implements the install SPEC.md specifies. It finds the span by the
stripped ends of the marker lines, replaces it with the rendered span, and writes every other byte
back as read. Every check, including the git-status refusal over `adjagent/`, runs before the first
write.

## Subsystem Map

Every entry below is rendered from the definition module under `adjagent/definitions/` named for its
output path, or for its set (Composition Model). A shared-text name given here is a constant or
function in `adjagent/clauses.py`, and an overlay anchor is spelled `fam-<key>`.

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
  banner-format change does not reach the seats' text.
- **kb set + kb_tools** — kb-claim-scorer, kb-maintainer, kb-docent. `clauses.kb_orientation`,
  carrying the system model (two graphs, the leaf/summary contract, authored-vs-derived metadata,
  the cast) with a per-definition `role=` clause, goes to the two seats that work a finished KB —
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
  applied-mathematician carries the `fam-ask-vs-stipulate` overlay anchor; `fam-gap-aversion` sits
  on kb-claim-scorer.
