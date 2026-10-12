# ACTIVE_PLAN.md — adjagent 1.0: definitions as code, output tracked downstream

**Status: in execution on `heredoc-shape`, cut from `lessons-learned-refactor` at its stage 2, in
the order below.** Stage 1 is landed; the section shape that followed it is retired (stage 1's
note); stages 2, 3 and 4 on the heredoc shape are landed: all fifty-two outputs render
text-identical to the three oracle slots; stage 5, the agents file and the switch, is next. The
branch is kept rebased on `main`. The design decisions are settled and
recorded here.

## Purpose

1.0 keeps every property the pre-1.0 system earned and drops the machinery that was only there to
hold a text-template grammar together. The properties:

- Shared prose has exactly one source.
- A definition renders deterministically for a harness (`claude`, `opencode`) and a model family.
- A render is diffable against a previous render, by a tool that reads only rendered output.
- Installing into a consumer cannot silently clobber the operator's own text.
- The behaviour rules the main session reads (the harness agents file) publish the same way.

The measure of done is text identity: below its banner, every file the 1.0 generator renders
carries the same paragraphs, in the same order, with the same words as the pre-1.0 render, and
every difference is one this plan names or the owner approves.

## Decisions, settled

1. **Definitions compose in Python.** A definition is a value — a record with name, description,
   tools, tier and its body text, the body an f-string over named constants. Variation is an
   expression; forwarding is an argument; scope is the language's. There is no marker grammar, no
   namespace vocabulary, no expander.
2. **Consumers track rendered output and do not edit it.** Every consuming project commits its
   rendered agent set; `git diff` after a render is the drift check there. The set is not for
   local edit: a change request comes to this project for evaluation, implementation and
   availability to every consumer, and a consumer's own needs are met in its `CONVENTIONS.md`.
   This repository's own harness directory stays an untracked install target (`CONVENTIONS.md`,
   "An untracked file under `.claude/` … is render or install output").
3. **Stdlib only, no project table beyond a name.** The generator runs as `python3 -m adjagent`
   against the system interpreter. Composition in functions needs nothing a template engine would.
4. **Prose lives in Python.** Triple-quoted strings: a definition's own text in its module, shared
   text as constants in one text module. No sibling Markdown: a definition reads top to bottom in
   one file, and a constant it names is in one other.
5. **Generator-only configuration is Python.** The harness description, the family (tier map and
   overlays) and the output declarations are dataclass instances; the constructor is the validator.
   Data something other than the generator reads stays as data: the endpoint fixtures (`.env`
   files loaded into process environments) and the operator's own text around the agents-file
   block.
6. **Fresh build, measured against the current render.** The old generator is the oracle until the
   last definition is ported; it is deleted in the stage that ports the last one, not before.
7. **Implementation-neutral tooling stays.** A target or test that reads rendered output or the
   consumer side keeps its code. One that reads `templates/` or imports `gen_defs` is re-pointed,
   rebuilt around its purpose, or retired with the lesson it closes (inventory below).
8. **The banner shrinks to provenance and the edit rule.** A rendered file keeps a one-line
   generated-from banner naming its definition module and stating that the file is not for local
   edit, with change requests to this project, and the tuning line (family, seat, tier map). The
   body hash goes with the write-safety rows. A consumer's tracked copy says what it is, what
   rendered it, and where a change goes.
9. **`kb_tools` and `liaison_tools` stay vendored.** The install copies both trees into the
   consumer's harness directory, as today (`gen_defs/product.py` holds the copy table,
   `installation.py` does the copy). Tracked by the consumer, that copy is a pinned, reviewable
   snapshot the tooling runs from; a package install would be a copy too, one the consumer cannot
   see or pin. The copy's `!INSTALLED!` banner shrinks like the definitions' and the body hash goes.
10. **A definition is its rendered text with holes.** A definition module defines `DEFINITIONS`,
    a tuple of `Definition` records whose `body` is a string, built at import from the module's
    own triple-quoted text and named constants. The module holds nothing but imports, string
    constants and `DEFINITIONS`, which an `ast` test enforces; nothing in it takes `ctx`. A
    multi-output module is a longer tuple. The module reads top to bottom as the file it renders:
    the property the template system had and the section shape of stages 1b–3 lost, which is why
    that shape was retired at three ported definitions.
