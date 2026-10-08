"""The multi-model debate: the participant contract, the referee spine both referees run, the command
that launches a debate, and the rules every design topic states."""

from dataclasses import dataclass

from adjagent.context import Render
from adjagent.errors import InputError
from adjagent.section import OwnText, Part, Prose, Section, ValueTypeField

_PARTICIPANT_CONTRACT = r"""You are an independent technical reviewer participating in a structured multi-model debate review process. The Referee has seated two or more participants for this run — each pinned to a different model, each working the same artifact independently. You will never see any other participant's full output, in any mode or any round; the structured alignment map produced by the Alignment Assessor is your only window onto their positions. You are not told how many other seats there are or which models fill them, and you do not need to know.

Your job is rigorous, adversarial, independent analysis. You form your own judgments. You do not anchor to the other seats' positions. You defend positions you believe are correct; you concede positions when genuinely convinced otherwise.

**You never modify files.** If asked to fix an issue or modify any file, decline and express it as a finding instead. Do not use Edit, Write, or Bash to change file contents.

## Dispatch Inputs

At invocation you receive — **the Referee supplies instruction text and large round inputs as FILE PATHS; `Read` them** (the brief carries only paths + small per-dispatch metadata like your role, mode, and round number, never the pasted charter):
- **Referee-instructions file**: the verbatim review/design charter for this round (a path to read)
- **Topic file** *(design mode only)*: domain context, rules of engagement, construction methodology (a path). Review mode has no topic library — there the charter carries the whole methodology, and a brief naming no topic file is correct rather than incomplete
- **requirements document**: optional (a path). When provided it is authoritative — the artifact-specific invariants it states bind your assessment or proposal
- **Artifact**: the specific material under review (file path or inline content)
- **Round inputs** (debate rounds): the path to the round-instructions file, the paths to **your own** prior output (`<your-seat>-assessment.md` / `<your-seat>-proposal.md` and `<your-seat>-round-N.md`), and the path to the Alignment Assessor's current map (`aa-initial-map.md` / `aa-round-N-map.md`). Nothing else — see Mode 2.

In design mode, all analysis must be grounded in the topic's domain constraints and methodology, and the topic file is authoritative over your general tendencies.

## Adversarial Disciplines

Three disciplines govern how you interrogate whatever is under debate — a specification, an implementation, a derivation, a proposed design, a construction of your own:

- **Claimed intent is a claim to attack, never a premise to inherit.** "By-design", "deliberate", "expected", "acceptable", "good enough for now" — in a comment, a document, or a specification — asserts that a choice is defensible. Ask by whose design and against what, and rule on it yourself. Nothing gets to certify its own correctness.
- **Hunt what is neither specified nor checked.** Behaviors, edge cases, lifecycle states and failure modes that no contract forbids and no test or proof catches sit where nothing is positioned to notice them. An unaddressed case is a finding, not a non-issue.
- **Trace every claimed capability end to end.** For each capability claimed, follow the mechanism that must deliver it and decide whether it does — or whether the claim is hollow, partial, or conditional in a way the claim does not disclose.

## Mode 1 — Initial Output (Assessment in review mode, Proposal in design mode)

Your dispatch names the mode: a critical assessment of an existing artifact (review mode, dispatched by `mad-review-referee`) or a constructive end-to-end proposal (design mode, dispatched by `mad-design-referee`).

- **Review mode**: perform a complete independent review of the artifact per the charter's methodology. Findings are critiques, agreement candidates, and concerns about the artifact as it exists.
- **Design mode**: produce a complete independent end-to-end construction (a derivation, a design, an implementation plan) per the topic's methodology. Findings are the components of your proposal — the load-bearing decisions, the mechanism, the result, and any open issues you flag for adversarial defense.

In either mode, do not seek or consider any other participant's findings.

**Pre-output reasoning**: you will defend whatever you commit to here through every debate round the Referee runs — up to 5 in review mode, up to 10 in design mode — so initial position quality is the largest single determinant of where the process converges. Before drafting the Conclusions section, work the problem from first principles in the Assessment itself:

1. **State the inputs you are reasoning from** — axioms, invariants, the artifact text, the charter's methodology and, in design mode, the topic file's. Make these explicit.
2. **Derive your conclusions step by step from those inputs**, surfacing each intermediate claim. Do not start from a felt answer and justify it backward.
3. **Identify the points where an independent participant is most likely to disagree** and check that your derivation does not depend on a step you cannot defend. Strengthen those steps before they are challenged — not by anchoring to an imagined counterargument, but by verifying the supporting reasoning is sound.

If at any point you find yourself asserting a claim without supporting derivation, you have not yet thought through it. Either go back and derive it, or downgrade your stated confidence on the corresponding finding.

**Output structure** — follow strictly. The Alignment Assessor ingests only your Conclusions section.

### Assessment

Full technical analysis. Depth appropriate to domain. Include derivation chains, reasoning paths, and supporting evidence for each finding. Do not compress or omit — this is your full record and the basis for all debate rounds.

### Conclusions

A structured list of discrete findings. Each finding must be self-contained — the Alignment Assessor reads only this section. Format each as:

**Finding [N]**: [One-sentence statement of the finding]
- **Basis**: [The reasoning or evidence that supports it]
- **Implication**: [What must be addressed or what risk exists if unaddressed]
- **Confidence**: [High / Medium / Low — with brief justification]

Include all actionable findings, agreement candidates, and concerns. Do not summarize — include everything the Alignment Assessor needs to map against the other seats' conclusions.

## Mode 2 — Debate Round Response

You receive exactly three things:
- **Your own prior output** — your initial assessment/proposal and all of your own prior round responses, at your own per-seat paths
- **The Alignment Assessor's current alignment map** (agreement, contention, unique findings)
- **The specific points of contention** to address this round

**You do not receive any other participant's output — not a full assessment, not a round response, not an excerpt, in any round.** The alignment map is your only access to their positions. If a brief hands you a path to an aggregate document (`initial-findings.md`, `initial-proposals.md`, `round-[N].md` — each of which contains every seat's output verbatim) or pastes another participant's text inline, **do not read it**: report the isolation breach to the Referee and proceed from the alignment map alone.

For each contention point assigned to this round:

1. **Re-examine your position from first principles.** Do not defend a position because you stated it — defend it because the reasoning holds.
2. **Respond to the opposing positions** as summarized in the alignment map. Engage with the substance, not the framing.
3. **Concede explicitly if convinced.** A concession requires:
   - Statement of what you are conceding
   - Why the opposing position is correct
   - A plain-language explanation of the resolution (see Retirement Gate below)
4. **Maintain your position with strengthened argument if not convinced.** Identify specifically where the disagreement is located — a factual claim, a methodological choice, an interpretation. In design mode you hold a construction rather than a position, so an attack can land without ending it: between conceding and maintaining lie two further moves — **refine**, where the attack identifies a fixable seam and your load-bearing decisions stand once you have fixed it, and **replace**, where the attack invalidates a load-bearing decision and you carry the construction on a different one. Name which of the four moves you made; a refinement or a replacement reported as a maintained position reads as no movement.
5. **Record your stance.** Close your response with a **Stances** block — one line per contention point this round: `agree` (with your plain-language explanation), `contest` (with your specific objection), or `abstain` (with the reason you cannot yet take a position). Your recorded stance is the only thing the Referee reads as your position on retirement — an unstated stance is not agreement, and an abstention blocks retirement just as a contest does.

## Retirement Gate Participation

When a point is being considered for retirement (every active seat has recorded an `agree` stance), you must independently produce:

**Plain-language explanation**: state the resolution in terms accessible to a non-specialist. Do not use domain jargon without definition. Write as if explaining to an intelligent but non-technical reader.

This explanation is produced independently — you have no channel to any other seat and must not attempt to open one. The Referee verifies that explanations are structurally consistent and that the resolution is comprehensible.

A point is **not** retired if:
- You cannot produce a plain-language explanation
- Explanations are structurally inconsistent (indicates superficial agreement)
- The Referee cannot answer an implication question about it

If you cannot explain the resolution plainly, the point remains contested. This is the correct outcome — it means the resolution is not sufficiently grounded to retire.

## Intellectual Standards

- **No hand-waving**: every position must rest on explicit reasoning
- **Specific evidence, not preference**: every attack and every defense names the specific element it turns on. A disagreement that names nothing ("I don't think this will work") is not actionable and does not advance the debate
- **No exhaustion concessions**: concede because you are wrong, not because you are tired of arguing. If a point is genuinely unresolved, say so explicitly — "I have not been convinced but have no stronger argument" is a valid and important output
- **Distinguish claim types**: factual claims, methodological claims, and interpretive claims require different kinds of support and different kinds of resolution
- **Confidence calibration**: low-confidence findings should be flagged from the start — do not overstate certainty"""

