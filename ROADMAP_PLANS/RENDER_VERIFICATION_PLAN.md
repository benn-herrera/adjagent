# RENDER_VERIFICATION_PLAN.md — no render tree is a baseline

**Paths** are repository-root-relative.

**Seats.** **PC** python-coder. **SH** shell-dsl-coder, for the justfile. **TW** tech-writer, for
`SPEC.md`, `ARCHITECTURE.md`, `README.md` and `ROADMAP.md`. **PE** prompt-engineer, for
`CONVENTIONS.md` and template commentary — model-facing text is its seat, not TW's.

**A row's `What` column marks a decision it must make with `DECIDE:`.** Bold is ordinary emphasis
everywhere, including there. A decision is recorded in the row's handoff report; nothing commits.

**What a dispatch brief carries**: this header, the whole RULED section, the standing rules, the
row, and the surface-table entries the row names. Not the narrative sections, not Order. The
contract documents and the code are read from the repository — this list is the brief's contents,
not a limit on what a row may consult.

## What produced this

`rendered/` is a single directory that `just generate` overwrites and `just check` diffs against.
Because `generate` destroys the only baseline `check` has, running the two in that order reports
clean against the state just written, and the defence is operator discipline rather than anything
structural. `rendered/` is gitignored besides, so from a clean checkout there is no baseline at all.

Around that sit two test classes verifying the two tuning rungs, one asserting a hardcoded
population count. A one-line command template added in `25dfb7a` failed it, and its only repair is
pasting the observed value into the expected one — a procedure that cannot tell a correct new value
from a regression.

**The test applied to every piece: would a diff between two render trees surface this?** Everything
answers yes except one thing — a *new* output landing with no pin site at all, which appears only
in the newer tree with nothing saying it should have carried one. That is the single residue, and
`assert_tiered`'s own docstring already names the class while explicitly declining this half of it.

## RULED — settled; a row that reopens one has misread the plan

1. **No render tree is ever a baseline.** Every tree is rebuilt on demand and no target reads an
   existing render directory as input. The `RENDERED` constant goes and `rendered/`
   stops being a tree, becoming the root the slots sit under — so no privileged tree
   survives to be mistaken for one.

2. **Two slots, and the default never overwrites the reference.** `just render` writes
   `rendered/latest/`; `rendered/reference/` is written only by an invocation that asks for one. A
   baseline is destroyed by a deliberate act or not at all, which is what makes a comparison
   structurally non-vacuous rather than carefully sequenced.

   **The slots live under `rendered/` in the repository root, not under `.claude-temp/`** — they are
   examinable output a person opens, not scratch a row clears at handoff. `rendered/` is already gitignored and stays so.
   Only the extracted source a cross-revision render works from stays scratch, at
   `.claude-temp/src/<sha>/`, being a git checkout rather than a render.

3. **A comparison's flag sets are fixed by the invocation that runs it**, never recalled by an
   operator between two invocations. Where both sides share a tuning, one flag set is supplied
   once; where the comparison is *about* a tuning difference, the flags that produced each slot are
   recorded with it. A tree rendered under one triple compared against a tree rendered under
   another unstated one is the failure this makes unrepresentable.

4. **The `render-diff*` targets report and exit zero on a difference.** A gate here would be claiming a verdict
   about whether an intended change was intended, and a target that fails on every deliberate edit
   is one operators learn to ignore — the argument `CONVENTIONS.md` already makes for the
   duplication sweeps. A `render-diff*` target exits non-zero only when a comparison could not be made.

5. **The mechanical gates over the real definition set are render-time refusals in `gen-defs.py`**,
   which fire on every render and every install, plus one smoke test proving the shipped families'
   overlay paths still run. **No runner recipe's own shell asserts a count, a census, or an expected
   string over that set.**

6. **Exhaustiveness over a tuning is not re-verified.** Pin text has one source and `assert_tiered`
   forbids the only escape from it, so a census over the rendered set re-checks a composition of
   two facts each already guarded at render. If that reasoning is ever doubted the answer is a
   third render-time refusal, never a count.

