# CONVENTIONS – Adjagent

House rules and project-specific traps only. Doc-structure conventions and general engineering ethos
live in operator config (the harness agents file, `adjagent/definitions/harness_agents_file.py`),
not here.

## Code, Definitions and Install

- **A definition module holds nothing but imports, string constants and `DEFINITIONS`.** It reads
  top to bottom as the file it renders. `just test` fails on any other top-level statement or call.
  A skill's supporting files are `SkillFile(path=…, body=…)` values inside its `files=`, each body
  held to the same rule as a definition body.
- **Text two definitions share byte for byte is one constant**, in `adjagent/clauses.py`, or in a
  group module's private constants when only that set shares it. A definition never pastes shared
  text or a paraphrase of it; `just test` fails on a paragraph two outputs write out.
  - **A private constant cannot name `clauses.*`.** Shared text that holds a harness string takes a
    hole, filled at the call site in the body.
  - **A paragraph added to `clauses.CODE_PRINCIPLES_CODER` goes before the constant's last one.**
    `python_coder.py` and `shell_dsl_coder.py` continue the constant on the same line with a
    sentence of their own, so a paragraph placed last is joined to that sentence under either
    harness and reads as theirs. `RECIPE_RULE` stands before `PROJECT_CONVENTIONS_OUTRANK` for
    that reason.
- **Composed text is never rescanned.** Outside `adjagent/definitions/`, no module of the package
  calls `str.replace`, `format` or `format_map` (`dataclasses.replace` is not one), and the only
  pattern substitution is the body fill in `render.filled_text`. A definition module's `.format` on
  one of its own string literals is the permitted call, and that literal holds no composed text.
  What a constant or a harness string fills in is literal: a placeholder-shaped span it introduces
  is never filled again. Only `tests/test_adjagent.py::test_no_composed_text_is_rescanned` stated
  the rule, which is why it is written here.
- **A `just` recipe's note goes above the recipe, not in its body.** A body with no shebang is run
  line by line, and `just` echoes every line it runs, `#` included: a note there prints on every
  invocation, so a note explaining the recipe reads as its output. Above the recipe the line is
  never a command line and stays silent under either body.
- **Never comment in a rendered body.** A definition's body, and every constant it interpolates,
  becomes an agent's system prompt; maintainer commentary there ships into every dispatch and is
  read by every seat. A Python `#` comment above a constant is not in the string and is the place
  for a note the next editor needs.
- **An untracked file under `.claude/`, `.opencode/` or `rendered/` is render or install output, not
  source.** SPEC.md states what an install ships and to which destination (Deployed Surfaces), and
  what a re-install replaces (Write Safety); ARCHITECTURE.md's Repo Layout holds the trees each is
  sourced from, the gitignored dist cache among them. The next install replaces what it wrote, bar
  the installed `kbase` executable a run carrying no new one leaves standing — so a change belongs
  at the source, not in the copy. Before an edit brief names a path, `git ls-files <path>` settles
  which it is, and the brief names the source. Running definitions point at the copy, which is how a
  brief comes to name it.
- **A set a default install excludes is excluded by its definitions' names, held in
  `NOT_BY_DEFAULT`.** `install.py` holds that pattern over definition names — `excluded()`'s one
  call site in the install is the `include` filter `render_all` takes, and what it passes is a
  definition's name — and it names `^(kb-|kbase$)` today: a name is excluded by its shape, so a
  `kb-` definition would stay out of a base install, and `kbase` is the one name it excludes.
  A package destination is not a name and no destination is matched: `SHIPPED_PACKAGES` destinations
  sit beside the surfaces under `adj-tools/` — the table holds no row today — and the kb toolchain's
  sits inside one, in the `kbase` skill's own directory, where its files are stamped installed or
  carry no banner and never a generated one, so no carve-out follows and every file under a surface
  is either ours or untouched. The match is on the definition's name, not on a rendered file's stem,
  so a definition that owns several files is one keep-or-drop decision and never a partial tree. A
  second such set adds its own alternation there, over its output names — a name the pattern misses
  is rendered and shipped by every install. A run that excludes the match renders none of the
  matching definitions, and one already installed is stale: removed from the tree and named in that
  run's report.
