"""mad-design-referee: the referee of a multi-model debate design."""

from adjagent.definition import Definition
from adjagent.section import Prose
from adjagent.sections.mad import (
    DispatchMechanism,
    DocumentFormat,
    FinalDocumentFormat,
    GateMetaRules,
    IndependentPhase,
    InitialAlignment,
    Mode,
    OutputPhase,
    RefereeInvocation,
    RefereeRole,
    RefereeSeats,
    RoundDispatch,
    RoundGate,
    RunFileSystem,
    SeatRoster,
    SessionStateFormat,
)
from adjagent.vocabulary import ALL

_MODE = Mode(
    name="design",
    run_dir="mad-design/[design-name]",
    gate="convergence",
    seat="participant",
    initial="proposal",
    aggregate="initial-proposals.md",
    final="SOLUTION.md",
    state="design-session-state.md",
    agreement="convergence",
    outcome="convergence",
)

_SIBLING = r"""This is the **design** referee — for construction and problem-solving. It is the sibling of
`mad-review-referee` (review and critique). The two referees draw seats from the same participant
pool and share the same alignment assessor (`mad-alignment-assessor`); the topic file determines
whether participants act in critical-review mode or constructive-proposal mode. If the artifact
under debate already exists and the goal is to find flaws in it, use `mad-review-referee`. If the
artifact does not yet exist and the goal is to produce it, use this referee."""

_PROPOSERS = r"""In design mode, treat the seats functionally as Proposers — Phase 1 produces an independent
end-to-end proposal (a derivation, a design, a construction); subsequent rounds are adversarial
defense and refinement."""

# The `sed` range opens on line 1 and searches for its end pattern from line 2, so the two identical
# delimiters cannot collide, and it needs no line constant: a header that grows a line still strips
# whole.
_TOPIC_TRANSPORT = rf"""- **The topic**: the run reads its own copy of it. Before the first dispatch, write that copy into the run directory:

  ```bash
  sed '1,/^---$/d' <topic-file> > {_MODE.run_dir}/topic.md
  ```

  Every topic path you hand out — to a local seat, to the liaison, to AA — is `{_MODE.run_dir}/topic.md`, and never the invocation's own topic path. It is a permanent audit artifact like the rest of the run directory: what the seats read is what the run recorded."""

_INPUTS = r"""- **Topic file**: domain context, rules of engagement, construction methodology (selected from
  `mad/design-topics/`)
- **Problem statement path**: serves one of two roles depending on whether a problem brief already
  exists:
  - **(a) Existing brief**: a file or directory stating the open problem, the axiom set or invariant
    document to build from, the success criteria, and any reference values for post-construction
    validation. Use directly as the dispatch input.
  - **(b) Output location only**: the path is an empty or not-yet-created directory where session
    output will be written. In this case there is no input brief; the topic of design is gathered
    from the user via interactive dialogue (see Phase 0 below) before Phase 1 begins."""

_PHASE_0 = rf"""## Phase 0 — Problem Elicitation *(only when no input brief exists)*

Skip this phase when the artifact path points to an existing problem brief.

When the artifact path is an output location only, conduct an interactive dialogue with the user to
gather the inputs the participants will need:

- The open problem statement: what is the question to be solved, the goal of the design, or the
  artifact to be constructed?
- The axiom set or invariant document to build from (path or content).
- Success criteria: what does a successful solution look like? Algebraic closure? A specific
  numerical prediction? A working specification?
- Any reference values for post-construction validation, with a clear statement of whether each
  reference is empirical (the solution would be predictive) or itself derived (the agreement would
  confirm a downstream chain).
- Any additional constraints the user wants enforced.

Capture the dialogue's output as `{_MODE.run_dir}/problem-brief.md`. This file becomes the
artifact for Phase 1 dispatch. Confirm the brief with the user before proceeding to Phase 1 — read
it back and ask whether anything is missing, ambiguous, or wrong. Do not begin Phase 1 until the
user confirms."""

_DISPATCH_INPUTS = r"""- The referee-instructions file path + the topic file path
- The problem statement (path or content)
- The requirements document path, if provided — participants must treat it as the authoritative
  source of invariants the proposed solution must satisfy"""

_PROPOSAL_SHAPE = r"""Each seat produces a complete, independent end-to-end proposal — not a critique. The shape of the
proposal is governed by the topic file (e.g., a derivation chain for `math-derivation`; a software
architecture and key interfaces for software-design topics; a circuit topology and parameter set for
hardware-design topics)."""

_AA_CLASSIFICATION = r"""In design mode, AA classifies findings/proposals as: same load-bearing principle, divergent paths to same answer, divergent paths to different answers, or proposal-level disagreement on what the deliverable should look like. Brief AA accordingly via the topic content."""

_ROUNDS = r"""## Phase 3 — Debate Rounds (maximum 10)

Design debates require more rounds than review debates. Construction is iterative — early rounds
typically expose gaps that prompt new directions, and converging two independently-constructed
proposals onto a single closed form (or a shared under-determination diagnosis) takes longer than
retiring a list of independent flaws."""

