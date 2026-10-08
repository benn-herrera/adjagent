# ACTIVE_PLAN.md — adjagent 1.0: definitions as code, output tracked downstream

**Status: in execution on `lessons-learned-refactor`, in the order below.** Stages 1 and 1b are
landed (`bec0bf9`, `248b78b`); stage 1c is in flight. The design decisions are settled and
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

1. **Definitions compose in Python.** A definition is a value — a dataclass with name, description,
   tools, tier and an ordered list of sections. A shared section is a function taking keyword
   arguments and returning text. Variation is a parameter; forwarding is a call; scope is the
   language's. There is no marker grammar, no namespace vocabulary, no expander.
2. **Consumers track rendered output and do not edit it.** Every consuming project commits its
   rendered agent set; `git diff` after a render is the drift check there. The set is not for
   local edit: a change request comes to this project for evaluation, implementation and
   availability to every consumer, and a consumer's own needs are met in its `CONVENTIONS.md`.
   This repository's own harness directory stays an untracked install target (`CONVENTIONS.md`,
   "An untracked file under `.claude/` … is render or install output").
3. **Stdlib only, no project table beyond a name.** The generator runs as `python3 -m adjagent`
   against the system interpreter. Composition in functions needs nothing a template engine would.
4. **Prose lives in Python.** Triple-quoted raw strings in the section module that parameterizes
   them. No sibling Markdown: a definition reads top to bottom in one file, a shared section in one
   other.
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
10. **The unit of composition is the section.** A `Section` base class with `render(ctx) -> str`;
    one subclass per section family, around ten, named for what the section is; `Prose` for a
    definition's own text. A public name under `adjagent/sections/` is a section class or a value
    type a section field is typed with, never a paragraph: a chunk's text is a private constant of
    the section that emits it, and a chunk's slot is a field of that section. No associative table
    of named text.
    - **A field that carries the definition's own text joined into a shared paragraph is named
      `lead` (own text opening the paragraph) or `tail` (own text continuing it), declared through
      the `OwnText` namespace (`lead: str | None = OwnText.lead`), whose only attributes are those
      two: any other spelling is an `AttributeError` at import, and `Section.__init_subclass__`
      refuses a marker bound under another name. Every such join is then a grep, which is what
      stage 6 removes. A naming rule agents must follow is enforced at class definition, not by
      observation; a package-wide rule a class cannot see about itself is a test.
11. **What varies by definition is a field of the section it lands in.** The unit-test framework,
    the build commands, the package registry, the logging baseline: each is a field of
    `Testing`, `BuildSystem`, `Dependencies` or `Logging`, named for its slot, with the common
    case as default. There is no profile: the stage 1b `Profile` held thirteen fields each read by
    one section, five of them paragraphs, and hid the varying values from `explain`. A vocabulary
    two or more section classes read is a value type the field is typed with — `Mode` for the two
    debate referees (gate, seat, outcome, the run and file names) and the liaison pair (principal,
    substantive) — declared `mode: Mode = Mode.field`, its instances defined in the definition
    modules so the words stay in the definition. The admission rule that keeps it from becoming a
    profile: a term joins only when two or more classes read it, asserted by a test. Unifying the
    referees' vocabulary on one set of words is a content change for the post-switch list.
12. **A definition is data.** A definition module defines `DEFINITIONS`, a tuple of `Definition`
    values whose sections are section instances; nothing in it takes `ctx`, which enters at render.
    Rendering iterates the package's modules and renders every entry. A multi-output module is a
    longer tuple, not a special case. No field is called `variant`: variation is a field with a
    meaningful name or a second class.
13. **The author's view is generated, not authored.** `python3 -m adjagent explain <name>` renders
    a definition with each paragraph headed by the section and field that produced it. The editing
    process is five lines in the README's Development section; if it cannot be stated that
    briefly, the shape is wrong.