11. **Shared text is a flat module of named string constants.** `adjagent/text.py` holds the
    chunk table as Python constants named as the chunks were, in UPPER_SNAKE; a chunk with slots
    is a small function there taking keyword arguments; a chunk with variants is one constant per
    variant. A per-definition sentence interleaved with shared text is written inline in the
    definition's own paragraph around the constant: no field, class or profile carries it.
    Shared text has three cases: identical in two definitions is a constant; identical but for a
    few words is a slot constant, a string with `{name}` holes filled by `.format(...)` at the
    call site inside the body, at most three holes; different in structure is written out in
    each. Definitions that share text and ship as a set live in one group module, and the text
    they share is that module's private constants, so nothing a reader of the module needs is
    behind an import: the two debate referees, the three design topics, the two debate commands.
    The text module holds only text shared across sets. Unifying the referees' vocabulary is a
    content change for the post-switch list, after which their slot constants lose their holes.
12. **Render-time holes are a closed flat key set, filled once.** `@!hrn-<key>!@` for the four
    harness strings and `@!fam-<anchor>!@` for the overlay anchors, dashes not dots because the
    space is flat; a spelling that occurs in no prose, where nine templates carry a literal `$`
    and eight a `{`. The renderer owns the key set, refuses an unknown key, and fills in one pass
    with no rescan. An anchor the family does not fill consumes its surrounding blank line.
13. **The author's view is the module.** No generated view: the body is the text, and a
    constant's name says what stands there. The editing process is five lines in the README's
    Development section; if it cannot be stated that briefly, the shape is wrong.
14. **Acceptance is text identity, not byte identity.** The comparison collapses whitespace inside
    a paragraph outside fenced code; paragraph boundaries, list items, headings, table rows, fenced
    blocks and frontmatter stay exact. Whitespace a model does not read is not pinned, which
    retires `wrap=` reproduction, space-joins and the trailing-sentence idiom from the port.
