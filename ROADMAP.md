# ROADMAP – devpro

Future intent only. Not part of the contract doc set; not handed to coding dispatches.
A finished item leaves nothing. Do not mark it as done and let it persist. Just remove it.

## Items

1. **(STICKY) Periodic load-bearing-ness pruning pass** over definition clauses, across model
   generations: apply strip-first-observe-patch (`docs/development.md`, "Authoring a family")
   on a cadence, using behavioral probe sets as the instrument. Byte-level instruments exist today —
   `just render-diff` between two render slots, and the render-property assertions in
   `tests/test_devpro.py` (ARCHITECTURE.md, Why There Is No Verification Verb);
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
   `devpro/definitions/kbase.py`) say only to restart or reconnect the server. The `reload_rule`
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

7. **Mage has no guardrail.** `devpro/harnesses/mage.py` sets `guardrail=None` and SPEC
   `shipped-files.md` says mage ships none, so a mage install's `.index/` protection rests on
   kbase's prose instruction alone. Check whether mage's plugin format carries a hook; if it does
   not, record the gap in SPEC.

8. **`just test` does not hold the own-paragraph rule for module text beside a clause.**
   `PROJECT_DOCS/CONVENTIONS/adding-definitions/clause-paragraphs.md` says `just test` holds none of
   it; `devtools/clause_join_sites.py` (`just clause-join-sites`) reports join sites, but no test
   fails on a new one.

9. **A shared sentence written out inside a longer paragraph is not checked for double delivery.**
    `tests/test_devpro.py` `_double_paragraphs` compares whole prose units and never splits them
    into sentences.

10. **The double-delivery check fills only the claude family under the claude harness.**
    `tests/test_devpro.py` `_prompts` fills with `_CLAUDE_RENDER`, so family overlay text and other
    harnesses' text go unchecked.

11. **Placeholder spelling.** The `@!<namespace>-<key>!@` spelling (`devpro/vocabulary.py`,
    `hole`) dates from before definition bodies were plain Python strings. Reconsider whether a
    plainer spelling now serves.

12. **The cold-read script is unreliable under opencode.** `devpro/development-tools/cold-read.sh`
    runs each read in a fresh directory, and in a directory where opencode's background service has
    never run a session, models a provider plugin discovers (`opencode-models-discovery`) are
    reported "Model unavailable", even after `opencode models` runs there; the run fails or falls
    back to opencode's free models. Whether the composed agent file's `"*": deny` blocks every tool
    is therefore unconfirmed by a live run.

13. **No TypeScript type check.** `devpro/harnesses/resources/opencode/index.ts`, `guardrail.ts`
    and the `tests/*.ts` runners are never type-checked: there is no `tsconfig` and no recipe. A
    recipe needs a declaration stub for `@opencode/plugin`.

14. **No shell lint.** No recipe runs `shellcheck` over `devtools/scripts/*.sh` or
    `devpro/development-tools/cold-read.sh`.

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

17. **Pi harness support** add ability to install as "Pi Package"
    See [pi-harness](https://github.com/wangmiaozero/pi-harness)

18. **Codex CLI harness support** add ability to install as codex plugin

19. **A design's final form is a SPEC delta.** In the `development` skill, a design ends as a
    delta to SPEC: each requirement an entry naming the SPEC leaf it changes and the statement it
    makes there, in SPEC's voice, or marked as not consumer-facing. The delta outlives the
    transition to a plan, which cites it rather than restating it. A requirement changed or found
    during the plan is entered in the delta when the user decides it. At landing the delta is
    applied to SPEC and deleted; ARCHITECTURE is updated from the plan's structural decisions, not
    a copy of its steps. The post-plan reviewers are given the delta. Readiness becomes visible: a
    design is offered for acceptance when every requirement is a delta entry and no open question
    remains, which the kanban board can show as the design's prose turning into delta cards.
    Touches the skill's rules that delete the design in the plan's commit, that a plan cites no
    design, and that SPEC moves in the change that motivates it. Undecided: whether a plan with no
    consumer-facing change carries an empty delta, and whether the delta replaces the design or is
    its final section.

20. **Leaner README integration instructions.** `README.md`'s Requirements and Quick Start carry
    more weight than a first install needs, so integrating looks less convenient than it is. Revamp
    them to be leaner. The sections before them, which give the reader a reason to install, stay
    first.
