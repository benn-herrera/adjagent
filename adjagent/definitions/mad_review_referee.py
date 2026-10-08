"""mad-review-referee: the referee of a multi-model debate review."""

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
    name="review",
    run_dir="mad-review/[review-name]",
    gate="retirement",
    seat="reviewer",
    initial="assessment",
    aggregate="initial-findings.md",
    final="SUMMARY.md",
    state="debate-session-state.md",
    agreement="agreement",
    outcome="resolution",
)

_INPUTS = r"""- **Review charter**: the invoker's verbatim instruction text — what to review and against what
  standard. Review mode has no topic library, so this is the whole methodology a seat receives; an
  invocation naming no topic file is complete, not defective
- **Artifact path**: the specific material under review"""

_FINDING_BUDGET = r"""### The finding budget — guidance for the invoker, not referee behavior

A review charter should cap how many findings a seat reports, so that the arbitration queue stays
readable. **12 per seat is the suggested default.** A cap wants a coverage note beside it — required
in every review, not only where something was cut — so that a truncated review does not read as a
complete one, and so that a defect one seat judged not worth reporting is visible to a seat other
than its author. The charter says what such a note holds; that is not yours to specify.

You neither set the number nor enforce it. Where a charter names no budget, that is the invoker's
choice and not a defect to correct."""

_DISPATCH_INPUTS = r"""- The referee-instructions file path
- The artifact (path or content)
- The requirements document path, if provided — reviewers must treat it as the authoritative source
  of invariants to validate against"""

_ROUND_POINTS = r"""**A round carries two kinds of point, and omitting the second is how a sound finding dies
unconfirmed.** Contested points, which need argument; and **points short a stance**, which need only
that a seat read and take one. A point two seats found independently and a third never addressed is
not agreed, not contested, and — if no round ever puts it — not retirable either.

- A **live point** is any entry the current map carries that is not already retired — every section
  of it, whatever the assessor headed the entry. An entry it labels a shared premise or a flagged
  ambiguity is a live point like any other: deciding that an entry is not really a finding is a
  content call, and your authority is process.
- A live point is **short a stance from seat S** when the map records anything other than a position
  explicitly attributed to S. The map's vocabulary for this varies — *silent*, *omission*, *implicit
  disagreement*, *raised as a coverage note* — and all of it means the same thing here: no stance.
  Neither an implicit disagreement nor a coverage note is a position.
- **Every round carries every unretired live point**, and the instruction text says of each whether
  it is contested or short a stance, so a seat spends argument only where argument is wanted. Seats
  stance every live point every round; a stance is a statement about this round, and the gate reads
  this round's.
- **A no-stance point carries what the seat needs to answer in one round**: the raising seat's cited
  locations, and the answers admitted. Quote the raising seat's Conclusions entry or the map's
  description of it — never paraphrase, because a summary of a finding is where its framing leaks.
  An abstention on such a point must say what would settle it."""

_GATE_PASSES = r"""**Gate passes**: mark the point retired. Tag as `[Conceded by <seat>]` naming the conceding seat
   (or several, comma-separated), or `[Mutual Agreement]` when no seat had to move.
   `[Initial Agreement]` or `[Eventual Agreement]` from the AA map carries forward."""

_END_CONDITIONS = r"""**Step 4 — Check end conditions**

- **End condition 1**: every live point is either retired by the gate, or has this round been
  stanced by **every** active seat without the gate retiring it. A point no seat contests but one
  has never addressed is **not** resolved, and a run that ends on it spends a human's judgement on a
  question a spare round would have answered. Proceed to Phase 4.
  - `abstain` is a stance and satisfies this condition, but retires nothing. A point every seat has
    stanced that the gate has not retired — including one carried by abstentions — goes to the human
    arbitration queue with the reason recorded, exactly as a contested point does.
- **End condition 2**: 5 rounds completed. Proceed to Phase 4; every point short of end condition 1
  goes to the human arbitration queue.
- Otherwise: increment round counter, return to Step 1.

Update session state at each transition."""

_GATE_ROLE = r"""**Your role**: you are testing comprehensibility, not correctness. You do not decide whether the
retired position is technically right. You decide whether it is coherent and mutually understood."""

_PATHS = r"""| Document | Filename | Audience |
|----------|----------|----------|
| Session state | `debate-session-state.md` | referee |
| Per-seat initial assessment | `<seat>-assessment.md` | that seat only |
| Per-seat round response | `<seat>-round-[N].md` | that seat only |
| Alignment map | `aa-initial-map.md`, `aa-round-[N]-map.md` | all seats |
| Initial findings *(aggregate)* | `initial-findings.md` | human — never a seat |
| Round N *(aggregate)* | `round-[N].md` | human — never a seat |
| Final summary | `SUMMARY.md` | human |"""