7. **`check` retires entirely** — the verb, its flags, its tests. Its verdicts are a diff's
   restatements except `ORPHAN`, which is an install concern: a target directory holding a file
   we own and no longer ship is pruned by the install that owns it, per `SPEC.md`'s existing rule
   that a banner is what makes a file ours. **The banner-reading machinery is install's write path
   and is out of scope here** — no row touches it.

8. **A fixture is in-spec or it is not a fixture.** A partial fixture is legitimate — frontmatter
   alone, exercising the frontmatter parser. An *illegal* one is not: it asserts behaviour over a
   state the product cannot produce. A fixture that a new render-time refusal rejects is a fixture
   that was already wrong.

## Standing rules — on every row, not restated per row

1. Code citations are by symbol, never by line. A row re-greps every symbol it is about to change
   and reports any that no longer resolves rather than improvising a referent.
2. Root `just test` green at handoff. Scratch under `.claude-temp/`. Never `/tmp`. Do not commit.
3. **A row that deletes machinery states what the deleted thing caught** and where that coverage
   now comes from, or that it is accepted as lost. A deletion justified only by something else
   looking similar has not been argued.
4. **At every row's handoff a definition still renders and installs** — demonstrated by running it,
   not asserted. This plan rewrites the machinery other work runs through.
5. **A model-name spelling is the harness's, not this repository's.** Where a row touches text
   asserting otherwise, it scopes the claim rather than restating it: Claude Code is the only
   harness today and `ROADMAP.md`'s multi-harness item plans others.

## The surface

| Where | What it is | Row |
|---|---|---|
| `gen-defs.py` — `assert_tiered` | the render-time refusal for a pin site resolving no tier. Its docstring names the uncovered class — a literal pin "costs the definition its model scope and nothing else, which is a loss no diff and no check can show" — and then states that an output with no pin site is untouched by it, which S2 reverses | S1, S2 |
| `gen-defs.py` — `assert_no_residual_markers` | the sibling render-time refusal; the shape a new guard follows, and it fires over fixtures today | S2 |
| `gen-defs.py` — `frontmatter_pin`, `tuning_claim`, `banner_body` | how a pin site and a tuning claim are read off a rendered output | S2 |
| `gen-defs.py` — the module docstring's usage block, and the `--model-pin-map` help text | two sites asserting pin text is "always in the claude model namespace" | S2 |
| `gen-defs.py` — `check_banner_claims`, the check pass, `--no-diff` | the `check` verb's implementation, retiring whole | S3, S4 |
| `templates/family/claude.toml`, `templates/family/gemma-4.toml` | **the claude family's members are the pin map's values** — `fable`/`opus`/`sonnet`/`haiku` — so "no member name appears in a rendered body" is false for it by construction and true for gemma-4 | S2 |
| `justfile` — `RENDERED`, `generate`, `check`, `_render-rung`, `_check-rung`, `generate-floor`, `check-floor`, `generate-stock`, `check-stock` | the apparatus this plan replaces, with the comment blocks arguing for the render/check split | S3 |
| `justfile` — `install`, and `render-claim-graph` | `install` is the entry point present in every revision, which is what a cross-revision render goes through; `render-claim-graph` is an unrelated neighbour a new `render` target sits beside | S3 |
| `tests/test_gen_defs.py` — `TestFloorRung`, `TestStockRung` | the two rung classes. `TestStockRung`'s member-name assertion is gemma-only for the reason above | S2, S4 |
| `tests/test_gen_defs.py` — `TestLiteralPinGuard.test_an_output_with_no_pin_site_renders` | asserts the exact negation of S2's guard, from `NO_PIN_SITE` | S2 |
| `tests/test_gen_defs.py` — the agents-surface fixtures carrying no `model:` line | roughly fifteen, across the surface-map, selection, chunk, overlay and nesting classes. Per RULED 8 these are out-of-spec and S2 corrects them | S2 |
| `tests/test_gen_defs.py` — `TestShippedFamilyFiles`, `TestLiteralPinGuard` | four further tests in this business, one a byte-for-byte second copy of `templates/family/gemma-4.toml`'s `[tiers]` table | S4 |
| `SPEC.md` — Generated-Definition Integrity, and Deployed Surfaces | the first states the guarantee over deployed surfaces of any tree, render trees included; **the second already partitions outputs carrying dispatch keys from those carrying a frontmatter block empty of them**, which is where an exemption may already live | S1 |
| `ARCHITECTURE.md` — Sanctioned Invocation | names `just generate`, `just check` and `just install` as the sole sanctioned entry points, which every new target falsifies until it is listed | S5 |
| `ARCHITECTURE.md` — *The Two Checks*, and the `rendered/` mention | one check after this plan, and no `rendered/` | S5 |
| `README.md` — the layout listing, the install/generate sentence, the working-sequence paragraph, and the bolded *"`just check` is the refactor instrument, and the order matters"* | the largest human-facing statement of the discipline RULED 1 abolishes | S5 |
| `ROADMAP.md` — *(STICKY) Periodic load-bearing-ness pruning pass*, and *Claude Code release reconciliation* | the first says "Byte-level checks (`just check`) exist today"; the second names `check-floor` / `check-stock` | S5 |
| `kb_tools/ROADMAP.md` — the `generate-stock` sentence | "`just generate-stock` renders at the `gemma-4` rung, so 'does this survive the target tier' is a run" | S5 |
| `CONVENTIONS.md` — the adding-templates line | "`just generate` creates the output and banners it" | S6 |
| `liaison_tools/CONVENTIONS.md` — the check sentence | "`just check` covers rendered definitions, not this package" | S6 |
| `templates/shared-chunks.toml` — the maintainer comment naming `just generate` | model-facing commentary | S6 |
| `.gitignore` — the `rendered/` entry | **unchanged**: it already covers the slots beneath it | S3 |

