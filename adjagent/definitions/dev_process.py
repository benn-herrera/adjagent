"""dev-process: the skill that carries one development process for the main session — planning,
dispatch, acceptance, checkpoints and post-plan review — and the references that start a project
on it, bind its terms, adopt it into a project with process of its own and run a release.

Each term is one constant here, and every mention in the skill's five files interpolates it, so no
two files can name a slot differently.
"""

from adjagent import clauses
from adjagent.definition import Definition, SkillFile
from adjagent.vocabulary import Kind

ACTIVE_PLAN_TERM = "active plan"
PARKED_PLANS_TERM = "parked-plans directory"
SCRATCH_TERM = "scratch directory"
EDIT_GATE_TERM = "edit gate"
CHECKPOINT_GATE_TERM = "checkpoint gate"
REFERENCE_SEARCH_TERM = "reference search"
STEP_DOWN_MODEL_TERM = "step-down model"
STEP_DOWN_APPLICATION_TERM = "step-down application"
POST_PLAN_REVIEWERS_TERM = "post-plan reviewers"
BURNDOWN_LIST_TERM = "burndown list"
PLAN_SIZE_LIMIT_TERM = "plan size limit"

DEFINITIONS = (
    Definition(
        name="dev-process",
        kind=Kind.SKILL,
        description=(
            "Production-grade development process for agentic work under human ownership: starting, "
            "planning, executing, delivering."
        ),
        body=f"""Where the project's CONVENTIONS.md states a local rule that departs from a rule here, the project's
rule governs.

## Route

| the situation | read |
| --- | --- |
| starting a new project | `references/new-project.md` |
| a rule needs a term that has no default and is unbound, or the user asks to set up the process | `references/project-setup.md` |
| a project with process already written takes up this skill | `references/adopting.md` |
| planning or running a release | `references/release.md` |

A reference is read only when its row is reached; the rest of this file applies in every case.

## Terms

The rules name slots by these terms. A project binds a term with a line `<term>: <value>` in
CONVENTIONS.md, and a binding replaces the default. A term marked — has no default.

| Term | Default | What it is |
| --- | --- | --- |
| {ACTIVE_PLAN_TERM} | `ACTIVE_PLAN.md` at the repository root | the one plan under way |
| {PARKED_PLANS_TERM} | `ROADMAP_PLANS/` | where partly-planned work waits |
| {SCRATCH_TERM} | `{clauses.PROJECT_TEMP_DIR}/` at the repository root | untracked working files |
| {EDIT_GATE_TERM} | — | the runner targets that verify one edit |
| {CHECKPOINT_GATE_TERM} | — | the runner targets run before a checkpoint commit |
| {REFERENCE_SEARCH_TERM} | `git grep -l '<name>'` | lists every file that references a name |
| {STEP_DOWN_MODEL_TERM} | the model the sentence after this table names; — where none follows | the model a mechanical dispatch runs on |
| {STEP_DOWN_APPLICATION_TERM} | — | how a mechanical dispatch gets the {STEP_DOWN_MODEL_TERM} where a dispatch cannot choose its model |
| {POST_PLAN_REVIEWERS_TERM} | the agent whose domain each change touched: the coder for each changed language, `{clauses.ref(name="architect")}` where structure changed, `{clauses.ref(name="tech-writer")}` where documents changed, `{clauses.ref(name="prompt-engineer")}` where model-facing text changed | the agents that review a finished plan |
| {BURNDOWN_LIST_TERM} | `<plan>_REVIEW_BURNDOWN.md` beside the plan, `<plan>` being its file name without `.md` | the post-plan review's findings, which the revision agents execute from |
| {PLAN_SIZE_LIMIT_TERM} | 800 lines | the length past which a plan or design is diced |

Where CONVENTIONS.md binds no {STEP_DOWN_MODEL_TERM}, it is `{clauses.STEP_DOWN_MODEL}`.

Before treating a term as unbound, run `git grep -n -F '<term>:' -- '*CONVENTIONS*'` with the term's
exact name; no hit, or a hit only in a `TODO:` note, means unbound. When a rule needs a term that
has no default and is unbound, ask the user for it then, through `references/project-setup.md`,
before applying the rule: never substitute a plausible value. *Purpose:* a guessed gate passes work
the project's own gate would refuse.

## Plans

- Plans are tracked files; notes not yet shaped into a plan are scratch, in the {SCRATCH_TERM}.
  *Purpose:* a plan survives in version control, and unshaped notes are not mistaken for one.
- A reference's target is at least as durable as the document that cites it: a tracked document
  cites only tracked paths; an untracked brief may cite scratch. *Purpose:* a citation that outlives
  its target sends the next reader to invent what it said.
- Rigor scales with the code's intended lifetime. The plan states each package's intended lifetime,
  and by default it gets: **shipped** → the whole of this skill; **exploratory** → the {EDIT_GATE_TERM} and
  the {CHECKPOINT_GATE_TERM}, no post-plan review; **throwaway** → the {SCRATCH_TERM} only, never committed.
  The plan sets the lifetime, never the agent doing the work; code that outlives its stated lifetime
  gets the whole process before it ships. *Purpose:* process costs what the code will cost to keep,
  and no one lowers the bar by leaving the lifetime unstated.
- One {ACTIVE_PLAN_TERM}: kickoff decisions, package boundaries, sequencing, status. It carries outcomes,
  their consequences and the principles still steering open choices, never decision history; its
  status moves as packages land. *Purpose:* agents execute from one current statement of intent, not
  from an account of how it was reached.
- On landing, the plan is replaced by the next plan, or deleted. *Purpose:* a landed plan left in
  place reads as work still under way.
- Partly-planned work waits, tracked, in the {PARKED_PLANS_TERM}. *Purpose:* design done ahead of its
  turn survives without competing with the {ACTIVE_PLAN_TERM}.
- A document or leaf the plan names as settling its subject outranks the plan: the work implements
  the document or leaf, the landing commit names the plan line the document or leaf overrode, and
  the landing does not edit the document or leaf.
  *Purpose:* a disagreement between plan and requirement is resolved in the open, never by quietly
  rewriting the requirement.
- A plan or design longer than the {PLAN_SIZE_LIMIT_TERM} is diced (the `{clauses.ref(name="docdicer")}` skill), and dispatches
  cite its leaves. *Purpose:* each executor reads whole the part it acts on.
- An approved plan runs to completion: blockers that need the user surface during planning.
  *Purpose:* the user approves once and is not called back mid-run for a question planning could
  have asked.

## Dispatchability

A work package is dispatchable only when:

- its scope is named in files, packages or symbols, never a span of design sections. *Purpose:*
  scope can be checked against a diff;
- each fact it acts on carries the command and its answer, or the quoted line. *Purpose:* the
  executor re-runs the check instead of trusting a reading that may have gone stale;
- a change to a type, signature, test double, or behaviour a test or fixture pins lists every
  referencing file, with the {REFERENCE_SEARCH_TERM} and its answer. *Purpose:* no referencing file
  is found broken after the package reports done, and updating an expectation the change forces is
  in scope;
- its done-line is stated in runner targets. *Purpose:* done is a run anyone can repeat, not a
  judgment;
- a before/after measurement done-line carries a passing run on the base commit, taken during
  planning. *Purpose:* a failed comparison is known to come from the change, not from a baseline that
  never passed;
- it has had `{clauses.ref(name="prompt-engineer")}` usability review, then `{clauses.ref(name="architect")}` revision. *Purpose:* the agent that
  executes it can act on it before it costs a dispatch;
- its brief names the {EDIT_GATE_TERM}'s targets, run after each edit. *Purpose:* each edit is
  verified while its cause is fresh.

A plan whose packages fail this is neither offered for approval nor dispatched. *Purpose:* what is
approved can run as approved.

Each plan section gets one review and one revision; a revision applying that review's findings is
not re-reviewed. A later change — a package added, a decision reversed, a section rewritten — gets a
review of the changed text only, plus a check that the rest of the plan cites no superseded form of
it. Settled calls are not reopened unless the change targets them. *Purpose:* each round reviews
only text no reviewer has seen, so review converges instead of re-litigating.

## Dispatch

- Rate each dispatch mechanical or expert by what it must decide, not how much it types: mechanical
  is every edit enumerated, no design choice, no debugging; anything else is expert. Mechanical
  runs on the {STEP_DOWN_MODEL_TERM}, through the {STEP_DOWN_APPLICATION_TERM} where a dispatch cannot choose
  its model; expert runs on the agent's own model. *Purpose:* settled work costs less, and judgment
  keeps the model it needs.
- Before dispatching, state the agent count and model. More than one agent at once on the most
  capable model the installed agents name waits for a go that names the count. *Purpose:* a
  fan-out's cost shows only once it is spent.
- Read an agent's definition before briefing it, if you have not read it this session. *Purpose:*
  the brief adds to what the agent carries instead of contradicting or repeating it.
- A brief adds the task's facts to the agent's definition; it never widens or replaces the question
  the definition gives the agent. *Purpose:* the agent keeps the discipline it was built for.
- Direction an agent reads carries outcome and operative consequence only, plus a principle that
  still steers open choices. Decision history — who ruled, when, which branches lost, the deciding
  narrative — stays in the audit record (changelog, ruling record, owner channel), out of briefs,
  plan dispatch sections and table cells. A quotation that states the requirement is direction; one
  that records who authorized it is history. *Purpose:* history read as direction reopens settled
  choices.
- A package whose code calls a network API carries that API's usage guidelines in its brief; where
  the API publishes none, the brief sets a reasonable, polite default for each of rate,
  concurrency, retry and backoff, identification and a per-run request cap. *Purpose:* the agent
  writing the code cannot comply with limits it was never given.
- Packages that share a build run serially in the shared tree. *Purpose:* one package's half-done
  edit does not fail another's build.

## Acceptance

- A returned report is evidence, not a conclusion. Its facts are the strong half — the agent has
  just read the files — so check them against the artifact itself (the diff, the code, the rendered
  output) before the commit that accepts the work. Its judgments, framings and hedges are the weak
  half — it lacks this thread's context — so test them against what is already decided or ruled
  out. An agent reopening a settled question is the normal case, not a signal. *Purpose:* an
  agent's confident error is caught before it is committed.
- Audit the diff, not the report, against these classes before accepting: entry points or switches
  that exist only for testing; verification that cannot be repeated, or evidence that exists only in
  the report; a loosened gate, pin or assertion; a second home for a value or mechanism; work beyond
  the dispatched scope. A violation blocks acceptance. *Purpose:* the defects a passing run hides are
  looked for where they live.
- A report that flags a departure from scope is redispatched or escalated, never accepted on your
  own reading of the scope. *Purpose:* a scope change is decided by the scope's owner, not settled by
  whoever accepts the work.
- An acceptance claim names which done-line items and audit classes it checked; a green run alone is
  not acceptance. *Purpose:* a skipped check shows as a missing name.

## Gates and checkpoints

- The {CHECKPOINT_GATE_TERM} runs once, before a checkpoint commit, never between edits. *Purpose:*
  the slow gate is paid once.
- A checkpoint is incomplete until every document describing the changed behaviour is updated, the
  contract documents included. *Purpose:* what a checkpoint ships matches its documentation.

## Post-plan review

- Every plan holding a shipped package ends with a review, revision and burndown section.
  *Purpose:* review is planned work, not a step dropped when the plan lands.
- The {POST_PLAN_REVIEWERS_TERM} are given the contract documents and not the plan, and review the
  changes and their tests against the project's standards and fitness for purpose. *Purpose:* they
  judge what shipped, not how well it matches the plan's account of itself.
- The review's findings go to the {BURNDOWN_LIST_TERM}. *Purpose:* revision works from one list.
- The {BURNDOWN_LIST_TERM} gets `{clauses.ref(name="prompt-engineer")}` usability review, then revision by its author,
  before any revision agent is dispatched from it. *Purpose:* the agents that execute from it can
  act on each item without inventing what it leaves open.
- The review of a release's hardening plan (`references/release.md`), and any review the user asks
  to include one, includes a user-flow audit: of the project's user-facing commands and flows, for
  elements that are redundant, over-composed, split finer than any use needs, ordered against how
  they are used, unnecessary or poorly named. It executes nothing and feeds the next design.
  *Purpose:* friction that no single change caused is found before it accumulates across releases.

## Pre-release

- While the repository has no release tag, replace a mechanism outright: no dual-write, shim or
  rollback flag; git is the rollback. *Purpose:* nothing depends on the old form yet, so
  compatibility code is only cost.
- In a release's hardening plan, where this rule and the hardening rules (`references/release.md`)
  pull apart, the hardening rules govern: a replacement too wide to be a fix is deferred, not made.
  *Purpose:* the release converges on what has been verified.""",
        files=(
            SkillFile(
                path="references/new-project.md",
                body=f"""Take a project from nothing to working under this skill. Work through the steps in order: each
one's answer feeds the next.

1. **What it produces.** Establish with the user what the project's output is — a CLI, library,
   service, app, document set, paper, analysis.
2. **Whether it needs code.** Where it does, settle its language and platform: draw out the user's
   constraints — target platform, ecosystem, deployment, performance, their own familiarity — and
   the `{clauses.ref(name="architect")}` agent may propose from them. This skill recommends no language. *Purpose:* the
   choice follows the project's constraints, not a habit.
3. **The contract documents**, drafted from 1 and 2: THESIS.md by you with the user; SPEC.md and
   ARCHITECTURE.md by `{clauses.ref(name="architect")}`, or SPEC.md by `{clauses.ref(name="tech-writer")}` for a project with no code;
   CONVENTIONS.md by you, from the choices made in 2. A project with no code may omit
   ARCHITECTURE.md, at the owner's choice. Dicing them is the `{clauses.ref(name="docdicer")}` skill's. *Purpose:* each
   document is drafted by the agent whose discipline it needs.
4. **A runner**, if one is needed: `just` by default; `make` only where the project has targets that
   must rebuild only when their inputs are newer than their outputs. A project on an ecosystem's
   native task surface (npm scripts, cargo) still gets a justfile whose recipes call into it.
   Record the choice in CONVENTIONS.md, then settle the runner targets the {EDIT_GATE_TERM} and the
   {CHECKPOINT_GATE_TERM} will name. *Purpose:* every gate binding takes the same form.
5. Go to `references/project-setup.md` to bind the terms.

A project with no code has gates too: its {EDIT_GATE_TERM} may be a link check or a document build.""",
            ),
            SkillFile(
                path="references/project-setup.md",
                body=f"""Bind the terms this skill's rules need and the project has not bound. Ask the owner about each,
and record each answer as a binding (SKILL.md, *Terms*). Where the project has no CONVENTIONS.md,
propose creating one to hold them. Reached because a rule needs one term, ask for that term alone.

- **Each term marked — in SKILL.md's *Terms* table, other than the two below.** Ask for its value;
  for a gate, the runner targets by name. Record every answer.
- **The {STEP_DOWN_MODEL_TERM}.** Offer the default named in the sentence after the *Terms* table, where
  one is there; where none is, it is a term with no default. Record the answer only where it departs
  from the default.
- **The {STEP_DOWN_APPLICATION_TERM}.** Only where this session's dispatch tool cannot set a model:
  ask how a mechanical dispatch gets the {STEP_DOWN_MODEL_TERM}. Record the answer.

A term with no default that the owner leaves unanswered is written into CONVENTIONS.md as a note
`TODO: <term>:`, so the lookup in SKILL.md's *Terms* finds it, and setup moves on to the next.
*Purpose:* setup reaches its end, and the gap sits where the term's binding will go.""",
            ),
            SkillFile(
                path="references/adopting.md",
                body="""Bring a project whose process is already written somewhere under this skill. Nothing moves
without the user's go.

1. **Find every place the project states process**, wherever it lives: a CONVENTIONS tree or single
   file, CONTRIBUTING, README, AGENTS.md, a harness agents file, a linked wiki. Text between the
   `vvv-adjagent` and `^^^-adjagent` marker lines, or in a file under a `!GENERATED!` or
   `!INSTALLED!` banner, belongs to the installed agent set, not the project: skip it. When this
   step finds no process statement in any place it searched, there is nothing to classify: go to
   `references/project-setup.md`.
2. **Classify each statement** against this skill's rules:
   - **duplicate** of a rule here → propose removing the local copy;
   - **value** for a term here → propose recording it as a binding (SKILL.md, *Terms*);
   - **refinement**, a stricter or narrower version of a rule here → propose stating it in
     CONVENTIONS.md as a local rule;
   - **contradiction** of a rule here → propose stating it in CONVENTIONS.md as a local rule, which
     overrules this skill's;
   - **no counterpart** → the project's own; it stays where it is.

   Where the project has no CONVENTIONS.md, propose creating one for the values, refinements and
   contradictions. *Purpose:* each rule has one home, and the project's departures are written
   where this skill's reader looks for them.
3. **Present the classification** with a count per class and the sections of this skill the
   contradictions hit. A statement no class fits cleanly is a question for the user.
4. **Where contradictions hit *Dispatch*, *Acceptance*, or *Gates and checkpoints*, say plainly that
   this skill does not fit the project.** *Purpose:* overruling those sections leaves a different
   process running under this one's name.""",
            ),
            SkillFile(
                path="references/release.md",
                body=f"""A release is a sequence of plans, each one job — the work one engineer would contribute — made the
{ACTIVE_PLAN_TERM} in turn under one owner. Its state is what exists: its jobs wait in the
{PARKED_PLANS_TERM}, each naming the release in one line, and what it did not choose is on `ROADMAP.md`.
Its phases: planning lays out the jobs; free development activates them one at a time, each an
ordinary plan with its own post-plan review; the last plan, the hardening plan, hardens the release
and delivers it.

## Planning

- Lay out the chosen features as the release's jobs, each a plan in the {PARKED_PLANS_TERM} naming the
  release; the last is the hardening plan, and its line says so. *Purpose:* what remains of the
  release is read from what is parked, not recalled.
- Each feature considered and not chosen goes into `ROADMAP.md`, and design already done for it into
  the {PARKED_PLANS_TERM} with no release named. *Purpose:* scoping a feature out loses nothing, so
  nothing is kept in to save it.
- Every package in the release's jobs is shipped (SKILL.md, *Plans*): exploratory work chosen for
  it is re-rated now. *Purpose:* the process a shipped package owes is paid before hardening, not
  during it.

## The line

- Free development ends when the owner activates the hardening plan; never activate it yourself,
  including when the other jobs have landed. *Purpose:* the scope closes when the owner decides it
  has.
- After the line, nothing new is activated for the release: a new feature or improvement goes into
  `ROADMAP.md`. *Purpose:* hardening converges only on a fixed scope.

## Hardening

- A fix changes only what its defect needs; no refactor, rename or cleanup rides along — those go
  into `ROADMAP.md`. *Purpose:* each fix leaves intact everything already verified, including
  checks a person made that no test repeats.
- A livable issue whose fix needs more change than the defect's own site is deferred: record it in
  `ROADMAP.md` and name it in the hardening plan's status. *Purpose:* the release ships a known issue
  rather than an unverified change of mechanism.
- Each fix's report and commit message state what else it can affect: callers, data, behaviour
  outside the defect's own path. Whether hardening is converging is the owner's judgment of those
  consequences, never a measure of the change's size. *Purpose:* the owner judges from what a fix
  can reach, which its size does not show.

## Delivery

- The release is tagged after the hardening plan's post-plan review, on a commit the
  {CHECKPOINT_GATE_TERM} passed on; any change after that run, a version bump included, runs it again.
  *Purpose:* what ships is what was reviewed and verified.""",
            ),
        ),
    ),
)