- **The runner include line is a byte-level edit of a file the project does not own.** The
  consumer's justfile or Makefile is read and written with `newline=""`, so a rewrite keeps each
  line's own ending instead of translating it to the host's. Only a live line matches: one whose
  first non-blank character is `#` is a comment about an install, never an include. The rewrite
  splices the installed snippets-path token in place of the path the line already names and keeps
  the rest of the line, so an assignment's left-hand side and a trailing comment survive. A file
  holding more than one matching line is reported for the operator to merge by hand, never
  half-rewritten.
- **The install's recognizer spells the banner the renderer writes.** `install.py` builds its
  generated-file prefixes from `render.GENERATED_MARK`, so what recognises a generated file reads
  the spelling the renderer writes. A test that plants a literal `!GENERATED!` banner does not hold
  that binding — a change on either side passes it — so the case plants rendered output.
- **The install stamps nothing on a file under `adjagent/harnesses/resources/`, which never takes
  the package loop.** `harness_resource_copies` writes each with `copyfile` and `copymode` and
  nothing else, so a consumer receives what the source holds — a header the file already carries
  included, as the file's own text. That header is required: a resource file carries
  `!INSTALLED! … adjagent` in its first ten lines, because an install refuses to overwrite a target
  without it, and the source test enforces it for every file a harness ships. The loop beside it
  stamps by suffix (`STAMPED_SUFFIXES`), a package's files being this repository's emissions, so a
  packet adding a resource must not reuse that loop just because the walk is already there: the
  suffix says nothing about what a file already holds, and a `.py` resource would gain a banner
  above its own. This tree is the master for what it ships — an installed copy is never edited,
  and no other repository's copy is a source.
- **The two guardrail implementations change together.** `guardrail.ts` (opencode) and
  `guardrail.pl` (claude) are meant to block exactly the same Bash commands, and nothing at runtime
  compares them. A behaviour change edits both and `tests/guardrail_cases.json` in one change, and
  `tests/test_guardrail.py` is what holds them to it: it runs the table through each, under `bun`
  and `perl`, and fails, not skips, without `bun`. The guardrail catches the in-place edit and
  redirect forms agents habitually use and points them to the edit tools; it is not a boundary
  against a command built to evade it, and a detection change earns its place by the common form it
  catches, not by closing an evasion.
- **Every tree an install copies from is walked through `_shipped`, and named in `_refuse_root`.**
  The filter is what keeps a `__pycache__`, a `.DS_Store`, a `.bak` copy and this repository's own
  project documents (`SPEC.md`, `AGENTS.md` and the rest) out of a consumer; a source that skips it
  ships them, and the walk is the one place they are caught. `_refuse_root` holds the same set of
  trees — a shipped package's, the kb toolchain's, `adjagent/harnesses/resources/` — because a
  ROOT inside one is refused rather than filled with the product it is itself copying from.
- **An install whose ROOT already holds the installed `kbase` executable installs the kb set.** The
  signal is the file — `skills/kbase/kb-tools/kbase`, `kbase.exe` where that is the installed
  name — never the `kb-tools/` directory it sits in: a destination holding no file of that name is a
  base install, while one holding a `kbase` that cannot run still selects the kb set, and the source
  check is what refuses it, writing nothing. The choice is per ROOT — the harness directory — not
  per project, so a later plain `just install` into that directory refreshes the snippets and leaves
  the installed executable where it stands, rather than emptying the directory. A plain install
  includes kb exactly when its ROOT holds that executable, at `skills/kbase/kb-tools/` or in the
  `agents/kb-tools/` an earlier version installed.
- **An install parameter and its CLI flag are one change.** `just install` reaches the verb only
  through the flags `adjagent/cli.py` declares in `build_parser`, so a parameter added to
  `install()` alone ships a capability no recipe can ask for. The flag lands in the same change. The
  parameter's own tests do not catch the gap: a test calling `install(...)` proves the parameter
  works, never that anything can supply it — only a call through `main([...])` proves the flag
  reaches it, the shape `--with-kb` has.
