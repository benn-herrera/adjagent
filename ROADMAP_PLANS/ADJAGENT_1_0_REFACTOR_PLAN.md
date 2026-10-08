# ADJAGENT_1_0_REFACTOR_PLAN.md — adjagent 1.0: definitions as code, output tracked downstream

**Status: active; executable in the order below.** The design decisions are settled and recorded
here.

## Purpose

1.0 keeps every property the pre-1.0 system earned and drops the machinery that was only there to
hold a text-template grammar together. The properties:

- Shared prose has exactly one source.
- A definition renders deterministically for a harness (`claude`, `opencode`) and a model family.
- A render is diffable against a previous render, by a tool that reads only rendered output.
- Installing into a consumer cannot silently clobber the operator's own text.
- The behaviour rules the main session reads (the harness agents file) publish the same way.

The measure of done is body identity: below its banner, every file the 1.0 generator renders
is byte-identical to the pre-1.0 render, and every difference is one this plan names or the
owner approves.

## Decisions, settled

1. **Definitions compose in Python.** A definition is a value — a dataclass with name, description,
   tools, tier and an ordered list of sections. A shared section is a function taking keyword
   arguments and returning text. Variation is a parameter; forwarding is a call; scope is the
   language's. There is no marker grammar, no namespace vocabulary, no expander.
2. **Consumers track rendered output.** Every consuming project commits its rendered agent set;
   `git diff` after a render is the drift check there. This repository's own harness directory
   stays an untracked install target (`CONVENTIONS.md`, "An untracked file under `.claude/` … is
   render or install output").
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
8. **The banner shrinks to provenance.** A rendered file keeps a one-line generated-from banner
   naming its definition module, and the tuning line (family, seat, tier map). The body hash goes
   with the write-safety rows. A consumer's tracked copy still says what it is and what rendered it.
9. **`kb_tools` and `liaison_tools` stay vendored.** The install copies both trees into the
   consumer's harness directory, as today (`gen_defs/product.py` holds the copy table,
   `installation.py` does the copy). Tracked by the consumer, that copy is a pinned, reviewable
   snapshot the tooling runs from; a package install would be a copy too, one the consumer cannot
   see or pin. The copy's `!INSTALLED!` banner shrinks like the definitions' and the body hash goes.

## The shape

The new package is `adjagent/`; every new module path below is under it.

```python
@dataclass(frozen=True)
class Definition:
    name: str
    description: str
    tools: Tools                 # neutral vocabulary; the harness adapter spells it
    tier: Tier                   # highest … lowest; the family binds the model
    sections: tuple[str, ...]    # rendered in order; each already text
    color: str | None = None

def python_coder(ctx: Render) -> Definition:
    return Definition(
        name="python-coder",
        description=...,
        tools=ALL,
        tier="medium",
        sections=(
            core_principles(kind="coder", tail="PEP 8 is the baseline when the project is silent."),
            EXPERTISE,                           # a module constant: prose
            parallel_execution(),
            output_format(),
            dissent(),
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
- A definition module returns one `Definition` or a tuple of them: the four MAD participants and
  the two MAD commands are one module each returning several, as their templates declare several
  outputs today.
- The harness agents file is a definition whose two operator-text parameters are passed in as
  strings the renderer never rescans. There is no rescanning anywhere, so verbatim needs no kind
  of its own.
- `python3 -m adjagent render --harness NAME --family NAME --out DIR` renders; the runner targets
  keep their names and flag grammar (`--model-tier-map`, `--model-pin-tier-alias-map`,
  `--harness`, `--family`).

## Acceptance

The oracle is the pre-1.0 render of `main` at `ad57df2`, taken once before any port into two slots
of the `render` target: `just render reference` for claude, and `just render reference-opencode
--harness=opencode` with the flags `install-agents-here` passes. Neither slot is re-rendered until
stage 4 lands.

Comparison is of bodies: everything below the leading `#` banner block of each rendered file. The
old banner names a template and carries a hash; the new one names a module. Stage 1 gives
`render-diff` that comparison, reading only rendered output, so the target stays implementation-
neutral.

