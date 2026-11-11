"""development: the skill that carries one development process for the main session — design,
planning, dispatch, acceptance, checkpoints and post-plan review — and the references that start a
project on it, bind its terms, adopt it into a project with process of its own, keep its project
documents and run a release.

Each term is one constant here, and every mention in the skill's six files interpolates it, so no
two files can name a slot differently.
"""

from adjagent import clauses
from adjagent.definition import Definition, SkillFile
from adjagent.vocabulary import Kind

ACTIVE_DESIGN_TERM = "active design"
ACTIVE_PLAN_TERM = "active plan"
PARKED_PLANS_TERM = "parked-plans directory"
SCRATCH_TERM = "scratch directory"
CHECKPOINT_GATE_TERM = "checkpoint gate"
REFERENCE_SEARCH_TERM = "reference search"
STEP_DOWN_MODEL_TERM = "step-down model"
STEP_DOWN_APPLICATION_TERM = "step-down application"
POST_PLAN_REVIEWERS_TERM = "post-plan reviewers"
REVIEW_DOCUMENT_TERM = "review document"
PLAN_SIZE_LIMIT_TERM = "plan size limit"
PERIODIC_REVIEW_INTERVAL_TERM = "periodic review interval"

DEFINITIONS = (
    Definition(
        name="development",
        kind=Kind.SKILL,
        description=(
            "Production-grade development process for agentic work under human ownership: starting, "
            "designing, planning, executing, delivering."
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
| writing, revising or reviewing the project documents | `references/project-documents.md` |

A reference is read only when its row is reached; the rest of this file applies in every case.

## Terms

The rules use these terms.

**Fixed terms.**

| Term | Fixed as | What it is |
| --- | --- | --- |
| {ACTIVE_DESIGN_TERM} | `ACTIVE_DESIGN.md` at the repository root | the one design under way, which feeds a plan |
| {ACTIVE_PLAN_TERM} | `ACTIVE_PLAN.md` at the repository root | the one plan under way |
| {PARKED_PLANS_TERM} | `ROADMAP_PLANS/` at the repository root | where partly-planned work waits |
| {SCRATCH_TERM} | `{clauses.PROJECT_TEMP_DIR}/` at the repository root | untracked working files |
| {REFERENCE_SEARCH_TERM} | `git grep -l '<name>'` | lists every file that references a name |
| {POST_PLAN_REVIEWERS_TERM} | the agent for each domain the plan changed substantively — a change where a defect would pass unseen without that seat: the coder for each changed language, `{clauses.ref(name="architect")}` where structure, or the project documents' claims about the code, changed, `{clauses.ref(name="tech-writer")}` where READMEs or human-facing guides changed, `{clauses.ref(name="prompt-engineer")}` where model-facing text, the project documents or ROADMAP.md changed | the agents that review a finished plan |
| {REVIEW_DOCUMENT_TERM} | `ACTIVE_PLAN_REVIEW.md` at the repository root | the post-plan review's findings, which the post-plan burndown is drafted from |

**Bindable terms.** A project binds one with a line `<term>: <value>` in CONVENTIONS.md, and a
binding replaces the default. A term marked — has no default.

| Term | Default | What it is |
| --- | --- | --- |
| {CHECKPOINT_GATE_TERM} | — | the runner targets run before a checkpoint commit |
| {STEP_DOWN_MODEL_TERM} | the model the sentence after this table names; — where none follows | the model a mechanical dispatch runs on |
| {STEP_DOWN_APPLICATION_TERM} | — | how a mechanical dispatch gets the {STEP_DOWN_MODEL_TERM} where a dispatch cannot choose its model |
| {PLAN_SIZE_LIMIT_TERM} | 800 lines | the length past which a plan or design is diced |
| {PERIODIC_REVIEW_INTERVAL_TERM} | 3 | the number of landed plans between periodic reviews |

Where CONVENTIONS.md binds no {STEP_DOWN_MODEL_TERM}, it is `{clauses.STEP_DOWN_MODEL}`.

Before treating a bindable term as unbound, run `git grep -n -F '<term>:' -- '*CONVENTIONS*'` with
the term's exact name; no hit, or a hit only in a `TODO:` note, means unbound. When a rule needs a
bindable term that has no default and is unbound, ask the user for it then, through
`references/project-setup.md`, before applying the rule: never substitute a plausible value.
*Purpose:* a guessed gate passes work the project's own gate would refuse.

## Skipping a step

- A step that applies to the work is dropped only when the user directs it, never because you judge
  it unneeded. A lifetime the user approves in a plan is such a direction for the steps that
  lifetime drops. *Purpose:* only the user changes how much process the work gets.
- You may propose a skip: a lighter plan where the code's intended lifetime warrants it, naming the
  lifetime; or going straight to the plan, where the design is small and was substantively settled
  in the conversation so far. The proposal names each step it drops and what that step's
  *Purpose* says is lost. It takes effect only when the user adopts it.
- When the user directs a skip you did not propose, advise once, at the decision: name the step and
  what its *Purpose* says is lost. The user's answer stands for that work; raise it again only if
  circumstances change in a way that bears on that *Purpose*. *Purpose:* advice about the process is
  given without being repeated.
- Record a directed skip as the user's direction where later readers look: the plan's stated
  lifetime, or a line in place of the section it drops. Going straight to the plan needs no record:
  a plan with no design behind it shows that on its face. *Purpose:* a later reader does not take a
  directed skip for a gap and raise it again.
- A condition that a directed skip drops counts as met wherever another rule requires it,
  *Dispatchability* included.

## Design

- The {ACTIVE_DESIGN_TERM} is where a request becomes the design a plan is written from. Design comes
  before a plan; going straight to the plan is a skip (*Skipping a step*). *Purpose:* requirements
  are settled and reviewed before packages are cut from them, and the step between a request and a
  plan has a known place.
- A design holds the requirements, decisions and constraints a plan is written from, and the
  questions still open for the user. It never holds packages, sequencing or status: those belong to
  the plan.
- The user accepts the design before a plan is written from it.
- The design is deleted, with its tree if it was diced, in the commit that adds the plan written
  from it, whether that plan is active or parked. That plan carries what it needs from the design
  and cites none of it. *Purpose:* a design that stays in place after its plan exists reads as work
  still in design, and a plan citing a deleted design is a citation that outlives its target.

## Plans

- Plans and designs are tracked files; notes not yet shaped into either are scratch, in the
  {SCRATCH_TERM}. *Purpose:* a plan or design survives in version control, and unshaped
  notes are not mistaken for either.
- A reference's target is at least as durable as the document that cites it: a tracked document
  cites only tracked paths; an untracked brief may cite scratch. *Purpose:* a citation that outlives
  its target sends the next reader to invent what it said.
- Rigor scales with the code's intended lifetime (*Skipping a step*). The plan states each
  package's intended lifetime, and by default it gets: **shipped** → the whole of this skill;
  **exploratory** → the done-line and the {CHECKPOINT_GATE_TERM}, no post-plan review;
  **throwaway** → the {SCRATCH_TERM} only, never committed. The plan sets the lifetime,
  never the agent doing the work; code that outlives its stated lifetime gets the whole process
  before it ships. *Purpose:* process costs what the code will cost to keep, and no one lowers
  the bar by leaving the lifetime unstated.
- One {ACTIVE_PLAN_TERM}: kickoff decisions, package boundaries, sequencing, status. A plan or
  design carries outcomes, their consequences and the principles still steering open choices, never
  decision history. *Purpose:* agents execute from one current statement of intent, not from an
  account of how it was reached.
- On landing, the plan is replaced by the next plan, or deleted. *Purpose:* a landed plan left in
  place reads as work still under way.
- Partly-planned work — a design set aside before its plan is written, or a plan not yet active —
  waits, tracked, in the {PARKED_PLANS_TERM}. It leaves that directory when it becomes the
  {ACTIVE_DESIGN_TERM} or the {ACTIVE_PLAN_TERM}, or when it is abandoned; superseded work counts as
  abandoned. Work can only finish as the {ACTIVE_PLAN_TERM}. *Purpose:* design done ahead of its turn
  survives without competing with the {ACTIVE_PLAN_TERM}, and one piece of work is in one place at a
  time.
- A document or leaf the plan names as settling its subject outranks the plan: the work implements
  the document or leaf, the landing commit names the plan line the document or leaf overrode, and
  the landing does not edit the document or leaf.
  *Purpose:* a disagreement between plan and requirement is resolved in the open, never by quietly
  rewriting the requirement.

- A plan or design longer than the {PLAN_SIZE_LIMIT_TERM} when it is offered for approval is diced
  (the `{clauses.optional_ref(name="docdicer")}` skill), and dispatches cite its leaves. Once approved, a plan is diced only
  when the user asks. *Purpose:* each executor reads whole the part it acts on.

- An approved plan runs to completion: blockers that need the user surface during planning.
  *Purpose:* the user approves once and is not called back mid-run for a question planning could
  have asked.

- Each section of a plan or design gets one `{clauses.ref(name="prompt-engineer")}` review and one
  revision; a revision applying that review's findings is not re-reviewed. A later change — a
  package added, a decision reversed, a section rewritten — gets a review of the changed text only,
  plus a check that the rest of the document cites no superseded form of it. Settled calls are not
  reopened unless the change targets them. *Purpose:* each round reviews only text no reviewer has
  seen, so review converges instead of re-litigating.

## Plan status

Where a plan, active or parked, states any of the following, it states it in this form. Nothing here
makes a plan state anything it otherwise would not. *Purpose:* a tool reading plans reads every plan
the same way.

- A package heading opens with its ID, then its title, at any heading level. The ID is unique
  within the plan and contains no spaces (`P1`, `WP2a`, `S0`).
- Package status goes in one table under a `## Status` heading, with a `Package` column, a
  `State` column and a `Rating` column; other columns are free. Each package has one row. A row
  naming no package, such as a kickoff commit or a note, has an empty `Package` cell.
- A `State` cell opens with its state word, `dispatchable`, `in progress` or `landed`; anything after
  the word is a note (`landed: inventory 49`). `dispatchable`: the package meets every condition in
  *Dispatchability*. `in progress`: dispatched and not landed. `landed`: accepted and committed, set
  in the commit that accepts it. A row with no state word is drafted.
- Each package's `Rating` cell opens with `mechanical` or `expert`, rated as *Dispatch* rates its
  dispatch; anything after the word is a note. *Purpose:* whoever reads the table sees which work runs on the
  {STEP_DOWN_MODEL_TERM}.
- The post-plan review and the post-plan burndown (*Post-plan review*) are packages, each with its
  own ID and row; the review's title opens with `Post-plan review`, the burndown's with
  `Post-plan burndown`.
- Set a state in the same turn as the act that changes it. *Purpose:* the table never trails the
  work.

After each edit to a plan, run `check-plan` on it (on its `entry-point.md` where it is diced; the
`{clauses.optional_ref(name="docdicer")}` skill) and fix what it reports.

## Dispatchability

A work package is dispatchable only when:

- its scope is named in files, packages or symbols, never a span of design sections. *Purpose:*
  scope can be checked against a diff;
- each fact it acts on carries the command and its answer, or the quoted line. *Purpose:* the
  executor re-runs the check instead of trusting a reading that may have gone stale;
- a change to a type, signature or test double lists every referencing file, with the
  {REFERENCE_SEARCH_TERM} and its answer. *Purpose:* no referencing file is found broken after the package
  reports done;
- a package that changes a stated behaviour names the tests and fixtures pinning it, and updating
  them is in scope; a test failing on behaviour the package does not state it changes is reported as
  a finding, never edited to pass. *Purpose:* an expectation moves only with its requirement, so an
  invariant test still stops wrong work;
- its done-line names, from the project's runner targets, those that check what the package changes
  (a package that changes only documents names only document checks, such as a link check), run
  once, at the package's end; the package is done when that run passes, or fails only where the plan
  names the breakage the package leaves and the later package or `ROADMAP.md` item that resolves it.
  *Purpose:* done is a run anyone can repeat, not a judgment, and no package hands on a breakage the
  plan does not account for;
- a before/after measurement done-line carries a passing run on the base commit, taken during
  planning. *Purpose:* a failed comparison is known to come from the change, not from a baseline that
  never passed;
- it has had `{clauses.ref(name="prompt-engineer")}` usability review, then `{clauses.ref(name="architect")}` revision. *Purpose:* the agent that
  executes it can act on it before it costs a dispatch.

A plan whose packages fail this is neither offered for approval nor dispatched. *Purpose:* what is
approved can run as approved.

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
- A brief removing a concern the user ruled out says to delete every site that handles it and
  offers no category of site to keep; a site survives only where the agent shows it is not about
  that concern. A brief never poses as a problem to design what a standard answer settles.
  *Purpose:* a removal stays a removal, not a design problem the agent is invited to solve.
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
  the {CHECKPOINT_GATE_TERM}'s cost is paid once.
- A checkpoint is incomplete until every document describing the changed behaviour is updated, the
  contract documents included. *Purpose:* what a checkpoint ships matches its documentation.

## Post-plan review

- Every plan holding a shipped package ends with two packages: the post-plan review, then the
  post-plan burndown. *Purpose:* review and its fixes are planned work, not a step dropped when the
  plan lands.
- The {POST_PLAN_REVIEWERS_TERM} are given the project documents and not the plan, and review the
  changes and their tests against the project's standards and fitness for purpose. *Purpose:* they
  judge what shipped, not how well it matches the plan's account of itself.
- The post-plan review writes the reviewers' findings to the {REVIEW_DOCUMENT_TERM}, which is never
  diced. The review's row is `landed` in the commit that adds the {REVIEW_DOCUMENT_TERM}.
  *Purpose:* the burndown is drafted from one record of what was found.
- Until the review lands, the burndown's section holds only: "Drafted from `ACTIVE_PLAN_REVIEW.md`
  once the post-plan review lands." Then you draft the burndown's work list from the
  {REVIEW_DOCUMENT_TERM}; it replaces that text where the section is, in the plan or in its leaf,
  and the burndown's row keeps no state word.
- The burndown gets `{clauses.ref(name="prompt-engineer")}` usability review, then your revision, before it is
  `dispatchable`. *Purpose:* the agents that execute from it can act on each item without inventing
  what it leaves open.
- The {REVIEW_DOCUMENT_TERM} is deleted in the commit that lands the plan, not before. *Purpose:*
  the burndown cites it until it lands, and a review left in place after reads as findings still
  open.
- The review of a release's hardening plan (`references/release.md`), and any review the user asks
  to include one, includes a user-flow audit, in the {REVIEW_DOCUMENT_TERM}: of the project's user-facing commands and flows, for
  elements that are redundant, over-composed, split finer than any use needs, ordered against how
  they are used, unnecessary or poorly named. It executes nothing and feeds the next design.
  *Purpose:* friction that no single change caused is found before it accumulates across releases.

## Periodic review

- Once the {PERIODIC_REVIEW_INTERVAL_TERM}'s count of plans has landed since the last periodic
  review, the next plan is a periodic review, before any other plan is made active. It looks past
  single changes, at what has accumulated across them. *Purpose:* drift that no single change
  caused accumulates whether or not anyone looks, and is found on a count the process keeps, not
  when someone remembers.
- The count is read from the history: a plan's landing commit says it lands a plan, and a periodic
  review's landing commit says it lands a periodic review. *Purpose:* the count needs no file of its
  own to keep current.
- Its members, each skipped when its subject has had no substantive change since it last ran: the
  full review of the project documents (`references/project-documents.md`, *Full review*). Each
  member judges only what changed since it last ran, and reopens nothing settled. *Purpose:* the
  review converges instead of re-litigating the whole project every round.
- Its members' findings are its post-plan review, written to the {REVIEW_DOCUMENT_TERM}, and are
  fixed in its post-plan burndown, outside any release's hardening. *Purpose:* cleanup has a home that is not a release.

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
3. **What it is built from.** Propose a breakdown of the project into pieces — the standard ones,
   the few new ones, and the new effect where there is one — and have the user correct it.
   *Purpose:* the project documents start from what the project is most like.
4. **The project documents**, drafted from 1–3 as `references/project-documents.md` describes:
   THESIS.md by you with the user, from 3's breakdown; SPEC.md and ARCHITECTURE.md by
   `{clauses.ref(name="tech-writer")}` with the user; CONVENTIONS.md by you, from the choices made in 2. Where the
   project has code, `{clauses.ref(name="architect")}` produces its initial design, held to SPEC.md;
   ARCHITECTURE.md is drafted from that design's invariants and skeleton. A behavioural acceptance
   criterion in the design (an outcome, not a mechanism) that SPEC.md does not already state is a
   SPEC.md gap raised with the user, not ARCHITECTURE.md content. `{clauses.ref(name="prompt-engineer")}` reviews
   each of the four drafts before the user accepts it, and authors and reviews their changes from
   then on; the user remains their owner. A project
   with no code may omit ARCHITECTURE.md, at the owner's choice. *Purpose:* each document is drafted
   by the agent whose discipline it needs.

   Dicing them is the `{clauses.optional_ref(name="docdicer")}` skill's.

5. **A runner**, if one is needed: `just` by default; `make` only where the project has targets that
   must rebuild only when their inputs are newer than their outputs. A project on an ecosystem's
   native task surface (npm scripts, cargo) still gets a justfile whose recipes call into it.
   Record the choice in CONVENTIONS.md, then settle the runner targets the {CHECKPOINT_GATE_TERM}
   will name. *Purpose:* the {CHECKPOINT_GATE_TERM} takes the form every done-line takes: runner
   targets.
6. Go to `references/project-setup.md` to bind the terms.

A project with no code has runner targets too: its done-lines and its {CHECKPOINT_GATE_TERM} may
name a link check or a document build.""",
            ),
            SkillFile(
                path="references/project-documents.md",
                body=f"""How the project documents are written and kept right. They rank THESIS.md, SPEC.md, ARCHITECTURE.md,
CONVENTIONS.md: the documents *above* one are those before it in that order, and each is written and
checked against them.

## Vocabulary first

One term for each meaning and one meaning for each term, across every document. Use the standard
word wherever one exists. Define only a coinage, or a common word used in a sense a reader would not
assume; a term of art used as its field uses it gets no definition, and a standard word used in its
standard senses, pinned by its context, is not a collision. No all-caps terms: a model reads one as
a placeholder. No location term whose place changes by case: name the directory each case uses.
Terms are settled in THESIS.md first and carry downward: a THESIS.md piece is named with the term
its field uses for that kind of piece, never with the lower documents' current words, and a lower
document may coin a narrower term tied to it. Before the first set is drafted, and before a full
review or a recovery revises a set, write the inventory — each concept, its one term, its meaning in
a sentence, every variant in use and where — in the plan doing the work, and have the user accept
it before any other text changes. A routine edit uses the settled terms; one that needs a new term,
or a new meaning for one, puts it to the user as one line with the proposed term. *Purpose:* a
requirement means one thing only when its words do.

## What each document holds

- **THESIS.md**: what the project is, what each piece is most like, and where each piece stops. A
  passage stays only if it changes what an agent building the project decides; motivation written
  for a person goes in the README.
- **SPEC.md**: outcomes the project's consumer observes, which any compliant implementation meets.
  It defines every term it uses and never sends its reader to another document for a requirement.
  It presents the one way every consumer runs the system; maintainer conveniences are
  ARCHITECTURE.md's or CONVENTIONS.md's.
- **ARCHITECTURE.md**: how this implementation meets each SPEC.md outcome.
- **CONVENTIONS.md**: the project's own process and house rules. A rule that would hold in every
  project using this skill is not the project's: report it as a change to the installed agent set,
  requested where its `!GENERATED!` banner says.

Code symbols, internal layout, tools and checks are mechanism, never THESIS.md's or SPEC.md's. Each
document opens by listing what it does not hold, in these words, the same across the set: no
consumer-facing behaviours or outcomes (SPEC.md's), no mechanisms or code structure
(ARCHITECTURE.md's), no project-specific process (CONVENTIONS.md's) — naming each that is not its
own. *Purpose:* content drifting into the wrong document shows against its list.

A document kept as a tree (the `{clauses.optional_ref(name="docdicer")}` skill) carries that list in its entry point.

## THESIS.md: what each piece is most like

THESIS.md opens with a paragraph saying in plain terms what the project does, and, where its scale
is small, saying so once. Then a table, `piece | most like | it is not`, with a row for every kind of
thing THESIS.md names, or a line saying that kind has none yet:

- **most like** names the standard pattern. A small, scoped version of a larger system carries the
  scoping word here. A new piece is described by the standard pattern it departs from, and how.
- **it is not** names the larger system the piece resembles and must not become, by what makes that
  system larger — external consumers, further media — never by the row's own pattern. It never rules
  out something the system does, and never names something the system already uses.
- For example: `| Storage | A local, internal tiered storage and retrieval scheme | A backup system
  or external tiered storage |`.
- A row is plain, not thin: it names every job the piece does and states no behaviour of any of
  them. How a piece treats its inputs (verbatim, merged, replaced whole) is SPEC.md's; what it is
  built from is ARCHITECTURE.md's. Where a check is cut from THESIS.md as mechanism, the property it
  secured stays, stated as a property.

Then two rules: a piece's conventional answer is its default; growing a piece toward its "is not" is
out of scope. Then the new pieces and the new effect, as a closed list: these, and only these. A new
effect is a result the pieces produce together that no piece produces alone, stated as an outcome; a
project with none states none. Novelty language appears only in that list. *Purpose:* an agent
building a piece described as what it is most like draws on everything known about that kind of
piece and makes the expected choices; a piece framed as unprecedented leaves it nothing to
interpolate from, so it invents.

## What the documents leave out

- A topic named only to dismiss it is purged, not disclaimed: the disclaimer teaches the reader the
  topic matters, and a reader working from the standard pattern never raises it unless the text
  does. A concern the user rules out appears in no document and is handled by no code — not even
  code that implements the ruling; errors the platform raises are handled like any other error.
- A check earns its place by enforcing something the contract documents state; a check for a
  condition they do not name is a rule nobody asked for, and goes.
- A guard that standard tools in the same role lack is a departure: it tells every reader the
  project is different, and they reach for unusual designs elsewhere. It goes unless ARCHITECTURE.md
  states a reason for it that holds.
- Where a comparison with standard tools decides whether one check stays, apply the same comparison
  to every check of that concern.

*Purpose:* the documents and the code teach their readers only what the project does.

## Cold reads

After a document is drafted, or revised under *Full review* or *Recovering a drifted set*, give it,
with only the documents above it, to `{clauses.ref(name="architect")}` and to the project's coder agent
(`{clauses.ref(name="tech-writer")}` for a project with no code).

{clauses.COLD_READ_RULE}
- Ask orientation questions only: for THESIS.md, what each piece is most like and what it must not
  grow into; for a lower document, what it promises or how it meets that, where it pushes a piece
  past its "is not", what it contradicts, and what in it belongs in another document. Never ask what
  the reader would build or where it was left guessing: the answer is a specification, not a
  reading. Do not point the reader at the "is not" column: the test is whether the document holds
  it unaided.
- SPEC.md is read twice: with THESIS.md, and with no other document.
- A finding counts when it shows a reach past an "is not", a contradiction, content in the wrong
  document, or a term the document uses and does not define. A request for more detail is the next
  document's to answer, not a gap. The reader sets aside the project's context, not general
  knowledge: a finding no generally informed reader would raise is dropped.
- Fix the document read, then read again with fresh readers; stop when findings shrink to trivia,
  usually after two reads.

*Purpose:* the document is tested as its readers will meet it.

## Writing the first set

1. The vocabulary inventory (*Vocabulary first*).
2. Write THESIS.md with the user, from the project's breakdown into pieces; cold-read it.
3. Write SPEC.md against THESIS.md; cold-read it both ways.
4. Write ARCHITECTURE.md against both; cold-read it.
5. Write CONVENTIONS.md last, holding only the rules the work has turned up so far; it grows as the
   project does.

Each document is accepted before the next is started. *Purpose:* each document is written against
settled ones, so a fault is found in the document that holds it, not two documents later.

## Full review

Because each edit to a document is reviewed only as a diff, the documents drift from each other and
from the code unseen. The periodic review (SKILL.md, *Periodic review*) holds a full review of the
project documents, skipped when no substantive document change has landed since the last one. It
reads each changed document whole against the documents above it and against the code, and judges
only what changed since the last full review: a settled passage is not reopened.

Where the documents are diced (the `{clauses.optional_ref(name="docdicer")}` skill), the full review reads each one undiced.

Its faults, in the order they are settled, each fix resting on the ones before it:

1. vocabulary;
2. novelty language outside the closed list;
3. contradictions, each checked against the code before the user decides;
4. terms left undefined, and requirements sent to another document;
5. mechanism in the wrong document;
6. a piece pushed past its "is not", where the user decides whether the document or THESIS.md moves.

*Purpose:* drift no diff shows is found on a trigger the process holds, not one someone must
remember, and each review converges because it judges only text no full review has seen.

## Recovering a drifted set

A set whose faults are too many to correct one by one is revised whole, as its own plan:

- The vocabulary inventory (*Vocabulary first*).
- Undice the documents, where diced, into a tracked working directory the plan names. Revise each as
  one document, top down, against the accepted ones above it, cold-read before the next; then dice
  them back over the originals.
- Within a document, settle one kind of fault at a time, in the order *Full review* lists. A cold
  read lists every kind; each finding waits for its turn.
- Have the user decide principles once, and single findings only where a fact or a call between
  THESIS.md and the document needs it — one line per question, with the proposed answer.
- Another plan that edits the same documents waits until they are diced back. Text that plan will
  delete is cut where this revision meets it, never reworded.

*Purpose:* a whole document is revised more reliably than its leaves.""",
            ),
            SkillFile(
                path="references/project-setup.md",
                body=f"""Bind the terms this skill's rules need and the project has not bound. Ask the owner about each,
and record each answer as a binding (SKILL.md, *Terms*). Where the project has no CONVENTIONS.md,
propose creating one to hold them. Reached because a rule needs one term, ask for that term alone.

- **Each term marked — in the *Bindable terms* table in SKILL.md's *Terms*, other than the two
  below.** Ask for its value; for a gate, the runner targets by name. Record every answer.
- **The {STEP_DOWN_MODEL_TERM}.** Offer the default named in the sentence after the *Bindable terms*
  table, where one is there; where none is, it is a term with no default. Record the answer only
  where it departs from the default.
- **The {STEP_DOWN_APPLICATION_TERM}.** Only where this session's dispatch tool cannot set a model:
  ask how a mechanical dispatch gets the {STEP_DOWN_MODEL_TERM}. Record the answer.

A term with no default that the owner leaves unanswered is written into CONVENTIONS.md as a note
`TODO: <term>:`, so the lookup in SKILL.md's *Terms* finds it, and setup moves on to the next.
*Purpose:* setup reaches its end, and the gap sits where the term's binding will go.""",
            ),
            SkillFile(
                path="references/adopting.md",
                body=f"""Bring a project whose process is already written somewhere under this skill. Nothing moves
without the user's go.

1. **Find every place the project states process**, wherever it lives: a CONVENTIONS tree or single
   file, CONTRIBUTING, README, AGENTS.md, a harness agents file, a linked wiki. Text between the
   `vvv-adjagent` and `^^^-adjagent` marker lines, or in a file under a `!GENERATED!` or
   `!INSTALLED!` banner, belongs to the installed agent set, not the project: skip it. When this
   step finds no process statement in any place it searched, there is nothing to classify: go to
   `references/project-setup.md`.
2. **Classify each statement** against this skill's rules:
   - **duplicate** of a rule here → propose removing the local copy;
   - **value** for a bindable term here → propose recording it as a binding (SKILL.md, *Terms*);
   - **refinement**, a stricter or narrower version of a rule here → propose stating it in
     CONVENTIONS.md as a local rule;
   - **contradiction** of a rule here, or of what a fixed term is fixed as → propose stating it in
     CONVENTIONS.md as a local rule, which overrules this skill's; where it relocates the
     {ACTIVE_PLAN_TERM}, {ACTIVE_DESIGN_TERM} or {PARKED_PLANS_TERM}, say that a tool reading plans
     will not find them there;
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
                body=f"""A release is a sequence of plans under one owner, each one job — the work one engineer would
contribute — taken through the {ACTIVE_DESIGN_TERM} and the {ACTIVE_PLAN_TERM} like any other work. Its membership
is the plans that carry its `Release:` line and land before the owner activates the hardening plan.
Free development activates plans for the release one at a time, each an ordinary plan with its own
post-plan review and post-plan burndown; the hardening plan, whose H1 heading opens with `Release hardening`, hardens the
release and delivers it. A plan names the release when it is activated for it: the first non-blank
line after the plan's H1 heading is `Release: <version>`, exactly that form. Work in the
{PARKED_PLANS_TERM}, plan or design, names no release. *Purpose:* the plan under way shows the
release it serves, and no release is promised for work not yet taken up.

## Scope

- Planning a release's jobs ahead is optional and the owner's choice; a release may also be
  assembled plan by plan. Where the owner plans ahead, the list of intended jobs is the owner's to
  keep, for example in `ROADMAP.md`. *Purpose:* the release's shape is the owner's to set, and the
  skill keeps no list of it.
- Each feature considered and not chosen goes into `ROADMAP.md`, and design already done for it into
  the {PARKED_PLANS_TERM} with no release named. *Purpose:* scoping a feature out loses nothing, so
  nothing is kept in to save it.
- Every package in the release's plans is shipped (SKILL.md, *Plans*): exploratory work is re-rated
  when its plan is taken into the release. *Purpose:* the process a shipped package owes is paid
  before hardening, not during it.

## The line

- Free development ends when the owner activates the hardening plan; never activate it yourself,
  whatever has landed. *Purpose:* the scope closes when the owner decides it has.
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

- The release is tagged after the hardening plan's post-plan burndown lands, on a commit the
  {CHECKPOINT_GATE_TERM} passed on; any change after that run, a version bump included, runs it again.
  *Purpose:* what ships is what was reviewed and verified.""",
            ),
        ),
    ),
)