14. **Acceptance is text identity, not byte identity.** The comparison collapses whitespace inside
    a paragraph outside fenced code; paragraph boundaries, list items, headings, table rows, fenced
    blocks and frontmatter stay exact. Whitespace a model does not read is not pinned, which
    retires `wrap=` reproduction, space-joins and the trailing-sentence idiom from the port.
15. **A definition has a kind and a folder.** `kind` is agent, document or command, and later
    skill; it decides the output root, the frontmatter the harness emits (a document carries the
    harness's document frontmatter, a command none, and no blank line after its fence), and which
    fields are required. `folder` is the path below the root for nested outputs such as the MAD
    reference documents. Output paths, not names, are unique.
16. **A definition's own prose can name a harness value as typed data.** `Prose` takes parts, a
    string or a `HarnessText` member naming one of the harness's string fields, joined at render.
    `Render` carries the definition's seat so a section can resolve an overlay; `FamilyText(anchor)`
    is the section that renders one, and an empty section renders nothing.
17. **A shared sentence moved to its section's canonical order is a named difference, not a
    bug.** Three templates place two shared sentences in swapped order; the section renders them
    once, in one order, and the stage 3 commit names each file that changes for that reason. The
    previous system's inability to own an order was its defect; reproducing it is not fidelity.
18. **Harnesses and families follow the definitions' expansion pattern.** `adjagent/harnesses/`
    and `adjagent/families/`, one module per instance, a fixed module-level name (`HARNESS`,
    `FAMILY`) read by the same loader that reads `DEFINITIONS`. The types stay at the package root;
    an instance module holds no class.

## The shape

The new package is `adjagent/`; every new module path below is under it.

```python
@dataclass(frozen=True)
class Definition:
    name: str
    description: str
    tools: Tools                      # neutral vocabulary; the harness adapter spells it
    tier: Tier                        # highest … lowest; the family binds the model
    sections: tuple[Section, ...]     # rendered in order, each with render(ctx)
    color: str | None = None

DEFINITIONS = (
    Definition(
        name="python-coder",
        description=...,
        tools=ALL,
        tier="high",
        sections=(
            Prose(_INTRO),
            CorePrinciples(kind="coder", baseline="PEP 8 is the baseline that applies …"),
            Prose(_EXPERTISE),
            Testing(unit_tests="`pytest` with …", routing="the logging system …"),
            BuildSystem(direct="the interpreter, test runner, or linter"),
            Dependencies(registry="PyPI downloads"),
            ParallelExecution(),
            OutputFormat(),
            Dissent(),
        ),
    ),
)
```

- `Render` carries the harness adapter, the family and the invocation's tier and alias maps, so a
  section that needs a model name or an overlay asks `ctx` for it. That one parameter replaces the
  dynamic table, the family source, the harness source and the verbatim value kind.
- A harness is a dataclass in `adjagent/harness.py`: agents-file name, harness and scratch
  directory names, the tools vocabulary, the frontmatter emitter, the model pattern. One instance
  each for `claude` and `opencode`; a new harness fills the type in completely or fails at import.
- A family is a dataclass in `adjagent/family.py`: tiers to members, overlays keyed by section
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

The oracle is the pre-1.0 render of `main` at `8fa1408`, taken once before any port into two slots
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
| `templates/shared-chunks.toml` (147 chunks) | — | port to section functions; expect fewer, larger units | — |
| `templates/agents/*.tmpl.md` (40 templates, 43 outputs: 39 subagents and 4 MAD reference documents), `templates/commands/*.tmpl.md` (8 templates, 9 outputs) | — | port to definition modules, one per template; a multi-output template's module returns a tuple | — |
| `templates/harness/*.toml`, `templates/family/*.toml`, `templates/family/README.md` | — | port to dataclass instances and a module docstring | — |
| `templates/harness/AGENTS.tmpl.md` | — | port to a definition; its prose unchanged | — |
| `tests/test_gen_defs.py` (incl. the 500-line cap, `TestRenderedDefinitionSize`), `test_gen_defs_structure.py`, `test_harness_frontmatter.py`, `test_agents_file_render.py`, `test_agents_file_install.py` | generator | rewrite against the new modules; every case that pins rendered behaviour carries over, the cap included | — |
| `tests/test_write_op_contract_sources.py` | parses the `kb-metadata-write` chunk from the toml | rewrite to read the section function that replaces the chunk | — |
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
   ported by hand renders body-identical under both harnesses. Landed at `bec0bf9`, with the
   section unit at paragraph grain; that port is the taste that produced decisions 10–14.
   1b. **The section shape.** `Section`, `Profile` and `Prose`; `DEFINITIONS` discovery in place of
   the function-named-after-its-module rule; the `explain` verb; text identity in `render-diff`.
   Proof: `python-coder` re-ported to the shape renders text-identical under both harnesses.
2. **The MAD set.** A cooperative working group rather than siblings, and the group that
   exercises what `python-coder` does not: the four participants as one module's four-entry
   tuple and the two MAD commands as another's, the nested output path for the `agents/mad/`
   reference documents, command frontmatter, the participant contract the guest extraction
   depends on (SPEC.md, Guest-Extraction Contract), and the overlay anchors. Modules: the
   participants, the two referees, the alignment assessor, `mad-guest-liaison`, the four
   reference documents, the commands. Proof: every MAD output renders text-identical in both
   harnesses. **Pause for review** of the shape before stage 3.
3. **Shared sections for the coders.** The chunk table ported to section classes, one per section
   family the definitions actually have (principles, testing, build and dependencies, logging,
   parallel execution, output format, dissent, review), each section's fields named for the slots
   the coders fill. A chunk used by one definition becomes that definition's own prose. Proof:
   the seven language coders and seven platform experts render text-identical.
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
   paragraph because a chunk could not own it, a section split at a marker boundary rather than
   a subject boundary — is removed on purpose, and the commit enumerates every differing file
   with its reason. Prose changes nothing it says; it changes where a boundary falls. The
   reference slots are re-rendered from this commit afterwards and become the oracle for 1.0.
   Inventory so far, each an artefact text identity carries: every `lead`/`tail` field (own text
   joined into a shared paragraph); the referees' "Steps 1–2 / 2–3" cross-reference computed from
   list position; `RoundDispatch`'s two sentences run as one paragraph and its two `*_points`
   wordings; the two `charter` fields that differ by one word; `MessageFile`'s shared sentence
   appended to the definition's own note; the `liaison_tools` path spelled in every command
   line rather than owned by the section. The post-switch content list, a change to what a seat
   reads and so outside this plan: unify the two referees' vocabulary on one set of words.
7. **Contract documents.** `SPEC.md` loses nothing it promises; `ARCHITECTURE.md`'s Template System
   section is replaced by the composition model; `CONVENTIONS.md` drops the identifier class, the
   namespace rule and chunk single-sourcing, and gains two rules: one module per definition, and a
   public name under `sections/` is a section class, never a paragraph. The
   README's Development section states the editing process in five lines: where a definition
   lives, where shared text lives, how to change text for everyone versus for one definition,
   `just render` then `just render-diff` to see what a change does, `explain` to see where a
   paragraph comes from, and that a wrong field name fails at import.
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
- **Section granularity.** Porting 147 chunks one-to-one reproduces the paragraph-level design in
  a new syntax; the stage 1 port did exactly that, and decisions 10–12 are the correction. The
  check in review: a public name under `sections/` that is a paragraph rather than a section
  class is the regression.
- **Scope creep into the definitions' content.** The port changes no prose. Content changes wait
  for the first 1.0 release, so that the acceptance diff stays a statement about the generator.
- **The banner.** It is the one line every file is allowed to differ on; the comparison must
  exclude exactly it and nothing else, or a body regression hides behind it.