- **Stages 1–3**: the 1.0 generator renders the ported subset into its own slot, and the check is
  per file: each ported output's body against the reference slot's. Unported outputs are not
  compared.
- **Stage 4**: the full `render-diff`, both harnesses, must report nothing but the banner line.

And once at the end, outside this repository: render into a consumer that tracks its set and read
its `git diff`.

## Tool inventory

What each existing piece reads decides its disposition. A piece that reads only rendered output or
the consumer side keeps its code; one that reads `templates/` or imports `gen_defs` cannot survive
stage 4 unchanged and is listed with what stage 4 does to it.

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
difference. The old generator keeps rendering, and stays the oracle, until stage 4 ends.

1. **Skeleton.** `adjagent/` with `Definition`, `Render`, the harness and family dataclasses, the
   claude and opencode adapters, the renderer with its two-line banner, and the render CLI; the
   two reference slots taken; `render-diff` extended to compare bodies. Proof: `python-coder`
   ported by hand renders body-identical under both harnesses.
2. **Shared sections.** The chunk table ported to section functions, grouped by the sections the
   definitions actually have (principles, testing, parallel execution, output format, dissent,
   review, kb orientation, MAD contract). A variant becomes a parameter; a chunk used by one
   definition becomes that definition's own prose. Proof: the seven language coders and seven
   platform experts render body-identical.
3. **Definitions.** The remaining 26 agent templates (29 outputs) and 8 command templates (9
   outputs), one module per template, in groups: the review and writing seats (architect,
   security-reviewer, prompt-engineer, tech-writer, tech-writer-reviewer, prose-architect); the
   domain seats (applied-mathematician, the two economists, literature-scout, ml-engineer,
   biz-dev-strategist, marketing-comms-expert); the kb set; guest-liaison and the MAD set; the
   commands. Proof after each group.
4. **The agents file and the switch.** The harness agents file as a definition; `just install`
   rebuilt as render, package copy and overwrite; every re-point in the inventory landed
   (`sweep-python`, `format-python`, `_harness-value` and `render-agents-file`, the
   `TEST_SURFACE_MAP` rows, the five kept tests, the marker sweep, `kb-testing/justfile`,
   `test_kb_driver_head.py`, `devtools/tests`); the full `render-diff` against both reference
   slots clean but for the banner; then `gen_defs/`, `templates/` and the retired tests deleted in
   the same commit (`CONVENTIONS.md`, "Obviated code is deleted, not parked").
5. **Contract documents.** `SPEC.md` loses nothing it promises; `ARCHITECTURE.md`'s Template System
   section is replaced by the composition model; `CONVENTIONS.md` drops the identifier class, the
   namespace rule and chunk single-sourcing, and gains the one-module-per-definition rule.
   `ROADMAP.md` items re-examined: 3 (atomic install) and 4 (unified install) close or shrink
   under tracked output; 6 (multi-harness) is the adapter; 14 (name prefix) is a render flag.

## Risks

- **A difference that is not a bug.** The old render has artefacts of the grammar — a stripped
  edge newline, a separator a chunk could not own. Body identity may require reproducing one; the
  stage commit names it and a later cleanup removes it on purpose.
- **Section granularity.** Porting 147 chunks one-to-one reproduces the paragraph-level design in
  a new syntax. Stage 2 groups by section first and only splits where two definitions genuinely
  share a paragraph and nothing more.
- **Scope creep into the definitions' content.** The port changes no prose. Content changes wait
  for the first 1.0 release, so that the acceptance diff stays a statement about the generator.
- **The banner.** It is the one line every file is allowed to differ on; the comparison must
  exclude exactly it and nothing else, or a body regression hides behind it.