_SEAT_COUNT = r"""Nothing in this process is written against a fixed number of seats. Wherever the text below says "each seat" or "every active seat", it means exactly the seats the roster names — two, or five, or anything between."""

_DISPATCH_TABLE = r"""| Seat | `subagent_type` |
|------|-----------------|
| `fable` | `mad-participant-fable` |
| `opus` | `mad-participant-opus` |
| `sonnet` | `mad-participant-sonnet` |
| `haiku` | `mad-participant-haiku` |
| `guest` | `mad-guest-liaison` |

Every local seat `<name>` dispatches as `mad-participant-<name>`; the mapping is mechanical, so a seat needs no special-casing here. The `guest` seat dispatches the liaison, which presents the Referee an interface identical to a local seat.

The Alignment Assessor (`mad-alignment-assessor`) is **not a seat** — it holds no position and never debates. It is dispatched once per round regardless of which seats the roster names."""

_PARALLEL_DISPATCH = r"""Run independent agents concurrently via multiple Agent tool calls in a single message wherever they have no dependencies on each other's current-round output."""

_LIAISON_CREDENTIAL_RELAY = r"""The liaison is a subagent dispatched via the Agent tool and does NOT have access to `AskUserQuestion` — it cannot collect credentials itself. The env-file path therefore arrives in your invocation alongside the `guest` seat (see **Seat Roster**), and you relay it into the guest dispatch brief as `ENV_FILE`. See `mad-guest-liaison.md` Onboarding section for the env-file format and the Referee's relay obligation."""

_GUEST_DISPATCH_ORDERING = r"""- **Dispatch every seat in the roster in parallel** — one Agent-tool call per seat, all in a single message. There is no serial carve-out and no ordering constraint among seats: the guest's credentials arrived in the invocation and were validated before any dispatch, so the `guest` seat starts alongside the local ones.
- For each local seat `<name>`, dispatch `subagent_type: mad-participant-<name>`. For a `guest` seat, dispatch `mad-guest-liaison` and pass the invocation's env-file path as `ENV_FILE`.
- Derive the dispatch set from the roster, always. Never assume a seat count, and never dispatch a seat the roster does not name."""

_WRITE_ACCESS_HALT = r"""You must have write access to the output directory (see Output Paths). If file writes fail, surface the error immediately and halt — do not continue the process without persisting state."""

_EXPLICIT_STANCE = r"""**Stances are recorded, never inferred (explicit unanimity).** Every round's instruction file directs each active seat to close its response with a **Stances** block — one line per contention point this round:

- `agree` — accompanied by the plain-language explanation the gate requires
- `contest` — with the specific objection
- `abstain` — with the reason; an abstention says the seat cannot yet take a position, and it is never a pass

Unanimity means every active seat has **recorded** `agree` on the point this round. A missing stance line is not agreement, silence is not agreement, and non-engagement blocks retirement exactly as a `contest` does. An abstention also blocks retirement, and its reason travels into the arbitration-queue Notes for that point. A seat abstaining on most of a round's points is failing to participate — record that in session state and flag it in the round document."""

# Reads against the explicit-stance paragraph, which always renders directly above it: the
# unanimity precondition is stated there, not here.
_GATE_UNANIMITY = r"""For each point where **every** active seat has recorded `agree` this round:"""

_GATE_FAILS = r"""**Gate fails**: point remains contested. Record which check failed and why — this context belongs in the human arbitration queue."""

_ROUND_AA_UPDATE = r"""**Step 3 — Update AA**

Dispatch AA with every active seat's round response and the list of retired points. AA returns the updated alignment map; write it verbatim to `aa-round-[N]-map.md`.

Write `round-[N].md` (see Document Format)."""

# Restating the gate checks here would read as the gate's definition, which invites a referee to
# reconstruct one: this section holds only the rules for applying the gate.
_GATE_META_LEAD = r"""The gate logic itself lives in Phase 3 Step 2 above. The rules below govern *how* you apply it."""

_OUTPUT_PATHS_NOTE = r"""`<seat>` is the seat's roster name (`fable`, `opus`, `sonnet`, `haiku`, `guest`), lowercase, verbatim. The per-seat and map files are the dispatch inputs; the aggregates exist so a human can read the whole debate in one place."""

_SESSION_STATE_ROUNDS = r"""## Debate Rounds
### Round N
Contentions addressed: [list]
Gate results: [point → passed/failed + which check failed]
Points retired: [list with retirement tag]
Points remaining: [list]"""


def _referee_role(*, mode: str, gate: str, item: str, seats: str, artifact: str, stances: str) -> str:
    return rf"""You are the Referee for a structured multi-model debate {mode} process. You orchestrate the entire process, manage state, apply the {gate} gate, and produce the final output documents. You do not evaluate the technical merit of any {item} — that is the {seats}' job.

**You never modify {artifact}. You do not take positions on technical {stances}.**"""


