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

2. **Legacy project comprehension skill**: how a session enters a brownfield project with known
   and unknown issues, builds familiarity with it, and begins repair work. The target case is
   projects whose debt accumulated through ungoverned agentic development. It follows the
   development-process skill and should not assume that skill's workflow is already in place.

3. **State the minimum Claude Code version that loads a plugin from a project's skills directory.**
   Under claude the set is a plugin at `.claude/skills/<plugin>/`. No document states the Claude Code
   version that loads one, and README.md's Requirements section names none; the version is not yet
   established from any source.

4. **Give the kbase router's not-offered branch the plugin reload remedy.** Under claude the
   plugin's `kbase` tools appear after a fresh install only once the plugins are reloaded. The "A
   path" branch of the router and `references/installing.md` (both in
   `adjagent/definitions/kbase.py`) say only to restart or reconnect the server. The `reload_rule`
   hole names agents, not tools, so reusing it there would misdirect the model; the remedy needs a
   harness hole of its own.

5. **Verify the opencode guardrail's tool names against the opencode runner.** Which tool names
   reach `execute.before` is unverified: only `patch` is matched, not `apply_patch`; a `list` tool
   taking `path` is not handled; the `shell` alias is accepted but never sent. Probe the runner,
   accept every name the hook receives, and add a case row for each (`guardrail.ts` `shellTools`
   and its tool `switch`; `tests/test_guardrail.py` `_OPENCODE_ONLY_TOOLS`).

6. **The guardrails hard-code kbase's private record names.** The Grep/Glob judgement depends on
   `nodes.yaml`, `edges.yaml` and `format.yaml` (`guardrail.pl` `@kb_records`, `guardrail.ts`
   `kbRecords`), so a record file a later kbase adds passes silently. Passing a Grep/Glob rooted in
   `kb-root/` only when its filter's last segment ends in `.md` drops both lists; it is a behaviour
   change to both scripts and the case table together.

7. **Mage has no guardrail.** `adjagent/harnesses/mage.py` sets `guardrail=None` and SPEC
   `shipped-files.md` says mage ships none, so a mage install's `.index/` protection rests on
   kbase's prose instruction alone. Check whether mage's plugin format carries a hook; if it does
   not, record the gap in SPEC.

8. **`just test` does not hold the own-paragraph rule for module text beside a clause.**
   `PROJECT_DOCS/CONVENTIONS/adding-definitions/clause-paragraphs.md` says `just test` holds none of
   it; `devtools/clause_join_sites.py` (`just clause-join-sites`) reports join sites, but no test
   fails on a new one.

9. **A shared sentence written out inside a longer paragraph is not checked for double delivery.**
    `tests/test_adjagent.py` `_double_paragraphs` compares whole prose units and never splits them
    into sentences.

10. **The double-delivery check fills only the claude family under the claude harness.**
    `tests/test_adjagent.py` `_prompts` fills with `_CLAUDE_RENDER`, so family overlay text and other
    harnesses' text go unchecked.

11. **Placeholder spelling.** The `@!<namespace>-<key>!@` spelling (`adjagent/vocabulary.py`,
    `hole`) dates from before definition bodies were plain Python strings. Reconsider whether a
    plainer spelling now serves.

12. **The cold-read script is unreliable under opencode.** `adjagent/development-tools/cold-read.sh`
    runs each read in a fresh directory, and in a directory where opencode's background service has
    never run a session, models a provider plugin discovers (`opencode-models-discovery`) are
    reported "Model unavailable", even after `opencode models` runs there; the run fails or falls
    back to opencode's free models. Whether the composed agent file's `"*": deny` blocks every tool
    is therefore unconfirmed by a live run.

13. **No TypeScript type check.** `adjagent/harnesses/resources/opencode/index.ts`, `guardrail.ts`
    and the `tests/*.ts` runners are never type-checked: there is no `tsconfig` and no recipe. A
    recipe needs a declaration stub for `@opencode/plugin`.

14. **No shell lint.** No recipe runs `shellcheck` over `devtools/scripts/*.sh` or
    `adjagent/development-tools/cold-read.sh`.

15. **Verify the opencode plugin entry against each opencode release.** `index.ts` is written for
    opencode v2.2.6 (SPEC `deployed-surfaces/shipped-files.md`) and tested only against a stub of
    that version's plugin API; nothing re-checks it when opencode changes.

16. **Change-case analysis run by agents.** A skill, or an addition to the `development` skill,
    that performs change-case analysis in the SAAM tradition: enumerate plausible future changes to
    a system, trace each through the design to every module and contract it touches, and judge the
    architecture by how far those changes spread. Uses: periodic re-review of a long-lived project,
    evaluation of a brownfield project, and evaluation of a large new architecture. Performed by
    people, the method consumed senior engineering attention and found little where those engineers
    had already designed against the failures it detects. Agents make it cheaper to run, and their
    designs produce those failures: an agent tends to build each piece as the typical form of
    something it resembles, then extend it toward a full implementation of that thing, which the
    project does not want, and the weaknesses of the aggregate are the ones change-case analysis
    exposes. The process may still be heavy, and it asks for speculation about future change, which
    agents do poorly; partially implementing a change case, so the trace runs through code that
    exists rather than predicted code, is one possible workaround. Brownfield evaluation overlaps
    item 2, which this would serve rather than absorb. Separate skill or `development` addition is
    undecided.

17. **Rename adjagent to devpro. devpro is the default installed plugin.**
    This change will be a bump to version 0.17.0.
    The tool, its Python package, its CLI command and its repository take the name devpro. 
    `devpro install <target>` installs the devpro
    plugin; `--plugin=kbase` selects kbase, and `--plugin=devpro`, the default, is accepted. SPEC
    `deployed-surfaces/plugins.md` ("The plugin argument has no default") and `package-and-command.md`
    change with it. The old name is carried into consumer projects by the generated banner the install
    recognizes its own files by, the agents-file marker line, the runner's `ADJAGENT_VER`, the
    `adjagent` skill, and pinned git URLs; with release tags out, each needs a compatibility rule
    (the install accepting the old banner and marker for a stated window) and a migration note in
    `docs/installing.md`. Whether "devpro" collides with an existing project or mark is unchecked.
    
18. **Change commit message attribution postscript**
    This change targets release 0.17.0 (goes out with #17)
    The commit message postscript, separated from the rest of the commit message by a blank line, will read:
    `ai assisted by [devpro](https://github.com/benn-herrera/devpro). submitter takes full responsibility.`
    Because this plugin supports multiple harnesses the harness and model will not be mentioned either
    in this line or in a separate acknowledgement. they don't need our marketing assistance and that falls
    under the rubric of 'submitter takes full responsibility.'