- **The harness agents file changes by explicit act, in either direction.** Publish by hand: edit
  `adjagent/definitions/harness_agents_file.py`, then commit. Adopt with
  `just install-agents-file <dir> [harness]`, which replaces only the block between the `adjagent`
  marker lines and refuses while `adjagent/` has uncommitted changes. Your own rules go outside the
  markers, because inside is replaced on every install. Machine-local sections (an auth sandbox,
  host-specific paths) live outside the block in the live file and are never published.
- **Obviated code is deleted, not parked.** When a change makes code unnecessary, it goes in the
  same change — not commented out, not left unreferenced behind a "maybe someday", not kept as a
  second implementation nobody calls. Git holds it, and a commit message naming what replaced it is
  a better record than a dead module. The cost of keeping it is paid by everyone after: a reader
  can't tell live from vestigial, an agent reads it as current, and whoever reads the module next
  inherits the job of classifying a name nothing refers to. A plan for rebuilding it later is cheap
  and belongs in `ROADMAP_PLANS/`; the code itself is not.

## Planning and Execution

- **Partly-planned work that isn't ready to execute lives in `ROADMAP_PLANS/`, not in scratch.**
  `mad-design/` and the repository's other scratch trees are gitignored, so a plan parked there is
  one power-cycle from gone. A plan worth keeping moves to `ROADMAP_PLANS/`, which is tracked. It's
  good practice for such a plan to correspond to a `ROADMAP.md` item, but that is a habit, not a
  rule — nothing requires or checks it.
- **A dispatch names its seats before the tool call.** The acting message states the agent count
  and model. More than one seat at the family's highest tier waits for a go that names the count: a
  fan-out's cost shows only as the plan's usage moving, and by then it is spent.
- **The gate after a change is `just test-changed [base]`.** It runs only the test surfaces the
  change touches (the mapping lives in the justfile's `TEST_SURFACE_MAP`); bare `just test` is the
  full run. Cross-surface coupling is removed, not paid for by running unrelated surfaces.
- **`just render-diff [a] [b]` takes its two slots positionally and reports pairs, not spans.** Both
  slots are positional parameters with defaults: `just render-diff` compares `reference` against
  `latest`, and `just render-diff my-slot` compares `my-slot` against `latest`. A slot is a bare
  word — `a=reference` is read as the first slot's own name, so the run fails on a slot that does
  not exist. A file present on one side only is reported `Only in <dir>: <name>`, so there is no
  second file to hand `diff -u`: read it under the slot that holds it. A pair's changed spans come
  from `diff -u` on its own two files under `rendered/<slot>/`. The list is a footprint, not the
  change: `reference` holds what was accepted at the last `just retake-reference`, so a pair carries
  every change accepted since as well, and the pair of names says nothing about which of them one
  run made.
- **A checkpoint is not complete until the sweep has run.** `just sweep-python` enumerates what no
  single file can report — one concept with two implementations, one constant with two definitions
  — because a rule honoured completely inside one file is still broken across two. It emits
  candidates and never verdicts, so the run is not finished when it exits zero; it is finished when
  someone has read the list and said which pairs are one idea.
- **Every activated plan, wherever it lives, ends with a post-sprint review section.** A plan is
  activated when its execution is approved; its sprint is its execution steps. The section is the
  plan's last step before its commit and holds review, burn-down and remediation, each with its
  seat count and model, so approving the plan is the count-naming go the dispatch bullet above
  requires; each acting message still states count and model, and the main session dispatches.
  Remediation's count is set by the burn-down, and past one seat at the highest tier it takes its
  own go. A plan without the section is incomplete.
  - **Review.** Unless the plan names others, the reviewers are an architect and the coder seat for
    each language the change touches. The plan adds a security-reviewer when the change touches
    what writes, prunes or refuses in a consumer's tree (`adjagent/install.py`,
    `adjagent/agents_file.py`), and a tech-writer when `SPEC.md`, `ARCHITECTURE.md`,
    `CONVENTIONS.md` or `README.md` changed. Each reviewer's pre-task reading is THESIS.md,
    SPEC.md, ARCHITECTURE.md and CONVENTIONS.md; none gets the plan. Each gets the diff range and
    one sentence stating what the change is for. A review judges the change, its tests included,
    against the project's standards and its fitness for that purpose, not by re-deriving the
    implementation. A coder's report and the main session's own diff check are not independent
    review and do not substitute for it.
  - **The security brief is bounded.** It carries this scope verbatim, naming the surface:
    *Findings are limited to realistic misuse and failure of [surface] — data loss, a write outside
    its target, a bypassable refusal, an overwritten consumer file — by an operator and the files
    already in their tree. Each finding names a concrete failure on that surface; other adversaries
    and hardening beyond it are out of scope.* Asked open-endedly about security, a reviewer widens
    the threat model until every change looks unsafe; the bound keeps its findings actionable.
  - **Burn-down.** An architect synthesizes the findings into one burn-down plan: the reviewing
    architect, or one the plan names for synthesis alone when none reviews. The burn-down gets a
    prompt-engineer review, and revision from its findings, before it is dispatched.
  - **Remediation.** A fix pass works the burn-down; then `just test-changed` and
    `just sweep-python` re-run, and `just render-diff` where rendered output can change. Only then
    does the change land.