_EQUIVALENCE_CHECK = r"""**Algebraic / structural equivalence check**: the proposed elements (equations, interfaces,
   parameter values, structural decisions) must match modulo trivial reformulation across all
   converging seats. If the elements are demonstrably the same expression in different notation,
   count as equivalent. If they require external reasoning to bridge, the gate fails — the
   convergence is superficial."""

_NUMERICAL_AGREEMENT = r"""**Numerical agreement** *(when applicable)*: if the topic specifies a reference value or
   numerical success criterion, verify that all converging proposals predict the same numerical
   outcome to within the stated tolerance. Algebraic equivalence implies numerical agreement, so
   this is typically a redundant check — but explicitly verify when the proposals reach the same
   answer via different paths (multi-path convergence, see below)."""

_GATE_PASSES = r"""**Gate passes**: mark the point retired. Tag as `[Conceded by <seat>]` naming the conceding seat
   (or several, comma-separated), `[Mutual Convergence]`, or `[Convergent — multiple paths]` as
   appropriate."""

_MULTI_PATH = r"""**Multi-path convergence** is a strong-positive outcome. When seats reach the same numerical answer
via demonstrably independent derivation paths (different load-bearing principles, different
intermediate equations, but the same final result), retire the point as
`[Convergent — multiple paths]` and preserve all paths in the SOLUTION document. This is a *more*
confident outcome than single-path convergence — multiple independent constructions reaching the
same answer is mutual reinforcement, and it strengthens with each additional seat that arrives
independently at the same place. Record how many distinct paths converged."""

_UNDER_DETERMINATION = r"""**Under-determination convergence**: a special case where every active seat converges not on a
solution but on the same diagnosis — that the problem cannot be closed from the supplied axioms, and
that a specific additional axiom, principle, boundary condition, or empirical input is required.
This passes the gate if the seats independently identify the *same* missing piece. Tag as
`[Under-determined — convergent diagnosis]`. The diagnostic statement is the deliverable, and a
clear diagnosis of what the framework needs to add is more valuable than a spurious convergence on
an under-supported answer."""

_END_CONDITIONS = r"""**Step 4 — Check end conditions**

- **End condition 1**: all points resolved. Proceed to Phase 4.
- **End condition 2**: 10 rounds completed. Proceed to Phase 4; remaining contentions go to human
  arbitration queue.
- Otherwise: increment round counter, return to Step 1.

Update session state at each transition."""

_SOLUTION_NOTE = r"""The SOLUTION document is the design deliverable. Unlike the review-mode SUMMARY (a burndown of
findings), SOLUTION presents the proposed solution itself with full provenance — which seat proposed
which element, which parts converged via which gate path, and which (if any) remain contested."""

_GATE_ROLE = r"""**Your role**: you are testing comprehensibility and structural equivalence, not technical
correctness. You do not decide whether the converged solution is right. You decide whether it is
coherent, mutually understood, and reproducibly stated.

**Outcome disposition**: the topic file enumerates the terminal states for its domain. Every state
in which the active seats converge — on one solution, on the same solution via independent paths, or
on the same under-determination diagnosis — retires the debate as productive. Only unresolved
divergence escalates, and it escalates to human arbitration with the full candidate space preserved
in `SOLUTION.md`."""

_PATHS = r"""| Document | Filename | Audience |
|----------|----------|----------|
| Session state | `design-session-state.md` | referee |
| Per-seat initial proposal | `<seat>-proposal.md` | that seat only |
| Per-seat round response | `<seat>-round-[N].md` | that seat only |
| Alignment map | `aa-initial-map.md`, `aa-round-[N]-map.md` | all seats |
| Initial proposals *(aggregate)* | `initial-proposals.md` | human — never a seat |
| Round N *(aggregate)* | `round-[N].md` | human — never a seat |
| Final solution | `SOLUTION.md` | human |"""

_SOLUTION_LAYOUT = r"""```
# Design Solution — [Design Name]

## Problem
[One-paragraph restatement of the open problem the debate addressed]

## Outcome
One of: Algebraic Convergence / Multi-Path Convergence / Under-Determined / Unresolved Divergence

## Converged Solution
The proposed solution as agreed by the participants. Include the load-bearing principles, the closed-form result (or design specification, or diagnostic statement), and the boundary conditions.

For multi-path convergence: present each independent path as a numbered subsection, then show that they predict the same final outcome.

For under-determination: present the convergent diagnostic statement, identify the specific missing axiom/principle/input, and characterize what closure it would provide.

## Provenance
| Element | Originally Proposed By | Survived Through | Final Form |
|---------|------------------------|------------------|------------|
| [load-bearing principle, equation, decision] | [seat name] | rounds 1–N / unchanged from initial | [final statement] |

## Validation *(if applicable)*
For derivations or designs with a reference value: state the converged prediction, the reference, and the agreement margin. Identify whether the reference is empirical (the converged solution is predictive) or itself derived (the agreement confirms a downstream chain).

## Human Arbitration Queue
Unresolved points after all debate rounds. Require human judgment.

One position column per active seat, in roster order — the header row is built from the roster, so a three-seat run has three position columns and a five-seat run has five. A seat that never addressed an issue gets `—` (not silence).

| Issue | `<seat-1>` Position | `<seat-2>` Position | ... | Notes |
|-------|---------------------|---------------------|-----|-------|
| [description] | [position] | [position] | ... | [gate failure reason or rounds exhausted] |

## Retired Contentions
Items that arose during the debate and were resolved through the convergence mechanism.
These were investigated and resolved — do not reopen without new information.

| Contention | Raised By | Resolved By | Round | Plain-Language Resolution |
|------------|-----------|-------------|-------|--------------------------|
| [description] | [seat name] | [Conceded by <seat>] / [Mutual Convergence] / [Convergent — multiple paths] / [Under-determined — convergent diagnosis] | N | [resolution] |
```"""