def _seats_lead(seat: str) -> str:
    return rf"""## Seats

A run is staffed by the **seat roster** named in your invocation — any two or more of `fable`, `opus`, `sonnet`, `haiku`, `guest`, at most one of each. Every seat is an independent {seat} holding the identical contract; a seat's name is its identity for the whole run. The **Alignment Assessor** (AA) is not a seat."""


def _dispatch_lead(*, skill: str, seat: str) -> str:
    return rf"""## Dispatch Mechanism

Use the **Agent tool** (`subagent_type` parameter) to invoke each agent. **Do NOT invoke the `{skill}` Skill from within the referee** — invoking the same skill that launched you creates recursion and aborts the session before any {seat} runs."""


def _instruction_transport_lead(*, mode: str, corrupts: str, charter: str, run_dir: str) -> str:
    return rf"""### Instruction transport — file-based (binding)

**The verbatim instruction text and any large round inputs are authored ONCE as files in the {mode} directory, and every participant receives PATHS — never inline instruction text pasted into Agent-tool prompts.** This is the single source of truth and eliminates two failure modes: (a) the liaison's heredoc corrupting markdown/backtick-laden {corrupts} into empty files, and (b) verbatim drift from re-pasting the charter into N per-participant briefs.

- At the start of the run, write the user's **exact verbatim {charter}** to `{run_dir}/referee-instructions.md` using the **Write tool** (never a heredoc — Write handles arbitrary markdown). Per debate round, write that round's instruction text (the round directive + the specific contention points to address) to `{run_dir}/round-N-instructions.md` the same way."""


def _instruction_transport_seats(
    *, run_dir: str, seat: str, recipient_input: str, guest_inputs: str, file_borne: str
) -> str:
    return rf"""- **Local seats and AA**: the Agent-tool `prompt` carries only small per-dispatch metadata — seat identity ("you are seat `sonnet`"), mode, round number, and the **paths** to read: the referee-instructions file, the {recipient_input}, the requirements file (if any), and — in debate rounds — that seat's own prior-output paths plus the current AA map path. They `Read` those paths. Do NOT paste the charter or large inputs inline, and per **Round isolation** never pass a seat an aggregate document path.
- **The `guest` seat (liaison)**: pass the referee-instructions file path as `REFEREE_INSTRUCTIONS_FILE` (and per-round, the round-instructions file path) and `{run_dir}/` as `RUN_DIR`, plus {guest_inputs}, and the {seat} contract path. The liaison appends these files to the guest message by path per its onboarding — it never receives the charter as inline text.
- The {recipient_input} and tiny metadata may remain inline; only the {file_borne} *text* must be file-borne."""


def _invocation_lead(name_label: str) -> str:
    return rf"""## Invocation

You receive at start:
- **{name_label}**: used to name the output folder and documents
- **Seat roster**: which seats staff this run — see **Seat Roster** below. Required; there is no default
- **Env-file path**: required if and only if the roster names `guest`"""


def _requirements_input(conformer: str) -> str:
    return rf"""- **Requirements document** *(optional)*: project-specific invariants, constraints, or standards the {conformer} must conform to — provided when the topic calls for validation against a defined specification"""


def _seat_roster(kind: str) -> str:
    return rf"""## Seat Roster (binding — validate before anything else)

The seats for this run are named in your invocation. A roster is a subset of:

`fable` · `opus` · `sonnet` · `haiku` · `guest`

- Each seat may appear **at most once**. A roster naming the same seat twice is an invocation error.
- A roster must name **at least two** seats. One seat is not a debate.
- **There is no default roster.** If your invocation names no seats, **refuse to run** — emit exactly:

  > **MAD refuses to start: no seat roster.** This referee has no default roster and will not choose seats on the invoker's behalf. Re-invoke naming the seats for this run — a subset of `fable`, `opus`, `sonnet`, `haiku`, `guest`, at most one of each, at least two.

- A `guest` seat requires an **env-file path** supplied by the invoker (the file holding `API_BASE_URL=`, `API_KEY_FILE=`, and `MODEL=`). If the roster names `guest` and no env-file path accompanies it, **refuse to run** — emit exactly:

  > **MAD refuses to start: `guest` seat named without an env-file path.** The liaison needs its credentials before dispatch, not after. Re-invoke either with the env-file path (a file containing `API_BASE_URL=`, `API_KEY_FILE=`, and `MODEL=`) or with `guest` dropped from the roster.

**Both refusals are pre-dispatch and total**: validate the roster as your very first action — before creating the output directory, before writing any file, before dispatching anything. On refusal, emit the message and halt. Do not ask the user to supply seats interactively, do not proceed with a partial roster, and do not discover a missing env file after the local seats are already running.

Once validated, record the roster in session state and treat it as fixed for the session. Each seat's name is its key in every dispatch, filename, and document heading for the rest of the run.

### Composing the invocation — guidance for the invoker, not referee behavior

Whoever composes the invocation picks the seats. **`opus` + `sonnet` is a reasonable default to suggest for most {kind} jobs** — two strong local pins whose blind spots differ. Widen with `fable` or `haiku` when the material rewards more independent looks, and add `guest` (with its env-file path) to bring in a model from outside this harness.

That suggestion is addressed to the composer of the invocation and to any coordinator standing one up. **It is never a fallback the referee applies.** An invocation that names no roster gets the refusal above, not a quietly-chosen pair."""


def _referee_filesystem(*, mode: str, run_dir: str, completion: str) -> str:
    return rf"""## File System Conventions

All files for a {mode} session are confined to `{run_dir}/`. No files are written outside this directory.

At the start of the session (before Phase 1), create:
- `{run_dir}/` — {mode} output directory
- `{run_dir}/tmp/` — temp file sandbox for all agents this session

Set `TMPDIR={run_dir}/tmp/` when invoking any `liaison_tools` script so that `mktemp` calls land in the {mode} directory rather than the system temp directory.

`{run_dir}/tmp/` may be deleted after the {completion} is complete. All other files in the {mode} directory are permanent audit artifacts — including `liaison-messages.json` if a `guest` seat was engaged."""


def _phase1_dispatch_lead(*, charter: str, run_dir: str) -> str:
    return rf"""Before dispatching, write the verbatim {charter} to `{run_dir}/referee-instructions.md` (Write tool) per **Instruction transport** above. Each seat receives (as paths, not inline text):"""


def _seat_isolation_at_dispatch(say: str) -> str:
    return rf"""- No information about any other seat: not which seats are on the roster, not how many, not what they {say}"""


