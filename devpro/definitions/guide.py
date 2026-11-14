"""guide: the skill where a session starts or continues work with devpro — a route to the development
process, the board, the installed set and the project's own design, and the two references it
routes to: installing, which carries everything about the installed set, and using, which walks the
development process from the user's side and reads, from the project's files, where a returning
user's work stands.
"""

from devpro import clauses
from devpro.definition import Definition, SkillFile
from devpro.vocabulary import Kind

DEFINITIONS = (
    Definition(
        name="guide",
        kind=Kind.SKILL,
        description=(
            "Use when the user wants to start a design, learn how the development process runs or where "
            "their work stands, see the "
            "project's board, or install, update, inspect or change the agent, command and skill definitions "
            "the `devpro` installer put here — the installed devpro version, a user-level install and the "
            "agents file included — or when a file carrying the devpro project's generated banner seems to "
            "need a change; NOT for a change to the project's own code."
        ),
        body=f"""Never edit a file carrying the devpro project's generated banner, or anything in the plugin's
install directory, or the devpro Python package the project installed. The next install
overwrites the one and the next update the other, leaving no diff to show the edit was there.
Where one seems to need a change, `references/installing.md`, *Customizing the set*, says where the
change goes.

## Route

| the starting place | served by | read |
| --- | --- | --- |
| starting a design | the `{clauses.ref(name="development")}` skill's *Design* | — |
| how the development process runs, or where the user's work stands | this skill | `references/using.md` |
| showing the project's board | the `{clauses.ref(name="docdicer")}` skill's `kanban` | — |
| installing, updating, inspecting or changing the installed set | this skill | `references/installing.md` |
| the project's own design: what it does, how it is built, its house rules | the project's contract documents | its SPEC.md, ARCHITECTURE.md and CONVENTIONS.md, or their trees |

Read a reference only when its row is reached.""",
        files=(
            SkillFile(
                path="references/installing.md",
                body=f"""How the `devpro` installer puts the {clauses.PLUGIN_NAME} plugin into a project or a user's
harness setup — under claude (Claude Code), opencode or mage — and how the installed set is updated,
inspected and changed. `devpro install --help` and `devpro install-agents-file --help` give each
flag's grammar. Below, `<repository>` is the devpro repository, {clauses.REPOSITORY_URL}, and
`v<version>` a release tag.

## Running devpro

Install devpro with Homebrew, from the `benn-herrera/tap` tap: `brew install benn-herrera/tap/devpro`.
On a machine without Homebrew, install devpro by hand, from a release tag:

- with pipx: `pipx install "git+<repository>@v<version>"`, then `pipx ensurepath` and a new shell;
- into a venv: `python3 -m venv <dir>`, then `<dir>/bin/pip install "git+<repository>@v<version>"`.

A bare `pip install` outside a venv fails on most hosts: Homebrew's and most distributions' Python
refuse it as `externally-managed-environment`, and Apple's `/usr/bin/python3` puts the command in
`~/Library/Python/3.9/bin`, which is not on `PATH`. Every later `devpro` command runs as the `devpro`
of that install: `devpro` on `PATH` for Homebrew and pipx, `<dir>/bin/devpro` for a venv.

`devpro install TARGET --plugin={clauses.PLUGIN_NAME}` installs into the existing directory TARGET,
with `--harness=claude`, `opencode` or `mage` where TARGET does not settle the harness. A claude or
opencode project install runs from the project root: `devpro install . --plugin={clauses.PLUGIN_NAME}`.
Every later `devpro install` for this project, a preview or an update, takes the target and flags it
already installs with.

## Requirements

- `just` 1.33.0 or later, where the project's runner is a justfile: a claude or opencode project
  install writes include lines into it.
- `perl` on `PATH` with core `JSON::PP`, for the claude guardrail hook. Without them a claude install
  skips the hook and its registration, says why in one line, and installs everything else.

Installing or upgrading kbase itself, the program the `kbase` MCP server runs, is the
`{clauses.optional_ref(name="kbase")}` skill's: follow its `references/installing.md`.

## Mage

With devpro installed by any route *Running devpro* gives, the target under mage is Mage's skills
directory, made first where absent: `mkdir -p ~/Mage/Skills`, then
`devpro install ~/Mage/Skills --plugin={clauses.PLUGIN_NAME} --harness=mage`, which writes
`~/Mage/Skills/{clauses.PLUGIN_NAME}/`. After installing the kbase plugin, restart Mage, so it starts
the `kbase` MCP server; restart it again after installing or upgrading kbase.

## Updating

Upgrade the installed devpro the way it was installed: `brew upgrade devpro` for Homebrew; for a
venv, `<dir>/bin/pip install "git+<repository>@v<version>"` with the next release's version, into
the same venv; for pipx, `pipx install --force "git+<repository>@v<version>"` likewise. Then preview
with `devpro install … --dry-run` and rerun the same `devpro install`, each with the target and flags
it already installs with. This holds under every harness, mage included.

## Inspecting

`devpro --version` prints the version of the devpro that installs. `devpro install … --dry-run`, with
the project's target and flags, shows whether the installed set differs from what that version
writes: it lists the paths it would create, change and remove, or reports the harness directory up
to date, and writes nothing.

## Global setup

A user-level install renders the plugin into a harness's user directory:
`devpro install ~ --plugin={clauses.PLUGIN_NAME} --harness=claude` writes
`~/.claude/skills/<plugin>/`, and `--harness=opencode` writes `~/.config/opencode/plugins/<plugin>/`.
It installs the definitions and no tools: no guardrail, no docdicer or cold-read script, no include
line. `devpro install-agents-file --plugin={clauses.PLUGIN_NAME} <dir>` installs the agents file into
`<dir>`: a user harness directory (`~/.claude`, `~/.config/opencode`), whose harness it infers, or a
project root, given `--harness`. Both verbs take `--dry-run`.

## The agents file

The operator's working rules reach a session as one marked block in an agents file; where that file
is follows.

- A claude or opencode project install keeps the block in one place: the global agents file
  (`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`) where that already holds the block, and
  otherwise the project's `AGENTS.md`, created where absent. Only `install-agents-file` into the user
  harness directory puts the block in the global agents file first.
- Under claude, with the block in the project, the project's `CLAUDE.md` is the one-line
  `@AGENTS.md` redirect, created where absent.
- Under mage the block is in the plugin directory's `CLAUDE.md`, which the install writes.

An install replaces only the block between its marker lines and keeps every other byte of the file.
An edit inside the block is lost; a write that changes the file keeps one rolling `backup.<name>`
beside it.

## Customizing the set

Rules the project wants its agents to follow go in its CONVENTIONS.md, or in its agents file outside
the block's marker lines: the agents read both, and no install changes either. A lasting change to
the definitions themselves goes through a copy of the devpro repository, since devpro merges nothing
local into the set it generates: vendor the repository as a copy the user's organization hosts,
edit the definitions there and install from it, owning that copy from then on; or fork it and open a
pull request.

## Rendering for another model family or tier map

`--family` renders the set for another model family, `--model-tier-map` sets the model each tier is
tuned for, and `--model-pin-tier-alias-map` renders an alias in place of each tier's model.
`devpro install --help` gives their grammar. A changed family or map changes the rendered files, so
that install proceeds where the set was otherwise up to date.

## Cold reads

The `{clauses.ref(name="development")}` skill's cold-read script needs `DEVPRO_COLD_READ_DIR`, which
the operator sets: an existing directory outside the project, with no instruction file
(`CLAUDE.md`, `AGENTS.md` or another a harness loads) at or above it, the operator's own `~/.claude/`
excepted.

## Install refusals

An install that refuses writes nothing and names each path at fault.

- A file at a path the install writes carries no devpro generated banner, or, for a harness resource,
  no devpro installed marker — a file the project wrote, or one a devpro release before 0.17.0 wrote:
  move or remove it, then install again.
- A directory at a path the install writes a file to: move or remove it, then install again.
- A project `CLAUDE.md` holds anything but the one-line `@AGENTS.md` redirect: move its content into
  `AGENTS.md` and make `CLAUDE.md` the redirect.
- An agents file holds marker lines other than one begin line followed by one end line: leave one
  ordered pair around the block, or delete the stray lines.
- An agents file is a redirect to another redirect, or to a file outside the directory named: merge
  them into one file by hand.
- A write of the global agents file, run from a checkout of the devpro repository whose sources
  have uncommitted changes, or whose commit state cannot be read: commit the changes, or install
  from a released devpro.
- A plugin given as a positional: the first positional is the target, so a lone
  `devpro install kbase` is refused where no directory `kbase` exists, and a second positional is
  refused. Name the plugin as `--plugin=NAME`.
- A plugin naming a definition that does not exist refuses every render: a defect in that devpro
  release, to report on `<repository>`'s issues.

## Agents missing or doubled

{clauses.RELOAD_RULE}

Under Claude Code, agents still missing after a restart or a plugin reload mean the plugin did not
load. By cause:

- The session started away from the project root, or before Claude Code's trust dialog was
  accepted: restart it at the project root and accept the dialog.
- Managed settings stop plugins loading from a skills directory: the administrator can allow it;
  no install changes it.
- The kbase plugin's `kbase` MCP server is unapproved: approve it when Claude Code asks.
- Any other load error: `/plugin`'s Errors tab names it.

Under claude, a user-level plugin shadows a project's plugin of the same name: the user-level one
loads, and the project's tuning, version and `kbase` server do not. A project install reports it as
shadowed by `~/.claude/skills/<plugin>`. Remove the user-level plugin, or work from it alone.

{clauses.SIDE_BY_SIDE_RULE}""",
            ),
            SkillFile(
                path="references/using.md",
                body=f"""The development process from the user's side: at each step, what the user decides, what they
tell the session, what appears in the project, and what comes next. Explain the process to the user
from this page. It states the session's rules only as the user meets them, and each step names where
its rule lives: an italic section name is a section of the `{clauses.ref(name="development")}`
skill's SKILL.md, a `references/` page in parentheses is one of that skill's pages, and *the agents
file* is the block of working rules devpro installs (`references/installing.md` here, *The agents
file*, says which file holds it). The quoted words below are examples: any plain words that name
the act serve.

## The user's go

The agents file, *Acting on the user's words*, *Responding to the user* and *Task management*.

- The session changes no file, dispatches no agent and makes no commit until the user's current
  message holds words that authorize that act: a quotable go. Each reply that acts quotes those
  words and names the act.
- Words authorize the act they name. "Start a design for a CSV export" starts a design; "yes"
  approves what the session's question proposed and nothing beside it. A preference, agreement
  with the session's analysis, or an "if we…" is not a go; where none is given, the session sets
  out what is ready and waits.
- A message holding any question is read-only: the session answers it and changes nothing, even
  mid-plan. Ask a request as a statement, not "could you…?"; to ask and keep a run going in one
  message, add the go: "Why P3 before P2? Carry on either way."
- One go covers one act, and an act that spans many turns, such as running an approved plan, stays
  covered to its end: the session keeps quoting the words that started it.
- Replies run to about 200 words unless the user asks for detail. While agents work in the
  background, the session keeps answering the user.

## Getting started

Installing devpro, and agents missing after an install, are `references/installing.md` here. The
scratch directory, `{clauses.PROJECT_TEMP_DIR}/` at the project root, holds untracked working files (*Terms*):
the user creates it and adds a `{clauses.PROJECT_TEMP_DIR}/` line to the project's `.gitignore`. Where it is
missing, the session stops and says so (the agents file, *Scratch space*). Then, by what the
project already has:

- **Nothing yet.** Say "Start a new project with the development process"
  (`references/new-project.md`). The session asks what the project produces, whether it needs code,
  and the constraints that settle its language and platform; it proposes a breakdown of the project
  into pieces for the user to correct. Then the project documents, each accepted by the user before
  the next is started: THESIS.md written with the user, SPEC.md and ARCHITECTURE.md drafted by a
  technical-writer agent with the user, CONVENTIONS.md last. Then a runner file (a justfile by
  default) where the project needs one, and the terms below. Appearing: THESIS.md, SPEC.md,
  ARCHITECTURE.md, CONVENTIONS.md, and the runner file where there is one.
- **Process written somewhere** — CONTRIBUTING, README, AGENTS.md, a wiki. Say "Adopt the
  development process here" (`references/adopting.md`). The session lists each process statement
  it finds as a duplicate, a value, a refinement, a contradiction or the project's own, with a count
  per class, and proposes where each goes; nothing moves without the user's go. Where the project's
  rules contradict *Dispatch*, *Acceptance* or *Gates and checkpoints*, it says the process does not
  fit the project. Appearing: CONVENTIONS.md, with the project's local rules and the terms below.
- **Code but no process written.** Say "Set up the development process"
  (`references/project-setup.md`): the terms below.
- **Alongside any case above: no SPEC.md or ARCHITECTURE.md.** Say "Write the project documents"
  (`references/project-documents.md`, *Writing the first set*). The session first lists each
  concept and the one term for it, for the user to accept; then each document, cold-read and
  accepted before the next.

The terms (*Terms*): the session asks for one when a rule first needs it and the project has not
set it, and records the answer as a line in CONVENTIONS.md. The one every project meets is the
checkpoint gate, the runner targets run before each commit of finished work: answer "just test",
and CONVENTIONS.md gets `checkpoint gate: just test`. An unanswered one is written as
`TODO: checkpoint gate:`, and the session asks again when it next needs it.

The user may also set the step-down model (default `{clauses.STEP_DOWN_MODEL}`).

The plan size limit (default {clauses.PLAN_SIZE_LIMIT_DEFAULT}) and the periodic review interval
(default {clauses.PERIODIC_REVIEW_INTERVAL_DEFAULT}) are set the same way.

## A request becomes a design

*Design*; `references/design.md`.

- **The user** states the change and asks for a design: "I want users to export the orders list as
  CSV. Start a design."
- **Appearing:** `ACTIVE_DESIGN.md` at the root. While in progress it holds a `## Drafts` section:
  the requirements, decisions, constraints and open questions, one `###` ticket each. The session
  asks the user the open questions; each answer is the user's decision.
- **When no question is open** the session puts it in final form, checks it with `check-design`,
  has it reviewed once, and offers it. The final form: a title; a few sentences of intent; a fixed
  line saying that summary is lossy and the entries are authoritative; then `## SPEC delta`,
  `## ARCHITECTURE delta` and `## Code delta`, those it needs, in that order. Each entry names the
  document leaf or section it changes and holds the exact passage and its replacement, the whole
  of a new text, or a removal; a Code delta entry states, for a fix, what the code does against
  what the document says, or, for a refactor, what changes in the code and that the document stays
  true.
- **The user decides:** accept it, or say what to change. Accepting is the user's word that these
  entries are the change the work makes to SPEC.md, ARCHITECTURE.md and the code: they reach the
  documents as written. Say "I accept the design. Write the plan." A change to CONVENTIONS.md or
  THESIS.md is not in a design; the plan carries it.
- **Next:** the plan. The design stays at the root until the plan lands.

## The plan

*Plans*, *Plan status*, *Dispatchability*.

- **Appearing:** `ACTIVE_PLAN.md`: a title; `Release: <version>` on the next line where the plan
  serves a release; a `## Status` table, one row per package, with `Package`, `State` and `Rating`
  columns; then each package under a heading opening with its ID (`P1`). Each package states its
  scope in files and its done-line: the runner targets whose passing run shows it done. A plan with
  shipped work ends in two more packages, *Post-plan review* and *Post-plan burndown*. A plan longer
  than the plan size limit is split into an `ACTIVE_PLAN/` directory read from its
  `entry-point.md`.
- **Lifetime**, stated per package: **shipped**, the whole process (the default); **exploratory**,
  its done-line and the checkpoint gate, no post-plan review; **throwaway**, in the scratch directory
  only and never committed.
- **Before it is offered**, every package has been reviewed for usability and revised, the plan
  passes `check-plan`, and anything that needs the user has been asked. Questions belong here.
- **The user decides:** approve it, or say what to change. Say "The plan is approved. Run it." An
  approved plan runs to completion: the session does not come back with a question planning could
  have asked.

## Running the plan

*Dispatch*, *Acceptance*, *Gates and checkpoints*, *Commits and pull requests*.

- **What the user sees:** before each dispatch the session states the agent count and model; a
  package rated `mechanical` runs on the step-down model, an `expert` one on the agent's own. The
  agent's report is checked against the diff, the checkpoint gate runs, and the session commits the
  package with its Status row set to `landed`. A State cell reads `dispatchable`, then
  `in progress`, then `landed`; a row with no state word is still drafted. Each commit message and
  pull-request description carries a paragraph opening `ai assisted by [devpro]`, and no co-author
  trailer.
- **When the session asks the user anything**, it is one of:
  - a go for more than one agent at once on the most capable model the installed agents name. It
    names the count; answer with the count: "Go, 3 agents."
  - an escalation: a choice where two readings lead to materially different work and nothing written
    settles it. It states what it checked — the contract documents, the plan and design, the agents'
    definitions, the commit history. Answer with the decision.
  - a term the work needs that the project has not set (*Getting started*).
- **A decision that changes the requirements**, an escalation's answer or the user's own, is entered
  in `ACTIVE_DESIGN.md` as an entry recording it and checked again, and may add a package to the
  plan; only the changed text is reviewed. Say it with its go: "Exports include refunds too. Update
  the design and the plan."
- **Setting the work aside** (*Plans*): "Set this work aside as orders-export." Every `ACTIVE_*` file
  moves into `ROADMAP_DESIGNS/` as `<topic>_DESIGN.md`, `<topic>_PLAN.md` and so on, and the plan
  drops its `Release:` line; the root is free for other work, and landed packages stay committed. It
  returns under its `ACTIVE_` names once no `ACTIVE_*` file is at the root: "Bring back
  orders-export." Dropped for good, it is abandoned and leaves `ROADMAP_DESIGNS/`.

## The post-plan review, the burndown and landing

*Post-plan review*, *Plans*.

- **Part of the approved plan.** After the last work package the session runs the review and the
  burndown under the same approval; no new go is needed. A plan with no shipped package has neither.
- **The review:** one reviewer agent per domain the plan changed: the coder for each changed
  language, an architect where structure changed, a technical writer where READMEs or guides
  changed, a prompt engineer where model-facing text or the project documents changed. They are
  given the project documents and the design, not the plan. Appearing: `ACTIVE_PLAN_REVIEW.md`,
  their findings, committed with the review's row `landed`.
- **The burndown:** the session drafts the fix list from `ACTIVE_PLAN_REVIEW.md` into the burndown
  package, has it reviewed, and runs it like any package. Every finding that cites a written rule is
  fixed, whatever its severity; one that needs a choice nothing written settles comes to the user.
- **The user** may read `ACTIVE_PLAN_REVIEW.md` and answers what comes to them; nothing else.
- **Landing:** one commit deletes `ACTIVE_PLAN.md` (or replaces it with the next plan),
  `ACTIVE_DESIGN.md` and `ACTIVE_PLAN_REVIEW.md`; its message says it lands a plan. **Next:** a new
  request or a roadmap ticket, or the periodic review where it is due.

## Lighter process

*Skipping a step*.

- **Only the user drops a step.** "Skip the design; go straight to a plan." "Make this plan
  exploratory." "Throwaway: don't commit it." "Just make the fix, no plan."
- **The session may propose one**: going straight to the plan where the design is small and already
  settled in the conversation, or a lighter lifetime where the code's warrants it. The proposal names
  each step dropped and what is lost; it takes effect only when the user adopts it: "Yes, straight
  to the plan."
- **A skip the user directs unprompted** gets one piece of advice, at the decision, naming what is
  lost. The user's answer stands for that work.
- **Where it shows:** a plan's lifetime, or a line where a dropped section would be. Straight to a
  plan leaves `ACTIVE_PLAN.md` with no `ACTIVE_DESIGN.md`.
- **No plan** leaves no `ACTIVE_*` file: the session makes the change the user's words name. A go
  covers only the act it names (the agents file, *Acting on the user's words*), so "Just make the
  fix, no plan." is no go for a commit; the session commits the change on words that name the
  commit: "Commit it."
- A one-line fix still gets the whole process unless the user drops steps; short of no plan, the
  lightest path is straight to an exploratory plan.

## The roadmap

*Roadmap tickets*, *Plans*.

- `ROADMAP.md` is work intended and not yet taken up: `##` categories holding `###` tickets. "Add a
  roadmap ticket under Exports: PDF export." The session checks it with `check-roadmap` after each
  edit.
- `ROADMAP_DESIGNS/` holds work set aside, as `<topic>_DESIGN.md`, `<topic>_PLAN.md` and so on, and
  names no release.
- Work leaves the roadmap when it becomes the active design or plan, when other work accomplishes it,
  or when it is abandoned, superseded work included. "Start a design from the PDF export ticket."

## A release

`references/release.md`.

- **What it is:** a sequence of ordinary plans under one owner, the user, then a hardening plan that
  delivers it.
- **The user decides** the version; what goes in, listed ahead in `ROADMAP.md` or not; each plan
  that joins, which carries `Release: <version>` on the line after its title ("This plan is for
  release 1.2."); and when free development ends, by activating the hardening plan, whose title
  opens `Release hardening` ("Start release hardening for 1.2."). The session never activates it.
- **In a release plan** every package is shipped. A feature left out goes into `ROADMAP.md`, its
  design work into `ROADMAP_DESIGNS/`.
- **Once hardening starts**, new work goes to `ROADMAP.md` only. Each fix changes only its defect,
  and its report and commit message say what else it can affect; the user judges from those whether
  hardening is converging. A livable issue needing more is deferred to `ROADMAP.md` and named in the
  hardening plan's status. Its post-plan review adds an audit of the project's user-facing commands
  and flows, which feeds the next design.
- **Tagging:** after the hardening plan's burndown lands, on a commit the checkpoint gate passed on;
  any change after that, a version bump included, runs the gate again. Name the act to have the
  session make it.

## The periodic review

*Periodic review*; `references/project-documents.md`, *Full review*. Where the post-plan review
above follows one plan, this one looks at what many plans have left behind.

- **Due** once the periodic review interval's count of plans (this page's *Getting started*) has
  landed since the last periodic review, counted from the landing commits' messages. A review the
  user directs over accumulated work is this same review.
- **What it holds up:** when due, the next plan made active is the periodic review, before any
  other. A request can still be designed; its plan waits.
- **What it holds:** the full review of the project documents, skipped where none changed
  substantively: each changed document read whole against the documents above it and the code. By
  default eight seats staff it, two of each of four kinds: an architect, a prompt engineer, a
  technical writer and the project's coder. Each seat judges only what changed since the review
  last ran and reopens nothing settled; the skill's *Periodic review* gives each pair's question
  and its two documents. The seat kinds are fixed, where the post-plan review's reviewers follow
  the domains its plan changed. The user accepts the term list first where the review revises the
  set, and decides each contradiction and each piece pushed past its THESIS.md "it is not".
- **Then** its findings go in `ACTIVE_PLAN_REVIEW.md`, one ID per defect however many seats
  reported it, and its burndown cites that ID and groups them by root cause rather than one item
  per finding. The session brings a plan and never a design — the review produces findings, not
  a contract change — so it goes straight to a plan (*Lighter process*), which the user approves
  as any other; its landing commit says it lands a periodic review.

## The board

The `{clauses.ref(name="docdicer")}` skill, *The script*.

- A live board of the project's roadmap, design and plan. `tools/docdicer kanban --help` gives the
  details.
- The user runs it; the session gives the command and does not run it: `just docdicer-kanban`, or
  `make docdicer-kanban`, where a project install wrote the runner include line; otherwise
  `tools/docdicer kanban` in that skill's directory. It serves until stopped.

## Where work stands

For a returning user, read the root and say what is next and what to say:

- **No `ACTIVE_*` file:** nothing under way. Next: a request, a `ROADMAP.md` ticket or work in
  `ROADMAP_DESIGNS/`, unless the periodic review is due (`git log`: plans landed since the last
  periodic review).
- **`ACTIVE_DESIGN.md` with `## Drafts`:** a design in progress; its open questions wait on the user.
- **`ACTIVE_DESIGN.md` in final form, no `ACTIVE_PLAN.md`:** offered for acceptance, or accepted
  and the plan not yet written.
- **`ACTIVE_PLAN.md`:** its Status table. Nothing past `dispatchable`, and no package commit in
  `git log`: awaiting approval, or approved and not started. A row `in progress`: the run is under
  way. Work packages `landed` and the review's row not: the review is next. `ACTIVE_PLAN_REVIEW.md`
  present: the burndown is next or under way. Every row `landed`: the landing commit is next.
- **`ACTIVE_PLAN.md` with no `ACTIVE_DESIGN.md`:** a plan that went straight to the plan.
- **A `Release:` line:** the plan serves that release; a title opening `Release hardening`: the
  release is hardening, and its tag follows the burndown.
- **An `ACTIVE_PLAN/` or `ACTIVE_DESIGN/` directory:** the same, split into files; read its
  `entry-point.md`.

## Worked example

A project with code, SPEC.md and ARCHITECTURE.md, and no written process, devpro just installed,
`{clauses.PROJECT_TEMP_DIR}/` created.

1. "Set up the development process." The session asks for the checkpoint gate. "just test."
   CONVENTIONS.md appears with `checkpoint gate: just test`.
2. "I want users to export the orders list as CSV. Start a design." `ACTIVE_DESIGN.md` appears with
   `## Drafts` tickets; the session asks which columns and which orders. "Order id, date and total;
   every order the user can see."
3. The session offers the final form: a `## SPEC delta` entry adding the export to SPEC.md's orders
   section, a `## ARCHITECTURE delta` entry describing the export code. "I accept the design. Write
   the plan."
4. `ACTIVE_PLAN.md` appears: P1 applies the two entries, P2 writes the export and its tests, P3 the
   post-plan review, P4 the post-plan burndown, all shipped. "The plan is approved. Run it."
5. The session names one agent and its model for P1, checks the result, runs `just test`, and
   commits P1 with its row `landed`; then P2. Mid-P2 it asks: "Dates in UTC or the user's time
   zone? SPEC.md and the design say neither." "UTC." The answer is entered in the design. "How far
   along are we?" gets an answer and nothing else; "Carry on." resumes.
6. P3: the coder for the app's language, an architect and a prompt engineer review, and
   `ACTIVE_PLAN_REVIEW.md` is committed. P4 fixes its findings and is committed.
7. The landing commit deletes `ACTIVE_PLAN.md`, `ACTIVE_DESIGN.md` and `ACTIVE_PLAN_REVIEW.md` and
   says it lands a plan. SPEC.md and ARCHITECTURE.md hold the accepted entries, the code has the
   export, and the root is ready for the next request.""",
            ),
        ),
    ),
)