## Rows

| Row | What | Who | Blocked on | Done when |
|---|---|---|---|---|
| **S1** | SPEC states the pin-site requirement, which S2 enforces: a dispatchable agent definition declares a tier-resolving pin site. The exemption is the `agents/mad/` prose — the participant contract is forbidden a pin and a methodology topic is prose a referee reads, not a seat something dispatches. `DECIDE:` which section it attaches to, given that **Deployed Surfaces already partitions outputs by whether they carry dispatch keys** — the exemption may already be expressed there, in which case this attaches rather than invents. `DECIDE:` whether the exemption is stated as a subtree or as a property of the output. Per standing rule 5, say nothing about how a pin's text is spelled — that is the harness's namespace, not this guarantee's | TW | — | The sentence added, with the exemption stated so a reader can tell which outputs it covers without consulting the template set. The two decisions recorded with their reasons. No behaviour changes |
| **S2** | A pin-site refusal beside the existing render-time ones: an agents-surface output with no pin site is refused, exempt where S1's landed sentence says it is — **read that sentence rather than restating it**. This closes the half `assert_tiered` explicitly declines, and its docstring's stance that a missing pin site is "a property of its type" moves with it. Per RULED 8, the roughly fifteen agents-surface fixtures carrying no `model:` line are out-of-spec and are corrected; `TestLiteralPinGuard.test_an_output_with_no_pin_site_renders` asserts this guard's negation and is re-pointed or retired with its reason. Also add a shipped-tuning smoke test: every shipped family renders the real template set without raising, and for a family whose members are **disjoint from the pin map's values** — gemma-4, never claude, whose members *are* those values — no member name appears in any `banner_body`. **Assert the disjointness rather than assuming it**, so a family file that later collides fails a precondition instead of an assertion. And scope the two "claude model namespace" docstring claims per standing rule 5 | PC | S1 | An agents template with no pin site is refused at render **with a message naming the template**, demonstrated. Both shipped families render the real template set under `just test`. The disjointness precondition fails loudly if violated — demonstrate with a temporary family file. Every corrected fixture is corrected because it was out-of-spec, stated per fixture in one line |
| **S3** | The render and diff targets, and the retirement of `generate` and `check`. `render [slug] *args` renders the full install product into `rendered/<slug>/`, **slug defaulting to `latest`**; `render reference` writes `rendered/reference/`, which nothing else writes. `render-revision <rev> [slug]` extracts `rev` with `git archive` into a fresh `.claude-temp/src/<sha>/` — removed first if present, never reused — and renders it **through that revision's own `just install`**, the one sanctioned entry point present in every revision including those predating this row; slug defaults to `reference`. `render-diff [a] [b]` diffs two slots, defaulting `reference` against `latest`. `render-diff-floor` and `render-diff-stock` are one-line delegations pinning the rungs' flag sets so neither is ever run from recalled flags. Delete `RENDERED`, `generate`, `check`, both rung pairs, `_render-rung`, `_check-rung`, their comment blocks, leaving the `rendered/` gitignore entry alone, since it already covers the slots. `DECIDE:` how each slot records the flags that produced it, per RULED 3. **Do not** cache a slot across runs, copy an existing directory into one, grep a tree for expected strings, or translate a rung assertion into shell | SH | S2 | From a clean checkout with no prior render, `render-revision` then `render` then `diff` produces a comparison — no target takes a previously-produced tree as input. `just render` twice does not touch the reference slot, demonstrated. A diff target exits zero when trees differ and non-zero only when a comparison could not be made — `diff(1)` status 2, a failed extraction, a render that raised. **`rendered/` holds slots and nothing else** — no `agents/` or `commands/` directly beneath it, so no tree sits where a baseline used to. A definition still renders and installs |
| **S4** | Delete what the diff and S2's guards now cover: `TestFloorRung` and `TestStockRung` whole; `TestShippedFamilyFiles`'s total-tier-map, stock-at-every-tier and gemma-spellings tests — the last a second copy of `templates/family/gemma-4.toml`'s `[tiers]`; `TestLiteralPinGuard`'s whole-tree-renders test, whose successor is S2's smoke test and not a manual invocation. `--no-diff` goes with `check`: its argparse declaration, its call site, its line in the module docstring's usage block, and its tests. Per standing rule 3, **state per deletion what it caught and where that coverage now comes from** — a diff for most, S2's guards for the pin cases, RULED 6 for the exhaustiveness ones, and *accepted as lost* where that is the answer | PC | S2, S3 | Each deletion justified in one line. **Adding a template requires no edit to any test, count or expected value** — demonstrated by adding one under `.claude-temp/`, rendering, and showing the suite unmoved. Root `just test` green |
| **S5** | The human-facing documents follow what landed. `ARCHITECTURE.md`'s Sanctioned Invocation list, which every new target falsifies until it names them; its *The Two Checks* section, now one check; its `rendered/` mention. `README.md`'s layout listing, its install/generate sentence, its working-sequence paragraph, and the bolded refactor-instrument paragraph whose whole content is the discipline RULED 1 abolishes. `ROADMAP.md`'s two items naming `just check` and the rung targets — **cited by title, not by number**, since an item closing renumbers the list. `kb_tools/ROADMAP.md`'s `generate-stock` sentence | TW | S3 | Each site corrected against the landed targets. A reader of `README.md` can follow the render-reference-then-compare sequence without consulting the justfile. No document names a deleted target |
| **S6** | The model-facing documents follow. `CONVENTIONS.md`'s adding-templates line naming `just generate`; `liaison_tools/CONVENTIONS.md`'s sentence scoping `just check`; `templates/shared-chunks.toml`'s maintainer comment naming `just generate`. **`CONVENTIONS.md` is the prompt-engineer's seat, not the tech-writer's** — house rules whose reader is a model | PE | S3 | Each corrected. No model-facing document names a deleted target |

## Out of scope

**Install's write path** — the banner reading, the write-safety table, backup branches, and the
pruning of files we own and no longer ship. That last is `ROADMAP.md`'s atomic-install item, and it
is where `check`'s one non-redundant verdict goes.

**A deleted template going unremarked** unless someone runs a diff. Nothing catches it today
either. Accepted: deleting a template is a deliberate edit whose commit diff shows it.

## Order

**S1 first** — it is the guarantee S2 enforces, and SPEC leads a behaviour change.

**S2 second.** Its guards must exist before S4 deletes what covers those cases, or the tree spends
a commit with neither.

**S3 third**, and it is the largest: the runner is swapped in one row, because any split leaves a
commit with no render path.

**S4 after S3**, since several deletions are justified by targets S3 creates.

**S5 and S6 last**, describing what landed rather than what was planned. They share no file and may
run concurrently.