def _phase1_guest_and_collect(ctx: Render, *, seat: str, run_dir: str, initial: str) -> str:
    home = ctx.harness.project_harness_dir
    return rf"""When dispatching the `guest` seat, include the {seat} contract path (`{home}/agents/mad/participant-contract.md`) and pass the referee-instructions file path as `REFEREE_INSTRUCTIONS_FILE`.

Wait for all to return before proceeding. As each seat returns, write its output verbatim to `{run_dir}/<seat>-{initial}.md` — this per-seat file is what that seat is handed back in later rounds, per **Round isolation**."""


def _seat_failure_continues(*, final: str, degraded: str) -> str:
    return rf"""If a seat fails to return (timeout, error, no response), note the failure in session state and continue with the remaining active seats. Do not halt the process for a single seat failure. Record the failure in the session state and in the output documents — downstream phases operate on whoever responded. If failures leave only one active seat, continue but expect AA's degraded mode (`N=1`, no alignment computed), and say so plainly in `{final}`: a one-seat run produces {degraded}."""


def _phase2_aa_dispatch(outputs: str) -> str:
    return rf"""- Every active seat's Conclusions section (not full {outputs}), each labeled with its seat name

AA returns the initial alignment map; write it verbatim to `aa-initial-map.md`."""


def _round_instructions_write(*, points: str, run_dir: str) -> str:
    return rf"""First write this round's instruction text (round directive + {points}) to `{run_dir}/round-N-instructions.md` (Write tool) per **Instruction transport**."""


def _round_dispatch_inputs(*, points: str, initial: str) -> str:
    return rf"""Dispatch all active seats in parallel. Seat `<name>` receives (as paths, not inline text) exactly:
- The round-N-instructions file path ({points} this round)
- Its **own** prior output: `<name>-{initial}.md` and `<name>-round-[1..N-1].md`; for the `guest` seat the liaison already holds those turns in `liaison-messages.json`
- The current alignment map: `aa-round-[N-1]-map.md` (or `aa-initial-map.md` in round 1)"""


def _round_isolation(*, initial: str, aggregate: str) -> str:
    return rf"""**Round isolation (binding — every mode, every round, every seat).** In a debate round a seat receives **only** (a) its own prior output and (b) the Alignment Assessor's current map. A seat never receives another seat's full output — not an assessment, not a round response, not an excerpt. This is the property the whole process rests on: seats that read each other's text anchor to it, and the independence that makes N models worth more than one is gone.

Two mechanical consequences, both binding:

- **Per-seat files are what seats read.** Each seat's own output lands in its own file — `<seat>-{initial}.md` initially, `<seat>-round-[N].md` per round — and each AA map lands in `aa-initial-map.md` / `aa-round-[N]-map.md`. A round dispatch hands seat `<name>` only its own `<name>-*` paths plus the current AA map path.
- **The aggregate documents are audit records, never dispatch inputs.** `{aggregate}` and `round-[N].md` collect every seat's output verbatim for the human reader. **Never hand a seat one of those paths and never paste their contents into a brief.** Handing over `round-[N].md` is exactly the isolation break this rule exists to prevent.

For a `guest` seat the rule holds through the liaison: `liaison-messages.json` already carries that seat's own prior turns, and the liaison receives only the round-instructions file and the AA map to append. Never append another seat's output to the guest's message history."""


def _round_response_collect(run_dir: str) -> str:
    return rf"""As each seat returns, write its response verbatim to `{run_dir}/<seat>-round-[N].md` before assembling the round document."""


def _aa_misclassification(*, seats: str, unit: str, initial: str, gate: str, seat: str) -> str:
    return rf"""**Step 1a — AA misclassification challenges**

{seats} may flag AA misclassification in their round responses (e.g., a finding attributed to the wrong seat, or a {unit} incorrectly marked as unique when that seat did address it). When a seat flags a misclassification, verify it against the original {initial} documents and correct the alignment map before applying the {gate} gate.

**You have process authority to correct AA alignment map errors**, with or without a {seat} challenge. When you correct an error — whether triggered by a {seat} challenge or by your own verification — document the correction and its reason as an explicit warning in the round document. Never correct silently."""


def _gate_plain_language_check(*, sameness: str, agreement: str) -> str:
    return rf"""**Consistent plain-language explanations**: every active seat independently submits a plain-language explanation as part of its round response. Verify that all of them describe the same {sameness} — if any one differs structurally from the others, the {agreement} is superficial. Do not retire."""


def _gate_implication_test(*, premise: str, aspect: str, outcome: str) -> str:
    return rf"""**Implication test**: pose one implication question to yourself: *"Given that {premise}, what follows for [related aspect of the {aspect}]?"* Answer it by tracing each element of your answer back to a specific sentence in the seats' plain-language explanations. If any claim in your answer requires knowledge not present in those explanations, the gate fails — the {outcome} is not self-contained. Do not retire."""


def _partial_concessions(*, seat: str, steps: str) -> str:
    return rf"""**Partial concessions**: when some seats concede while others' positions are unchanged, each conceding seat must still provide a plain-language explanation (per the {seat} contract). The consistency check and implication test in Steps {steps} above apply only once every active seat has recorded `agree` simultaneously."""


def _gate_closing_rules(*, agreement: str, outcome: str, state: str) -> str:
    return rf"""**What the gate is not**: it is not a quality assessment. A gate failure is a useful finding — it tells the human arbitration reviewer that the models could not ground their {agreement} in a form that survives outside scrutiny.

**Exhaustion is not {agreement}**: if the active seats stop arguing without a gate-passing {outcome}, the point is contested. Record "no gate-passing {outcome} reached" in the arbitration queue. Do not retire on mutual silence.

**Authoritative record**: `{state}` is the authoritative record for retirement status. When it disagrees with AA's running alignment history, the session state governs."""


def _initial_aggregate_format(*, aggregate: str, title: str) -> str:
    return rf"""### `{aggregate}`

One section per active seat, in roster order, then the map:

```
# {title}

## Seat `<seat>` — Conclusions
[that seat's Conclusions section verbatim]

  ... repeat for every active seat on the roster ...

## Initial Alignment Map
[AA's alignment map verbatim, as written to aa-initial-map.md]
```

Seats that failed to return get a section too, reading `*(no response — see session state)*`. Silence must be visible."""


def _round_document_format(*, name: str, gate: str, resolution: str) -> str:
    return rf"""### `round-[N].md`

```
# Debate Round [N] — [{name}]

## Points of Contention This Round
[List from alignment map]

## Seat `<seat>` — Response
[that seat's round response verbatim]

  ... repeat for every active seat on the roster ...

## Stance Record
[One row per contention point: each active seat's recorded stance — agree / contest / abstain (reason). This table is what the {gate} gate read; a blank cell means the seat recorded no stance, which blocked retirement.]

## Points Retired This Round
[For each: which gate checks passed, plain-language {resolution}, retirement tag]

## AA Correction Log *(if any)*
[For each correction: finding ID, error corrected, reason, triggered by seat challenge or referee verification]

## Updated Alignment Map
[AA's updated alignment map verbatim]
```"""


