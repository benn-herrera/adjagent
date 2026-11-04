# ROADMAP – Adjagent

Future intent only. Not part of the contract doc set; not handed to coding dispatches.

## List conventions

- **A finished item leaves nothing.** An item that is done or dropped is deleted outright and the
  list renumbers behind it, so a reference by number is verified against this file rather than
  trusted. A `(KEEP LAST)` item is last in this file, not merely last to execute: a new item is
  appended above it, and the `(KEEP LAST)` entry takes the new highest number.

## Items

1. **(STICKY) Periodic load-bearing-ness pruning pass** over definition clauses, across model
   generations: apply strip-first-observe-patch (README.md, "Variants and platform compatibility")
   on a cadence, using behavioral probe sets as the instrument. Byte-level instruments exist today —
   `just render-diff` between two render slots, and the render-property assertions in
   `tests/test_adjagent.py` (ARCHITECTURE.md, Why There Is No Verification Verb);
   behavioral ones do not yet.

2. **Two skills that drive tools, and the diced-project-docs clause.** Release 0.13.1:
   - **An adjagent skill** for sessions in a consuming project: when it applies (install, update,
     global setup, a generated file needing change), the install command and its global opt-in
     flags, `adjagent --help` for the rest, and the rule that a generated file is never edited
     locally — a local need goes in the project's CONVENTIONS.md, a change to adjagent.
   - **A docdicer skill**, default set, every harness. The skill: what dicing buys (loading only
     the leaves a task needs), when (a project's contract documents; a plan or design too large to
     read whole), when to undice (a diced plan or design that has shrunk back to readable size, or
     one that needs reading or reviewing whole: `docdicer undice` writes the tree back out as one
     document), offer and run `<harness-dir>/skills/docdicer/tools/docdicer --install` at the
     user's direction, then `docdicer --help`; no command list. `tools/docdicer` (POSIX sh) checks
     for `python3` 3.9 or later and names the remedy where it is missing (macOS: `brew install
     python` or `xcode-select --install`; Linux: the distribution's `python3`), installs into
     `tools/.venv` with `pip install --upgrade` from `git+https://github.com/benn-herrera/docdicer@v0.7.1`
     (the version the skill is written against) on `--install`, says how to install when absent, and otherwise passes its arguments through;
     `tools/.gitignore` holds `.venv/`. An adjagent install that finds `tools/.venv` before it
     replaces the package re-runs `--install` after, so docdicer stays matched to the skill; a
     failure there is reported and does not fail the install. docdicer's own pitfalls (a bare `§N`
     linked to the wrong volume) are docdicer issues, not skill text.
   - **The diced-project-docs clause** in the harness agents file: a project whose contract
     documents are trees under `PROJECT_DOCS/` reads the volume entry points and opens the leaves a
     question needs, and the rules naming THESIS.md, SPEC.md, ARCHITECTURE.md or CONVENTIONS.md
     apply to those trees. `clauses.PROJECT_DOCS_SETUP` defers to it. A sentence where plans are
     authored: a plan or design too large to read whole is diced.

3. **Follow-ups from the 0.12.7 review**, unscheduled — `ROADMAP_PLANS/review-0.12.7-followups.md`.

4. **(KEEP LAST) Definition namespace prefix** (`just install --name-prefix=aa- <project>`):
   installs the agent and command definitions under a prefixed namespace so the set coexists with
   an existing fleet — generic names (`python-coder.md`) are the collision surface; the tool
   packages are self-namespaced and stay bare. Default empty renders today's bytes. Requires a
   render pass substituting every cross-reference site (dispatch names, slash-command names in
   prose) with a lint against bare fleet names. Nothing outside the definition text
   names an agent, so the rendered prose is the whole substitution set and no runtime route has to
   carry the prefix. The harness agents file (`adjagent/definitions/harness_agents_file.py`) is in
   it, so agent references inside that file — the prompt-engineer review rule, any seat named by
   the working preferences — render with the prefix applied at install.