- **`just retake-reference` is run only after a content change is accepted.** It overwrites the
  baseline `just render-diff` compares against, so running it earlier erases the change from the
  next comparison.
- **A plan leaves `ROADMAP_PLANS/` when it is finished, abandoned or superseded — in the same
  change.** A superseding plan first absorbs every section, decision and piece of evidence it
  still relies on, stated as its own, and cites nothing in the plan it replaces; then the old plan
  is deleted. A plan still on disk reads as work waiting to be done.

## Adding Definitions

- **Where it goes.** One module in `adjagent/definitions/`; its existence is its enrollment, and
  nothing imports it by name. Definitions that share text and ship as a set share one module.
- **What it is called.** From the output path below the surface root, the folder as a prefix and each
  `/` and `-` read as `_`: `python_coder.py` for `agents/python-coder.md`. A module of a set is named
  for the set, not for one member's output path; no set is defined today.
  A skill's output path is `skills/<name>/SKILL.md`, and its fixed file name is no part of the
  module's name, so the module takes the skill's name alone: `kbase.py` for `skills/kbase/SKILL.md`.
  The harness agents file, which has no output path, is `harness_agents_file.py`.
- **What it sets.** `kind` is agent, document, command, skill or agents file; it decides the output
  root, the frontmatter and the required fields. `folder` is the path below the root for a nested
  output and empty otherwise; a skill refuses it, its directory being its name. A skill's
  `description` is required and is all the model sees before it loads the skill; its `files` are the
  supporting files, each a kebab path ending `.md` below the skill's directory, opened by the comment
  banner. A definition's output paths are unique — its own, and each supporting file's.
- **A skill's reference carries only what its tool's offered surface does not.** A session sees the
  server instructions, each tool's description and its parameter descriptions, and each resource's
  text once it reads it — the listing carries a resource's uri, name and mimeType only — so a
  reference that restates one is a second source for text its consumer already reads, and the two
  drift the moment either moves. The offered surface is the one `justfile`'s `KBASE_VERSION` pins, so
  a bump of that pin is the moment to re-read the references. What a table can hold is guarded —
  `tests/test_kbase_retired_forms.py` holds the retired forms — and nothing checks the rest for
  sync. Prose only the tool's README carries is not offered to a session, and stays in the reference.
- **What `render-diff` shows.** The first `just render-diff` after adding a definition shows its
  whole file — for a skill, each of its files — as `Only in`.
- **Where the rest is.** The composition model is in ARCHITECTURE.md; the `adjagent` package and
  module docstrings hold the mechanism.