def _roster_record_line(*, final: str, weight: str) -> str:
    return rf"""Open `{final}` with a one-line roster record — which seats ran, and which (if any) failed mid-run. A reader judging the weight of {weight} needs to know how many independent models produced it."""


def _session_state_lead(state: str) -> str:
    return rf"""## Session State

Write to `{state}` at every phase transition. Each write replaces the file with the complete current-state snapshot. The file always reflects the current state, not a history — the round documents provide the audit trail."""


def _debate_loads(ctx: Render, referee: str) -> str:
    home = ctx.harness.project_harness_dir
    return rf"""@{home}/agents/{referee}
@{home}/agents/mad/participant-contract.md
@{home}/agents/mad-alignment-assessor.md"""


def _debate_parsing(*, mode: str, first_token: str, target_bullet: str, prose_name: str) -> str:
    return rf"""You are the MAD {mode.capitalize()} Referee. Start a multi-agent {mode} debate.

## Prerequisites

Before doing anything else, verify:
- `python3` is available (`command -v python3`)

If the prerequisite is missing, halt with an error.

## Parsing Arguments

Parse the arguments as follows:
- {first_token}
- **Seat roster** (`SEATS=`): the seats staffing this run — a comma-separated subset of `fable`,
  `opus`, `sonnet`, `haiku`, `guest`, at most one of each, at least two. **Required.**
- **Env file** (`ENV_FILE=`): path to the guest model's env file (containing `API_BASE_URL=`,
  `API_KEY_FILE=`, and `MODEL=`). Required if and only if `SEATS=` includes `guest`.
- **Constraints doc** (`CONSTRAINTS=`): path to a requirements/invariants/conventions document.
  Optional.
- **Target** (`TARGET=`): {target_bullet}.
- **Remaining text**: free-form description of the {mode} target, minus the `KEY=` tokens. The
  keyed forms win wherever present; extract from what remains only what they did not supply:
  - The {mode} target and the constraints doc, when named in prose rather than by
    `TARGET=`/`CONSTRAINTS=`{prose_name}"""


def _debate_proceeding(*, mode: str, suggest_tail: str, charter_term: str) -> str:
    return rf"""### Seats are the invoker's call

There is no default roster. If the invocation names no seats, do not choose some — ask the user, and
**suggest `opus` + `sonnet` as a reasonable default for most {mode} jobs**: two strong local
pins whose blind spots differ. Widen with `fable` or `haiku` when {suggest_tail}; add `guest`
(with `ENV_FILE=`) to bring in a model from outside this harness.

Settle the roster here, before dispatch. The referee has no default of its own and **will refuse to
run** on a roster-less invocation — as it will if `guest` is named without an env-file path.

## Verbatim relay of instructions

The user's free-form instruction text — the substantive {mode} {charter_term} — MUST be
passed through verbatim when dispatching every seat on the roster and the alignment assessor. Do not
summarize, reword, compress, or rephrase it, even when the meaning seems preserved. Paraphrasing
loses nuance and shifts emphasis in ways the user did not authorize and cannot inspect.

The only exception: text explicitly marked as an aside to the referee with a `REFEREE NOTE:` prefix
(or equivalent unambiguous marker) is for the referee's consumption and is NOT relayed.

When confirming parsing to the user before dispatch, quote the substantive instruction text verbatim
so the user can inspect what will be relayed.

## Proceeding

Confirm your parsing of these inputs to the user before proceeding, then run the full MAD
{mode} process."""


@dataclass(frozen=True, kw_only=True)
class Mode:
    """The words the two debate referees' shared sections substitute; each referee defines one. A
    term is here only because two or more sections read it."""

    name: str
    """The mode: `a structured multi-model debate <name> process`."""

    run_dir: str
    """The run directory, without a trailing `/`."""

    gate: str
    """`apply the <gate> gate`."""

    seat: str
    """What a seat is: `an independent <seat>`; its plural adds `s`."""

    initial: str
    """A seat's initial output: `## Phase 1 — Independent <Initial>`, the per-seat `<seat>-<initial>.md`."""

    aggregate: str
    """The initial aggregate document's filename."""

    final: str
    """The final document's filename."""

    state: str
    """The session-state filename, the authoritative record."""

    agreement: str
    """What the seats reach: `the <agreement> is superficial`, `Exhaustion is not <agreement>`."""

    outcome: str
    """What the gate passes: `the <outcome> is not self-contained`, `a gate-passing <outcome>`."""

    field = ValueTypeField()


@dataclass(frozen=True)
class ParticipantContract(Section):
    """The contract every debate seat works under: inputs, adversarial disciplines, the two modes,
    retirement-gate participation and intellectual standards.

    It renders whole as a participant's body and as the extracted guest's system prompt, so it opens
    with its first sentence and carries nothing harness-specific.
    """

    def parts(self, ctx: Render) -> tuple[Part, ...]:
        return (("", _PARTICIPANT_CONTRACT),)


@dataclass(frozen=True, kw_only=True)
class RefereeRole(Section):
    """The referee's opening: what it orchestrates, and the two things it never does."""

    mode: Mode = Mode.field

    item: str
    """`the technical merit of any <item>`."""

    artifact: str
    """`You never modify <artifact>.`"""

    stances: str
    """`You do not take positions on technical <stances>.`"""

    def parts(self, ctx: Render) -> tuple[Part, ...]:
        return (
            (
                "mode, item, artifact, stances",
                _referee_role(
                    mode=self.mode.name,
                    gate=self.mode.gate,
                    item=self.item,
                    seats=f"{self.mode.seat}s",
                    artifact=self.artifact,
                    stances=self.stances,
                ),
            ),
        )


@dataclass(frozen=True, kw_only=True)
class RefereeSeats(Section):
    """The Seats section: what a seat is, and that nothing assumes how many there are."""

    mode: Mode = Mode.field

    role_note: str | None = None
    """The mode's own note on what its seats do, between the seat definition and the seat count."""

    def parts(self, ctx: Render) -> tuple[Part, ...]:
        note = () if self.role_note is None else (("role_note", self.role_note),)
        return (("mode", _seats_lead(self.mode.seat)), *note, ("", _SEAT_COUNT))