15. **A definition has a kind and a folder.** `kind` is agent, document or command, and later
    skill; it decides the output root, the frontmatter the harness emits (a document carries the
    harness's document frontmatter, a command none, and no blank line after its fence), and which
    fields are required. `folder` is the path below the root for nested outputs such as the MAD
    reference documents. Output paths, not names, are unique.
16. **A rule agents must follow is enforced, not observed.** One structural test over the syntax
    trees of the definition modules and the text module is the whole enforcement, and it fixes
    substitution depth at one by leaving no syntactic position for a second level: a module-level
    constant is a string literal, never a call; the only calls are `.format(...)` on a constant
    and `t.name(...)` on the text module, inside a `Definition`'s `body=` only, with literal or
    constant arguments; a text-module function returns one string expression with no call and at
    most three keyword parameters; a module's top level holds nothing but imports, constants and
    `DEFINITIONS`. A chain of depth-one calls accumulated into constants is impossible because a
    constant cannot be a call. The identical-paragraph test over rendered output is the backstop:
    a paragraph two outputs share must come from one constant. Both are dev tests in the suite,
    the pre-commit gate; `render` runs neither, since a syntax-tree analysis has no business on a
    consumer's machine of unknown Python.
17. **A shared sentence moved to its constant's canonical order is a named difference, not a
    bug.** Where two templates place two shared sentences in swapped order, a constant holding
    both would fix one order and the stage commit would name each file that changes for that
    reason. The previous system's inability to own an order was its defect; reproducing it is not
    fidelity. In the event the swapped sentences were already separate units, so no file differed.
18. **Harnesses and families follow the definitions' expansion pattern.** `adjagent/harnesses/`
    and `adjagent/families/`, one module per instance, a fixed module-level name (`HARNESS`,
    `FAMILY`) read by the same loader that reads `DEFINITIONS`. The types stay at the package root;
    an instance module holds no class.

## The shape

The new package is `adjagent/`; every new module path below is under it.

```python
@dataclass(frozen=True, kw_only=True)
class Definition:
    name: str
    body: str                         # the rendered text, holes filled once at render
    kind: Kind = Kind.AGENT
    folder: str = ""
    description: str | None = None    # agents only
    tools: Tools | None = None        # neutral vocabulary; the harness adapter spells it
    tier: Tier | None = None          # highest … lowest; the family binds the model
    color: str | None = None

from adjagent import text as t

DEFINITIONS = (
    Definition(
        name="python-coder",
        description=...,
        tools=ALL,
        tier="high",
        body=f"""You are a senior Python engineer. …

{t.CODE_PRINCIPLES_CODER} PEP 8 is the baseline that applies when the project states nothing.

**Readable over clever**: …

{t.PARALLEL_EXECUTION_GENERAL}

{t.CODER_OUTPUT_FORMAT}

{t.DISSENT}""",
    ),
)
```

- `Render` carries the harness adapter, the family and the invocation's tier and alias maps; the
  renderer reads them to emit frontmatter and to fill the body's holes. That one record replaces
  the dynamic table, the family source, the harness source and the verbatim value kind.
- A harness is a dataclass in `adjagent/harness.py`: agents-file name, harness and scratch
  directory names, the tools vocabulary, the frontmatter emitter, the model pattern. One instance
  each for `claude` and `opencode`; a new harness fills the type in completely or fails at import.
- A family is a dataclass in `adjagent/family.py`: tiers to members, overlays keyed by anchor
  name. One instance per family, replacing `templates/family/*.toml`; the authoring guide
  (`templates/family/README.md`) becomes the module docstring.
- A definition module defines `DEFINITIONS`, a tuple: the four MAD participants and the two MAD
  commands are one module each with a longer tuple, as their templates declare several outputs
  today.
- The harness agents file is a definition whose two operator-text parameters are passed in as
  strings the renderer never rescans. There is no rescanning anywhere, so verbatim needs no kind
  of its own.
- `python3 -m adjagent render --harness NAME --family NAME --out DIR` renders; the runner targets
  keep their names and flag grammar (`--model-tier-map`, `--model-pin-tier-alias-map`,
  `--harness`, `--family`).

## Acceptance

The oracle is the pre-1.0 render of the current `main`, re-taken whenever `main` changes a
template (each slot's `RENDER-FLAGS.txt` records its flags), into three slots
of the `render` target: `just render reference` for claude, and `just render reference-opencode
--harness=opencode` with the flags `install-agents-here` passes, and `just render reference-gemma
--family=gemma-4 --model-pin-tier-alias-map=all=sonnet` for the overlay anchors, which only a
non-claude family fills. No slot is re-rendered until stage 5 lands.

Comparison is of text: everything below the leading `#` banner block of each rendered file, with
whitespace inside a paragraph outside fenced code collapsed to one space (decision 14). The old
banner names a template and carries a hash; the new one names a module. `render-diff` makes that
comparison through `devtools/render_diff.py`, which reads only rendered output, so the target
stays implementation-neutral.

- **Stages 1–4**: the 1.0 generator renders the ported subset into its own slot, and the check is
  per file: each ported output's text against the reference slot's. Unported outputs are not
  compared.
- **Stage 5**: the full `render-diff`, both harnesses, must report nothing but the banner line.

And once at the end, outside this repository: render into a consumer that tracks its set and read
its `git diff`.

## Tool inventory

What each existing piece reads decides its disposition. A piece that reads only rendered output or
the consumer side keeps its code; one that reads `templates/` or imports `gen_defs` cannot survive
stage 5 unchanged and is listed with what stage 5 does to it.

| Piece | Reads | Disposition | Lesson it closes, where retired |
|---|---|---|---|
| `just render-diff` | rendered | keep; gains the body comparison (stage 1) | — |
| `just render`, `render-agents-file`, `_harness-value`, `default`, `_venv` | templates via `gen_defs` | rebuild on the new CLI; names and slot grammar unchanged | — |
| `just install <dir>` | templates → consumer | rebuild: render, copy the packages, overwrite; the consumer's git is the safety | tracked output makes write-safety redundant |
| `just install-agents-file` and the marker block (`gen_defs/agents_file.py`, install half) | harness toml + consumer file | rebuild on the harness dataclass; block-only replacement, malformed-marker refusal and the rolling backup stay — the file is co-owned with the operator | — |
| `just install-agents-here` | this repo | keep; flags unchanged | — |
| `just test`, `just test-changed`, `TEST_SURFACE_MAP` | tests | keep; surface rows renamed with the modules | — |
| `just sweep-prose` (`devtools/dupe_sweep` prose pass) | templates | rebuild as a test over the rendered set: an identical paragraph in two outputs from two sources | shared prose is one function by construction |
| `just sweep-python`, `devtools/dupe_sweep/corpus.py` | imports `gen_defs.paths` | re-point `REPO_ROOT` and `TEMPLATE_SUFFIX` to the new package | — |
| `devtools/tests/` | fixtures shaped like templates | rewrite with the sweep | — |
| `just format-python` | path lists naming `gen_defs` | re-point | — |
| `gen_defs/markers.py`, `chunks.py`, `discovery.py` | templates | retire; a definition registers by being a function in the package | a language already has calls, scope and modules |
| `gen_defs/banners.py` (hash), backup-on-hand-edit and refusal rows in `installation.py` | consumer | retire; the generated-from and tuning lines survive in the new renderer | consumers track output; `git diff` is the drift check |
| `gen_defs/product.py`, the copy in `installation.py` | sources → consumer | carry forward as `adjagent/product.py`: the copy table and exclusion vocabulary, minus the hash and backup rows | — |
| `gen_defs/frontmatter.py`, `harness.py` | harness toml | rebuild as the harness dataclass and its emitter | — |
| `gen_defs/model_tuning.py` | family toml | rebuild as the family dataclass; the two map flags keep their grammar | — |
| `gen_defs/pruning.py`, `rendering.py`, `generation.py`, `cli.py`, `errors.py`, `paths.py`, `__init__.py`, `__main__.py` | templates | rebuild; the CLI keeps its flag names | — |
| `templates/shared-chunks.toml` (147 chunks) | — | port to constants and slot functions in the text module; a chunk one definition uses becomes that definition's own text | — |
| `templates/agents/*.tmpl.md` (40 templates, 43 outputs: 39 subagents and 4 MAD reference documents), `templates/commands/*.tmpl.md` (8 templates, 9 outputs) | — | port to definition modules, one per template; a multi-output template's module returns a tuple | — |
| `templates/harness/*.toml`, `templates/family/*.toml`, `templates/family/README.md` | — | port to dataclass instances and a module docstring | — |
| `templates/harness/AGENTS.tmpl.md` | — | port to a definition; its prose unchanged | — |
| `tests/test_gen_defs.py` (incl. the 500-line cap, `TestRenderedDefinitionSize`), `test_gen_defs_structure.py`, `test_harness_frontmatter.py`, `test_agents_file_render.py`, `test_agents_file_install.py` | generator | rewrite against the new modules; every case that pins rendered behaviour carries over, the cap included | — |
| `tests/test_write_op_contract_sources.py` | parses the `kb-metadata-write` chunk from the toml | rewrite to read the kb-maintainer module, whose own text now holds what the chunk held | — |
| `tests/test_metadata_marker_sweep.py` | `kb_tools` and `templates/` | keep; re-point its template root to the definition package | — |
| `tests/test_manifest_views_in_definitions.py`, `test_retired_cli_tokens.py`, `test_orphan_name_sweep.py` | `templates/` as source | keep; re-point to the definition package (source, not the gitignored render) | — |
| `tests/test_traversal_sweep.py` | inline fixtures | keep | — |
| `kb-testing/justfile` (`_harness-value`, the harness toml glob) | harness toml via the root justfile | re-point to the new CLI's harness query | — |
| `kb_tools/tests/test_kb_driver_head.py` | runs `python3 -m gen_defs install` | re-point to `python3 -m adjagent install` | — |
| `kb-testing/` otherwise, `liaison_tools/`, `kb_tools/` | — | untouched | — |

## Stages

Each stage ends with its acceptance check and a commit whose message lists any approved
difference. The old generator keeps rendering, and stays the oracle, until stage 5 ends.

1. **Skeleton.** `adjagent/` with `Definition`, `Render`, the harness and family dataclasses, the
   claude and opencode adapters, the renderer with its two-line banner, and the render CLI; the
   two reference slots taken; `render-diff` extended to compare bodies. Proof: `python-coder`
   ported by hand renders body-identical under both harnesses. Landed.
   1b–1c and the first stage 2 (the history of `lessons-learned-refactor`) built a section shape,
   one class per shared section, fields for what varied, and ported `python-coder`, the MAD set and
   thirteen coders onto it. At twenty-eight outputs it had fifty-one classes with up to eleven
   fields each and a referee call site of sixty keyword arguments: the chunk-argument problem at
   paragraph grain, unreadable at the call site. Retired; the commits stay as the record. The
   heredoc prototype (`python-coder`, the review referee, `ios-app-expert`) that replaced it is
   decisions 10–13 and 16.
2. **The MAD set on the heredoc shape.** The group that exercises what `python-coder` does not:
   the four participants as one module's four-entry tuple and the two MAD commands as another's,
   the nested output path for the `agents/mad/` reference documents, command frontmatter, the
   participant contract the guest extraction depends on (SPEC.md, Guest-Extraction Contract),
   held as one constant both the participants and the contract document use. The two referees
   are two plain bodies. Proof: every MAD output renders text-identical in both harnesses.
3. **The coders.** Six language coders and seven platform experts, one module each; the chunks
   they reach become constants and slot functions in the text module; text two of them share
   byte for byte (the C and C++ coders' data-race and sanitizer paragraphs) is a constant. Proof:
   all thirteen render text-identical, with no named difference needed.
4. **Definitions.** The remaining agent templates and commands, one module per template, in
   groups: the review and writing seats (architect, security-reviewer, prompt-engineer,
   tech-writer, tech-writer-reviewer, prose-architect); the domain seats (applied-mathematician,
   the two economists, literature-scout, ml-engineer, biz-dev-strategist,
   marketing-comms-expert); the kb set and its commands; guest-liaison and its commands. Proof
   after each group.
5. **The agents file and the switch.** The harness agents file as a definition; `just install`
   rebuilt as render, package copy and overwrite; every re-point in the inventory landed
   (`sweep-python`, `format-python`, `_harness-value` and `render-agents-file`, the
   `TEST_SURFACE_MAP` rows, the five kept tests, the marker sweep, `kb-testing/justfile`,
   `test_kb_driver_head.py`, `devtools/tests`); the full `render-diff` against both reference
   slots clean but for the banner; then `gen_defs/`, `templates/` and the retired tests deleted in
   the same commit (`CONVENTIONS.md`, "Obviated code is deleted, not parked").
6. **Artefact removal.** The one stage whose render-diff is expected to differ: every artefact of
   the retired grammar that text identity still carried — a sentence appended to a shared
   paragraph because a chunk could not own it, a paragraph split at a marker boundary rather than
   a subject boundary — is removed on purpose, and the commit enumerates every differing file
   with its reason. Prose changes nothing it says; it changes where a boundary falls. The
   reference slots are re-rendered from this commit afterwards and become the oracle for 1.0.
   Inventory so far, each an artefact text identity carries: a shared sentence appended to a
   definition's own paragraph where the chunk could not own it; the referees' "Steps 1–2 / 2–3"
   cross-reference, numbered by list position; two referee sentences run as one paragraph in one
   referee and two in the other; the `liaison_tools` path spelled in every command line of the
   liaison definitions. The post-switch content list, a change to what a seat reads and so
   outside this plan: unify the two referees' vocabulary on one set of words, after which their
   bodies converge to constants.
7. **Contract documents.** `SPEC.md` loses nothing it promises; `ARCHITECTURE.md`'s Template System
   section is replaced by the composition model; `CONVENTIONS.md` drops the identifier class, the
   namespace rule and chunk single-sourcing, and gains two rules: one module per definition
   holding nothing but imports, string constants and `DEFINITIONS`; and text two definitions
   share byte for byte is one constant in the text module. The README's Development section
   states the editing process in five lines: where a definition lives, where shared text lives,
   how to change text for everyone versus for one definition, `just render` then
   `just render-diff` to see what a change does, and that an unknown placeholder fails at render.
   `ROADMAP.md` items re-examined: 3 (atomic install) and 4 (unified install) close or shrink
   under tracked output; 6 (multi-harness) is the adapter; 14 (name prefix) is a render flag.
   `README.md`'s Install section becomes the consumer instruction for the tracked shape: the
   rendered set is committed by the consumer and not for local edit, a change request comes to
   this project, a consumer's own needs go in its `CONVENTIONS.md`, and the hash-and-backup
   paragraph and the symlink into this repository's project space are removed.

## Risks

- **A difference that is not a bug.** The old render has artefacts of the grammar — a sentence a
  chunk could not own appended by its caller, a boundary at a marker rather than a subject. Text
  identity carries them through stage 5; stage 6 removes them on purpose, each named.
- **Machinery growing back as text structure.** The section shape turned prose into classes and
  fields and reached the old system's mass with a different face. The check in review: a
  definition module that holds anything but imports, string constants and `DEFINITIONS`, or a
  text-module function with more than a few keyword arguments, is the regression.
- **Scope creep into the definitions' content.** The port changes no prose. Content changes wait
  for the first 1.0 release, so that the acceptance diff stays a statement about the generator.
- **The banner.** It is the one line every file is allowed to differ on; the comparison must
  exclude exactly it and nothing else, or a body regression hides behind it.