_SUMMARY_LAYOUT = r"""```
# Review Summary — [Review Name]

## Burndown List
Agreed actionable items. Address these.

| Finding | Agreement Type | Round Reached |
|---------|----------------|---------------|
| [description] | Initial / Eventual | — / N |

## Human Arbitration Queue
Unresolved points after all debate rounds. Require human judgment.

One position column per active seat, in roster order — the header row is built from the roster, so a three-seat run has three position columns and a five-seat run has five. A seat that took no position gets `—` (not silence), and the Notes column says which kind of silence it was: **never asked** — no round put the point to that seat — or **abstained**, which is a judgement it made. A reader weighing a finding needs to know whether the gap is the seat's or the process's.

| Finding | `<seat-1>` Position | `<seat-2>` Position | ... | Notes |
|---------|---------------------|---------------------|-----|-------|
| [description] | [position] | [position] | ... | [gate failure reason or rounds exhausted] |

## Retired Actionables
Items initially flagged as actionable but withdrawn through the concession mechanism.
These were investigated and resolved — do not reopen without new information.

| Finding | Raised By | Retired By | Round | Plain-Language Resolution |
|---------|-----------|------------|-------|--------------------------|
| [description] | [seat name] | [Conceded by <seat>] / [Mutual Agreement] | N | [resolution] |
```"""

_SNAPSHOT_HEAD = r"""```markdown
---
review: <name>
phase: <current-phase>
status: <current-status>
roster: [<seat>, <seat>, ...]
seats_active: <N>
rounds_complete: <N>
points_resolved: <N>
points_remaining: <N>
end_condition: <none|1|2>
---

# Debate Referee Session State

## Review Name
<name>

## Roster
<the validated seat roster, in invocation order; env-file path recorded as present/absent if `guest` is seated>

## Artifact
<artifact path>

## Phase 1 — Independent Assessment
<one line per seat on the roster>
<seat>: complete / pending / failed

## Phase 2 — Initial Alignment
AA: complete / pending
Points of agreement: N
Points of contention: N
Unique findings: N"""

_SNAPSHOT_TAIL = r"""## End Condition
<which condition triggered, at which round>

## Status
<current phase, next action>
```"""

DEFINITIONS = (
    Definition(
        name="mad-review-referee",
        description=(
            "Referee and coordinator for multi-model debate review process. Orchestrates the full process: "
            "dispatches reviewers and alignment assessor, manages debate rounds, applies the retirement gate, and "
            "generates output documents."
        ),
        tools=ALL,
        tier="medium",
        color="#059669",
        sections=(
            RefereeRole(mode=_MODE, item="finding", artifact="the artifact under review", stances="findings"),
            RefereeSeats(mode=_MODE),
            DispatchMechanism(
                mode=_MODE,
                skill="mad-review",
                corrupts="charters",
                charter="review charter",
                recipient_input="artifact",
                guest_inputs="the requirements-file path, artifact, mode",
                file_borne="charter/requirements/round-input",
            ),
            RefereeInvocation(name_label="Review name", inputs=_INPUTS, conformer="artifact"),
            SeatRoster(mode=_MODE, invoker_guidance=_FINDING_BUDGET),
            RunFileSystem(mode=_MODE, completion="review"),
            IndependentPhase(
                mode=_MODE,
                charter="charter",
                inputs=_DISPATCH_INPUTS,
                say="say",
                degraded="findings, not a debate",
            ),
            InitialAlignment(mode=_MODE, context="The referee-instructions file path", outputs="reviews"),
            Prose("## Phase 3 — Debate Rounds (maximum 5)"),
            RoundDispatch(mode=_MODE, unit="finding", round_points=_ROUND_POINTS),
            RoundGate(
                mode=_MODE,
                sameness="resolution",
                premise="[resolution] is true",
                aspect="artifact",
                checks_after=(_GATE_PASSES,),
            ),
            Prose(_END_CONDITIONS),
            OutputPhase(mode=_MODE),
            GateMetaRules(mode=_MODE, role=_GATE_ROLE),
            DocumentFormat(
                mode=_MODE,
                paths=_PATHS,
                title="Initial Findings — [Review Name]",
                name="Review Name",
                resolution="resolution",
            ),
            FinalDocumentFormat(mode=_MODE, layout=_SUMMARY_LAYOUT, weight="an agreement"),
            SessionStateFormat(mode=_MODE, snapshot_head=_SNAPSHOT_HEAD, snapshot_tail=_SNAPSHOT_TAIL),
        ),
    ),
)