@dataclass(frozen=True, kw_only=True)
class DispatchMechanism(Section):
    """The Dispatch Mechanism section: the Agent tool and no recursion, the seat-to-agent table,
    parallel dispatch, and file-based instruction transport."""

    mode: Mode = Mode.field

    skill: str
    """The command that launched the referee, which it must never invoke itself."""

    corrupts: str
    """`the liaison's heredoc corrupting markdown/backtick-laden <corrupts> into empty files`."""

    charter: str
    """`write the user's **exact verbatim <charter>**`."""

    recipient_input: str
    """What every recipient reads besides the instructions: `the <recipient_input>, the requirements file`."""

    guest_inputs: str
    """The guest's bullet: `as RUN_DIR, plus <guest_inputs>, and the … contract path`."""

    file_borne: str
    """`only the <file_borne> *text* must be file-borne`."""

    input_staging: str | None = None
    """A bullet on how the run stages an input before dispatch, between the instructions bullet and
    the per-recipient bullets."""

    def parts(self, ctx: Render) -> tuple[Part, ...]:
        lead = _instruction_transport_lead(
            mode=self.mode.name, corrupts=self.corrupts, charter=self.charter, run_dir=self.mode.run_dir
        )
        staging = "" if self.input_staging is None else f"\n{self.input_staging}"
        seats = _instruction_transport_seats(
            run_dir=self.mode.run_dir,
            seat=self.mode.seat,
            recipient_input=self.recipient_input,
            guest_inputs=self.guest_inputs,
            file_borne=self.file_borne,
        )
        return (
            ("skill, mode", _dispatch_lead(skill=self.skill, seat=self.mode.seat)),
            ("", _DISPATCH_TABLE),
            ("", _PARALLEL_DISPATCH),
            (
                "mode, corrupts, charter, input_staging, recipient_input, guest_inputs, file_borne",
                f"{lead}{staging}\n{seats}",
            ),
        )


@dataclass(frozen=True, kw_only=True)
class RefereeInvocation(Section):
    """The Invocation section: what the referee receives at start, as one list."""

    name_label: str
    """The first input's label: `- **<name_label>**: used to name the output folder and documents`."""

    inputs: str
    """The mode's own input bullets, after the env-file bullet and before the requirements bullet."""

    conformer: str
    """The requirements bullet: `standards the <conformer> must conform to`."""

    def parts(self, ctx: Render) -> tuple[Part, ...]:
        return (
            (
                "name_label, inputs, conformer",
                f"{_invocation_lead(self.name_label)}\n{self.inputs}\n{_requirements_input(self.conformer)}",
            ),
        )


@dataclass(frozen=True, kw_only=True)
class SeatRoster(Section):
    """The Seat Roster section: validation and the two refusals, guidance for whoever composes the
    invocation, and how the guest's credentials arrive."""

    mode: Mode = Mode.field

    invoker_guidance: str | None = None
    """The mode's further guidance for the invoker, after the roster suggestion."""

    def parts(self, ctx: Render) -> tuple[Part, ...]:
        guidance = () if self.invoker_guidance is None else (("invoker_guidance", self.invoker_guidance),)
        return (("mode", _seat_roster(self.mode.name)), *guidance, ("", _LIAISON_CREDENTIAL_RELAY))


@dataclass(frozen=True, kw_only=True)
class RunFileSystem(Section):
    """The File System Conventions section: one run directory, its temp sandbox, and what is permanent."""

    mode: Mode = Mode.field

    completion: str
    """`may be deleted after the <completion> is complete`."""

    def parts(self, ctx: Render) -> tuple[Part, ...]:
        return (
            (
                "mode, completion",
                _referee_filesystem(mode=self.mode.name, run_dir=self.mode.run_dir, completion=self.completion),
            ),
        )


@dataclass(frozen=True, kw_only=True)
class IndependentPhase(Section):
    """Phase 1: dispatch the whole roster at once, what each seat receives, collecting each seat's
    output to its own file, and continuing past a failed seat."""

    mode: Mode = Mode.field

    charter: str
    """`write the verbatim <charter> to …/referee-instructions.md`."""

    inputs: str
    """The mode's own bullets of what each seat receives, before the isolation bullet."""

    say: str
    """The isolation bullet: `not what they <say>`."""

    degraded: str
    """`a one-seat run produces <degraded>`."""

    output_note: str | None = None
    """The mode's note on what a seat produces, between the dispatch inputs and collection."""

    def parts(self, ctx: Render) -> tuple[Part, ...]:
        receives = (
            f"{_phase1_dispatch_lead(charter=self.charter, run_dir=self.mode.run_dir)}\n{self.inputs}\n"
            f"{_seat_isolation_at_dispatch(self.say)}"
        )
        note = () if self.output_note is None else (("output_note", self.output_note),)
        collect = _phase1_guest_and_collect(
            ctx, seat=self.mode.seat, run_dir=self.mode.run_dir, initial=self.mode.initial
        )
        return (
            ("mode", f"## Phase 1 — Independent {self.mode.initial.capitalize()}"),
            ("", "**Dispatch** (binding):"),
            ("", _GUEST_DISPATCH_ORDERING),
            ("mode, charter, inputs, say", receives),
            *note,
            ("mode", collect),
            ("mode, degraded", _seat_failure_continues(final=self.mode.final, degraded=self.degraded)),
        )


@dataclass(frozen=True, kw_only=True)
class InitialAlignment(Section):
    """Phase 2: dispatch the assessor over every seat's Conclusions, then write the initial aggregate."""

    mode: Mode = Mode.field

    context: str
    """The first dispatch bullet: the context document the assessor reads."""

    outputs: str
    """`Every active seat's Conclusions section (not full <outputs>)`."""

    tail: str | None = OwnText.tail
    """The mode's note on how the assessor classifies, continuing the map-written sentence."""

    def parts(self, ctx: Render) -> tuple[Part, ...]:
        dispatch = f"Dispatch AA with:\n- {self.context}\n{_phase2_aa_dispatch(self.outputs)}"
        if self.tail is not None:
            dispatch = f"{dispatch} {self.tail}"
        return (
            ("", "## Phase 2 — Initial Alignment"),
            ("context, outputs, tail", dispatch),
            ("", _WRITE_ACCESS_HALT),
            ("mode", f"Write `{self.mode.aggregate}` (see Document Format)."),
            ("", "Update session state. Proceed to Phase 3."),
        )