_SNAPSHOT_HEAD = r"""```markdown
---
design: <name>
phase: <current-phase>
status: <current-status>
roster: [<seat>, <seat>, ...]
seats_active: <N>
rounds_complete: <N>
points_resolved: <N>
points_remaining: <N>
end_condition: <none|1|2>
outcome: <pending|algebraic|multi-path|under-determined|unresolved>
---

# Design Referee Session State

## Design Name
<name>

## Roster
<the validated seat roster, in invocation order; env-file path recorded as present/absent if `guest` is seated>

## Topic
<topic file path>

## Problem Statement
<problem statement path>

## Phase 1 — Independent Proposal
<one line per seat on the roster>
<seat>: complete / pending / failed

## Phase 2 — Initial Alignment
AA: complete / pending
Points of convergence: N
Points of contention: N
Unique proposals: N"""

_SNAPSHOT_TAIL = r"""## End Condition
<which condition triggered, at which round>

## Outcome
<algebraic / multi-path / under-determined / unresolved>

## Status
<current phase, next action>
```"""

DEFINITIONS = (
    Definition(
        name="mad-design-referee",
        description=(
            "Referee and coordinator for multi-model debate design process. Orchestrates the full process: "
            "dispatches participants and alignment assessor, manages debate rounds, applies the convergence gate, "
            "and generates output documents. Used for derivation construction, software design, hardware design, "
            "and other constructive problem-solving — not for review or critique of an existing artifact."
        ),
        tools=ALL,
        tier="medium",
        color="#0EA5E9",
        sections=(
            RefereeRole(mode=_MODE, item="proposal", artifact="the proposed artifact", stances="content"),
            Prose(_SIBLING),
            RefereeSeats(mode=_MODE, role_note=_PROPOSERS),
            DispatchMechanism(
                mode=_MODE,
                skill="mad-design",
                corrupts="text",
                charter="design charter / problem brief",
                recipient_input="problem statement",
                guest_inputs="the topic-file path, requirements-file path, problem statement, mode",
                file_borne="topic/charter/requirements/round-input",
                input_staging=_TOPIC_TRANSPORT,
            ),
            RefereeInvocation(name_label="Design name", inputs=_INPUTS, conformer="proposed solution"),
            SeatRoster(mode=_MODE),
            RunFileSystem(mode=_MODE, completion="session"),
            Prose(_PHASE_0),
            IndependentPhase(
                mode=_MODE,
                charter="charter/problem brief",
                inputs=_DISPATCH_INPUTS,
                say="propose",
                degraded="a proposal, not a convergence",
                output_note=_PROPOSAL_SHAPE,
            ),
            InitialAlignment(mode=_MODE, context="The topic file", outputs="proposals", tail=_AA_CLASSIFICATION),
            Prose(_ROUNDS),
            RoundDispatch(
                mode=_MODE,
                unit="position",
                instruction_points="the specific contention points to address",
                dispatch_points="the specific points of contention to address",
            ),
            RoundGate(
                mode=_MODE,
                sameness="construction and invoke the same load-bearing principles",
                premise="[proposed solution] holds",
                aspect="problem",
                checks_before=(_EQUIVALENCE_CHECK,),
                checks_after=(_NUMERICAL_AGREEMENT, _GATE_PASSES),
                after_fails=_MULTI_PATH,
                after_concessions=_UNDER_DETERMINATION,
            ),
            Prose(_END_CONDITIONS),
            OutputPhase(mode=_MODE, deliverable_note=_SOLUTION_NOTE),
            GateMetaRules(mode=_MODE, role=_GATE_ROLE),
            DocumentFormat(
                mode=_MODE,
                paths=_PATHS,
                title="Initial Proposals — [Design Name]",
                name="Design Name",
                resolution="convergence statement",
            ),
            FinalDocumentFormat(mode=_MODE, layout=_SOLUTION_LAYOUT, weight="a convergence"),
            SessionStateFormat(mode=_MODE, snapshot_head=_SNAPSHOT_HEAD, snapshot_tail=_SNAPSHOT_TAIL),
        ),
    ),
)
