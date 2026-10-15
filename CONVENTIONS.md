# CONVENTIONS – Adjagent

House rules and project-specific traps only. Doc-structure conventions and general engineering ethos
live in operator config (the harness agents file, `adjagent/definitions/harness_agents_file.py`),
not here.

- **A definition module holds nothing but imports, string constants and `DEFINITIONS`.** It reads
  top to bottom as the file it renders. `just test` fails on any other top-level statement or call.
- **Text two definitions share byte for byte is one constant**, in `adjagent/clauses.py`, or in a
  group module's private constants when only that set shares it. A definition never pastes shared
  text or a paraphrase of it; `just test` fails on a paragraph two outputs write out.
  - **A private constant cannot name `clauses.*`.** Shared text that holds a harness string takes a
    hole, filled at the call site in the body.
- **`just retake-reference` is run only after a content change is accepted.** It overwrites the
  baseline `just render-diff` compares against, so running it earlier erases the change from the
  next comparison.
- **A checkpoint is not complete until the sweep has run.** `just sweep-python` enumerates what no
  single file can report — one concept with two implementations, one constant with two definitions
  — because a rule honoured completely inside one file is still broken across two. It emits
  candidates and never verdicts, so the run is not finished when it exits zero; it is finished when
  someone has read the list and said which pairs are one idea.
- **The gate after a change is `just test-changed [base]`.** It runs only the test surfaces the
  change touches (the mapping lives in the justfile's `TEST_SURFACE_MAP`); bare `just test` is the
  full run. Cross-surface coupling is either removed or explicitly accepted as a risk — never paid
  for by running unrelated surfaces. The accepted exception today:
  `kb_tools/tests/test_kb_driver_head.py` runs the real generator install, so a generator change can
  break it unnoticed until the `kb_tools` surface next runs.
- **Never comment in a rendered body.** A definition's body, and every constant it interpolates,
  becomes an agent's system prompt; maintainer commentary there ships into every dispatch and is
  read by every seat. A Python `#` comment above a constant is not in the string and is the place
  for a note the next editor needs.
- **An untracked file under `.claude/`, `.opencode/` or `rendered/` is render or install output.**
  Its source is a definition module under `adjagent/definitions/` or a module at the repository
  root (`liaison_tools/`, `kb_tools/`), and the next install overwrites the copy. Before an edit
  brief names a path, `git ls-files <path>` settles which it is, and the brief names the source.
  Running definitions point at the copy, which is how a brief comes to name it.
- **A dispatch names its seats before the tool call.** The acting message states the agent count
  and model. More than one seat at the family's highest tier waits for a go that names the count: a
  fan-out's cost shows only as the plan's usage moving, and by then it is spent.
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
  can't tell live from vestigial, an agent reads it as current, and
  `tests/test_orphan_name_sweep.py` makes every unreferenced module-level name someone's problem to
  classify. A plan for rebuilding it later is cheap and belongs in `ROADMAP_PLANS/`; the code itself
  is not.
- **Partly-planned work that isn't ready to execute lives in `ROADMAP_PLANS/`, not in scratch.**
  `mad-design/` and the repository's other scratch trees are gitignored, so a plan parked there is
  one power-cycle from gone. A plan worth keeping moves to `ROADMAP_PLANS/`, which is tracked. It's
  good practice for such a plan to correspond to a `ROADMAP.md` item, but that is a habit, not a
  rule — nothing requires or checks it.
  - **A plan leaves `ROADMAP_PLANS/` when it is finished, abandoned or superseded — in the same
    change.** A superseding plan first absorbs every section, decision and piece of evidence it
    still relies on, stated as its own, and cites nothing in the plan it replaces; then the old plan
    is deleted. A plan still on disk reads as work waiting to be done.

## Adding Definitions

- **Where it goes.** One module in `adjagent/definitions/`; its existence is its enrollment, and
  nothing imports it by name. Definitions that share text and ship as a set share one module.
- **What it is called.** From the output path below `agents/` or `commands/`, the folder as a
  prefix and each `/` and `-` read as `_`: `python_coder.py` for `agents/python-coder.md`,
  `mad_design_topics.py` for `agents/mad/design-topics/*.md`. A module of a set is named for the
  set (`mad_referees.py`). The harness agents file, which has no output path, is
  `harness_agents_file.py`.
- **What it sets.** `kind` is agent, document, command or agents file; it decides the output root,
  the frontmatter and the required fields. `folder` is the path below the root for a nested output
  and empty otherwise. Output paths, not names, are unique.
- **What `render-diff` shows.** The first `just render-diff` after adding a definition shows its
  whole file as `Only in`.
- **Where the rest is.** The composition model is in ARCHITECTURE.md; the `adjagent` package and
  module docstrings hold the mechanism.