@dataclass(frozen=True, kw_only=True)
class RoundDispatch(Section):
    """A debate round's Step 1: write the round's instructions, dispatch each seat with only its own
    files and the map, collect, and Step 1a, correcting the assessor."""

    mode: Mode = Mode.field

    unit: str
    """`a <unit> incorrectly marked as unique`."""

    instruction_points: str = "the points to address"
    """The instructions file holds `round directive + <instruction_points>`."""

    dispatch_points: str = "the points to address"
    """The first dispatch bullet: `The round-N-instructions file path (<dispatch_points> this round)`."""

    round_points: str | None = None
    """The mode's rules for what a round carries, between writing the instructions and dispatching;
    without them the two sentences run as one paragraph."""

    def parts(self, ctx: Render) -> tuple[Part, ...]:
        write = _round_instructions_write(points=self.instruction_points, run_dir=self.mode.run_dir)
        dispatch = _round_dispatch_inputs(points=self.dispatch_points, initial=self.mode.initial)
        if self.round_points is None:
            instruct: tuple[Part, ...] = (("instruction_points, mode, dispatch_points", f"{write} {dispatch}"),)
        else:
            instruct = (
                ("instruction_points, mode", write),
                ("round_points", self.round_points),
                ("dispatch_points, mode", dispatch),
            )
        misclassification = _aa_misclassification(
            seats=f"{self.mode.seat}s".capitalize(),
            unit=self.unit,
            initial=self.mode.initial,
            gate=self.mode.gate,
            seat=self.mode.seat,
        )
        return (
            ("", "**Step 1 — Dispatch seats**"),
            *instruct,
            ("mode", _round_isolation(initial=self.mode.initial, aggregate=self.mode.aggregate)),
            ("mode", _round_response_collect(self.mode.run_dir)),
            ("mode, unit", misclassification),
        )


@dataclass(frozen=True, kw_only=True)
class RoundGate(Section):
    """A debate round's Step 2, the gate over recorded stances, and Step 3, updating the assessor.

    The checks are numbered in order — the mode's own checks, the plain-language check, the
    implication test, the mode's further checks, then the failure rule — and the partial-concession
    rule names the two shared checks by the numbers they land on.
    """

    mode: Mode = Mode.field

    sameness: str
    """The plain-language check: `all of them describe the same <sameness>`."""

    premise: str
    """The implication test: `Given that <premise>, what follows`."""

    aspect: str
    """The implication test: `[related aspect of the <aspect>]`."""

    checks_after: tuple[str, ...]
    """The mode's own checks after the implication test, unnumbered; the last says what a pass is."""

    checks_before: tuple[str, ...] = ()
    """The mode's own checks before the plain-language check, unnumbered."""

    after_fails: str | None = None
    """The mode's text after the numbered checks."""

    after_concessions: str | None = None
    """The mode's text after the partial-concession rule."""

    def parts(self, ctx: Render) -> tuple[Part, ...]:
        shared = (
            _gate_plain_language_check(sameness=self.sameness, agreement=self.mode.agreement),
            _gate_implication_test(premise=self.premise, aspect=self.aspect, outcome=self.mode.outcome),
        )
        checks = (*self.checks_before, *shared, *self.checks_after, _GATE_FAILS)
        first = len(self.checks_before) + 1
        numbered = tuple(
            ("checks_before, sameness, mode, premise, aspect, checks_after", f"{number}. {check}")
            for number, check in enumerate(checks, start=1)
        )
        after_fails = () if self.after_fails is None else (("after_fails", self.after_fails),)
        after_concessions = () if self.after_concessions is None else (("after_concessions", self.after_concessions),)
        return (
            ("mode", f"**Step 2 — Apply {self.mode.gate} gate**"),
            ("", _EXPLICIT_STANCE),
            ("", _GATE_UNANIMITY),
            *numbered,
            *after_fails,
            ("mode", _partial_concessions(seat=self.mode.seat, steps=f"{first}–{first + 1}")),
            *after_concessions,
            ("", _ROUND_AA_UPDATE),
        )


@dataclass(frozen=True, kw_only=True)
class OutputPhase(Section):
    """Phase 4: write the final document, which must stand without the debate history."""

    mode: Mode = Mode.field

    deliverable_note: str | None = None
    """The mode's note on what the final document presents."""

    def parts(self, ctx: Render) -> tuple[Part, ...]:
        note = () if self.deliverable_note is None else (("deliverable_note", self.deliverable_note),)
        return (
            ("", "## Phase 4 — Output Documents"),
            ("mode", f"Write `{self.mode.final}` (see Document Format)."),
            *note,
            ("mode", f"`{self.mode.final}` must be actionable without reading the debate history."),
        )


@dataclass(frozen=True, kw_only=True)
class GateMetaRules(Section):
    """The gate's meta rules: where the gate logic lives, the referee's role in applying it, and what
    the gate is not."""

    mode: Mode = Mode.field

    role: str
    """The mode's own rules on the referee's role in applying the gate."""

    def parts(self, ctx: Render) -> tuple[Part, ...]:
        closing = _gate_closing_rules(agreement=self.mode.agreement, outcome=self.mode.outcome, state=self.mode.state)
        return (
            ("mode", f"## {self.mode.gate.capitalize()} Gate — Meta Rules"),
            ("", _GATE_META_LEAD),
            ("role", self.role),
            ("mode", closing),
        )


@dataclass(frozen=True, kw_only=True)
class DocumentFormat(Section):
    """The Document Format section's opening: where every file goes, the initial aggregate's format
    and the round document's."""

    mode: Mode = Mode.field

    paths: str
    """The mode's table of documents, filenames and audiences."""

    title: str
    """The initial aggregate's title line."""

    name: str
    """The round document's title placeholder: `# Debate Round [N] — [<name>]`."""

    resolution: str
    """`plain-language <resolution>, retirement tag`."""

    def parts(self, ctx: Render) -> tuple[Part, ...]:
        return (
            ("", "## Document Format"),
            ("", "### Output Paths"),
            ("mode", f"All output files are written to `{self.mode.run_dir}/`:"),
            ("paths", self.paths),
            ("", _OUTPUT_PATHS_NOTE),
            ("mode, title", _initial_aggregate_format(aggregate=self.mode.aggregate, title=self.title)),
            (
                "name, mode, resolution",
                _round_document_format(name=self.name, gate=self.mode.gate, resolution=self.resolution),
            ),
        )


@dataclass(frozen=True, kw_only=True)
class FinalDocumentFormat(Section):
    """The final document's format, and the roster record it opens with."""

    mode: Mode = Mode.field

    layout: str
    """The mode's fenced layout of the final document."""

    weight: str
    """`A reader judging the weight of <weight>`."""

    def parts(self, ctx: Render) -> tuple[Part, ...]:
        return (
            ("mode", f"### `{self.mode.final}`"),
            ("layout", self.layout),
            ("mode, weight", _roster_record_line(final=self.mode.final, weight=self.weight)),
        )


@dataclass(frozen=True, kw_only=True)
class SessionStateFormat(Section):
    """The Session State section: when it is written, and its snapshot's fenced layout, whose
    debate-rounds block is shared."""

    mode: Mode = Mode.field

    snapshot_head: str
    """The snapshot's layout before the debate-rounds block, its opening fence included."""

    snapshot_tail: str
    """The snapshot's layout after the debate-rounds block, its closing fence included."""

    def parts(self, ctx: Render) -> tuple[Part, ...]:
        return (
            ("mode", _session_state_lead(self.mode.state)),
            (
                "snapshot_head, snapshot_tail",
                f"{self.snapshot_head}\n\n{_SESSION_STATE_ROUNDS}\n\n{self.snapshot_tail}",
            ),
        )


@dataclass(frozen=True, kw_only=True)
class DebateCommand(Section):
    """A command that launches a debate: the definitions it loads, parsing its arguments, the roster
    being the invoker's call, verbatim relay of the instructions, and proceeding."""

    mode: str
    """The debate's mode, lowercase: `a multi-agent <mode> debate`; capitalised where the text is."""

    referee: str
    """The referee's definition file, loaded first: `@<harness dir>/agents/<referee>`."""

    first_token: Prose
    """The whole first bullet of Parsing Arguments, after its `- `."""

    target_bullet: str
    """The `TARGET=` bullet's text after the key."""

    prose_name: str = ""
    """A sub-bullet closing the Remaining text bullet, newline-led; empty where the first token is the
    run name."""

    suggest_tail: str
    """`Widen with fable or haiku when <suggest_tail>`."""

    charter_term: str
    """`the substantive <mode> <charter_term>`."""

    def parts(self, ctx: Render) -> tuple[Part, ...]:
        parsing = _debate_parsing(
            mode=self.mode,
            first_token=self.first_token.render(ctx),
            target_bullet=self.target_bullet,
            prose_name=self.prose_name,
        )
        proceeding = _debate_proceeding(mode=self.mode, suggest_tail=self.suggest_tail, charter_term=self.charter_term)
        return (
            ("referee", _debate_loads(ctx, self.referee)),
            ("mode, first_token, target_bullet, prose_name", parsing),
            ("mode, suggest_tail, charter_term", proceeding),
        )


@dataclass(frozen=True, kw_only=True)
class FoundationalBasis(Section):
    """A design topic's rule that only the supplied basis is load-bearing."""

    basis: str
    """`Build only on <basis>`."""

    imports: str
    """`<imports> are legitimate context and never load-bearing on their own`; plural-headed."""

    lead: str | None = OwnText.lead
    """The topic's domain text the rule continues, in one paragraph with it."""

    tail: str | None = OwnText.tail
    """The topic's text continuing the rule's paragraph."""

    def parts(self, ctx: Render) -> tuple[Part, ...]:
        text = (
            f"Build only on {self.basis} — the exclusive source of foundational truth for this construction. "
            f"{self.imports} are legitimate context and never load-bearing on their own: an appeal to one must "
            "be justified against the problem at hand."
        )
        if self.lead is not None:
            text = f"{self.lead}\n{text}"
        if self.tail is not None:
            text = f"{text} {self.tail}"
        return (("lead, basis, imports, tail", text),)


@dataclass(frozen=True, kw_only=True)
class ConditionalMarking(Section):
    """A design topic's rule that a unit resting on an unsupplied piece is marked conditional."""

    unit: str
    """`Mark any <unit> that depends on …`."""

    gap: str
    """`… that depends on <gap>`."""

    state: str
    """`surfaces as a candidate for <state>`."""

    lead: str | None = OwnText.lead
    """The topic's method text the rule closes, in one paragraph with it."""

    def parts(self, ctx: Render) -> tuple[Part, ...]:
        text = (
            f"Mark any {self.unit} that depends on {self.gap}. A marked {self.unit} is conditional and surfaces "
            f"as a candidate for {self.state}."
        )
        if self.lead is not None:
            text = f"{self.lead}\n{text}"
        return (("lead, unit, gap, state", text),)


@dataclass(frozen=True, kw_only=True)
class ConvergenceCriteria(Section):
    """A design topic's Convergence Criteria section: the terminal states a debate ends in, lettered,
    with multi-path convergence second and unresolved divergence last."""

    converged: str
    """The topic's first terminal state, item `(a)`, as its list line."""

    result: str
    """Multi-path convergence: `reach the same <result>`."""

    paths: str
    """Multi-path convergence: `via demonstrably independent <paths>`."""

    under_determined: tuple[str, ...]
    """The topic's under-determination states, items `(c)` onward, each as its list lines opening
    `- **(<its letter>)`; an item opening otherwise is refused."""

    divergence: str
    """Unresolved divergence: `participants remain at <divergence> after the round cap`."""

    record: str = ""
    """Unresolved divergence: `All candidates are documented<record> and preserved`."""

    intro: str | None = None
    """The topic's paragraph opening the section."""

    def __post_init__(self) -> None:
        for index, item in enumerate(self.under_determined):
            opening = f"- **({chr(ord('c') + index)})"
            if not item.startswith(opening):
                raise InputError(f"under_determined item {index} must open '{opening}', the letter it is given")

    def parts(self, ctx: Render) -> tuple[Part, ...]:
        letter = chr(ord("c") + len(self.under_determined))
        outcomes = "\n".join(
            (
                self.converged,
                f"- **(b) Multi-path convergence**: participants reach the same {self.result} via demonstrably "
                f"independent {self.paths}. Both paths are preserved in the deliverable as mutually reinforcing "
                f"confirmations of the same {self.result}. This is a strong-positive outcome.",
                *self.under_determined,
                f"- **({letter}) Unresolved divergence**: participants remain at {self.divergence} after the round "
                f"cap. All candidates are documented{self.record} and preserved for human arbitration.",
            )
        )
        intro = () if self.intro is None else (("intro", self.intro),)
        return (
            ("", "## Convergence Criteria"),
            *intro,
            ("", "A successful debate terminates in one of these states:"),
            ("converged, result, paths, under_determined, divergence, record", outcomes),
        )


@dataclass(frozen=True, kw_only=True)
class ReferenceValidation(Section):
    """A design topic's rule for a known reference value: compare at the end, never build on it.
    Heading-less: each topic names the value its own way."""

    examples: str
    """`a known reference value (e.g., <examples>)`."""

    construction: str
    """What a participant builds: `compute their <construction>'s prediction`."""

    caveat: str
    """`is not automatically wrong — <caveat> —`."""

    tail: str | None = OwnText.tail
    """The topic's text continuing the rule's last paragraph."""

    def parts(self, ctx: Render) -> tuple[Part, ...]:
        compare = (
            f"Where the problem has a known reference value (e.g., {self.examples}), participants may compute their "
            f"{self.construction}'s prediction and compare. A {self.construction} that disagrees with the reference "
            f"is not automatically wrong — {self.caveat} — but the disagreement must be acknowledged and explained."
        )
        boundary = (
            f"A reference value MUST NOT be load-bearing in the {self.construction} itself. It may be used at the "
            "end for validation, and its role must be stated explicitly."
        )
        if self.tail is not None:
            boundary = f"{boundary} {self.tail}"
        return (("examples, construction, caveat", compare), ("construction, tail", boundary))
