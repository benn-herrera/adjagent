"""kbase: the skill that carries the KB capability — a router, and the references it routes to.

The router is the only text a session pays for before it knows what was asked: it locates the KB,
says what a repository with no KB is, and routes to one reference by the request. A reference is read
only when its route is reached, and every route is a reference.
"""

from adjagent import clauses
from adjagent.definition import Definition, SkillFile
from adjagent.vocabulary import Kind

KBASE_MIN_VERSION = "0.10.0"
KBASE_TAP_FORMULA = "benn-herrera/kbase/kbase"

DEFINITIONS = (
    Definition(
        name="kbase",
        kind=Kind.SKILL,
        description=(
            "Use when the user asks what this repository records about a result, claim, derivation, citation or "
            "strength — whatever they call the store — or when they point at .tex sources here, a repository of "
            "papers, to index into one, or when they ask to score the KB's rigor and bearings, or when "
            "they hand over a correction, a finished result or a migration to land in the KB, or when they "
            "ask to install or upgrade kbase itself; NOT for "
            "questions about code, configuration, or documents, except a KB."
        ),
        body=f"""## Locate the KB

Before reading anything, establish where the KB is. The probes run from the directory you are standing
in, in this order:

1. `./kb-root/entry-point.md` **and** `./kb-root/.index/` both exist → the **KB root** is `./kb-root`
2. otherwise `./entry-point.md` **and** `./.index/` both exist → the **KB root** is `.`
3. otherwise there is no KB here — the outcomes below say what that means

Neither probe passing is a finding, not a failure. The `.index/` sibling is what the probes turn on: it
is what makes a directory a viable KB root rather than a section inside one. Each probe tests only that
`.index/` exists, never what it holds. Do not search the tree for a KB — section
directories carry their own `entry-point.md`, and a search finds the wrong one.

{clauses.KBASE_PROJECT_RULE}

In every path a reference names, `kb-root/` stands for the located **KB root**.

## One of three outcomes

**A KB is found.** Say in one line where it is, then route by the table below.

**No KB, and this repository holds LaTeX sources.** Not a dead end: it is a build waiting to happen.
Identify the volume root — `kbase://help/build` states the rule — put it to the user, and route to
`references/building.md` once they confirm it. That build has a fast path that spends no inference, and
the reference carries it.

**Neither a KB nor a source.** Say so and stop. There is nothing here to probe for, and further
looking only costs the user time.

## KB metadata goes through kbase

Under the KB root, the statement markers in the documents are metadata. A document's prose is yours
to read, and reading it passes over these: take no value from them, and never grep or count them. A
value metadata carries comes from a query, never off the file.

## kbase's own text governs

kbase's own text — its server instructions, each tool's description, usage guidelines and
constraints — is authoritative. Whatever it states — a limit, an order, a prohibition — is a rule,
not a suggestion, and where this skill disagrees with it, kbase's text governs. `kb-root/AGENTS.md`
likewise governs this skill where they disagree.

## Route by the request

Every route except `references/installing.md` needs the `kbase` MCP server's tools offered to you.
When a request matches a row below other than installing, and those tools are not offered, run
`command -v kbase` — a `PATH` lookup that runs nothing — and tell the user what it found:

- **Nothing:** kbase is not installed. On macOS or Linux it installs with Homebrew,
  `brew install {KBASE_TAP_FORMULA}`, version {KBASE_MIN_VERSION} or later. Open
  `references/installing.md` if they want the walkthrough.
- **A path:** kbase is installed, but its MCP server is not running here. The user enables it, or
  restarts or reconnects it, in their harness. If a restart does not bring the tools back, open
  `references/installing.md`: it covers that case.

Outside that check, mention installing kbase only when the user asks about it. Run `kbase` itself or
its `kb-` runner targets only when the user directs you to — what they named, and nothing more. A
`wait` line a kbase tool's result hands you is that tool's own continuation: run it as the reference
says. Turning the server on is the user's call, not a gap for you to work around.

| the request | the route |
| --- | --- |
| answering from the KB, navigating it, or reporting a recorded claim's strength | `references/reading.md` |
| building a KB over the LaTeX sources here | `references/building.md` |
| adding, correcting or migrating KB content | `references/maintaining.md` |
| scoring the KB's rigor and bearings | `references/scoring.md` |
| how the scoring system works | `references/scoring-system.md` |
| installing or upgrading kbase | `references/installing.md` |

Open only the reference the matched row names: the other route's text is not context for this
request.

## Session policy

The conversation continues across topics: there is no handoff to perform and no session file to write
between them. Write a reading log only when the user asks for one. Never change directory once you are
underway: a KB root the probes located from where you stand is relative to it, and a `cd` loses it.""",
        files=(
            SkillFile(
                path="references/reading.md",
                body=f"""{clauses.kb_orientation(role="you are the reading seat of a finished KB — you navigate it, reason about what it says, and write nothing")}

{clauses.kb_orientation_docs(when="at session start")}

## Starting a session the user opened to explore

1. Read `kb-root/entry-point.md` → the domain index is now in context
2. A question the user has already asked goes to **Navigating a question** now, with no greeting first
3. Otherwise show the volume list and announce: "Ready. What would you like to explore?"

## Navigating a question

When the user asks a question:

1. **Identify the domain**: from the entry-point index, which domain is most relevant?
2. **Announce the path**: "Navigating: [domain] → [subtopic] → ..." before reading any documents. The
   user can redirect before you go further.
3. **Read progressively**: domain index first, then subtopic index, then relevant leaves. Do not read
   the entire branch — read to the depth needed to answer the question. Every domain and subtopic index
   contains a Key Results section at the top listing conclusions and formulae verbatim from the source.
   Check this section before going deeper — if the question is answered by a Key Results entry, the leaf
   is not needed.
4. **Track what you read**: maintain a running list of every `kb-root/` path read for this question, so
   a reading log the user asks for is already assembled.
5. **Answer** with the accumulated context. Cite the specific leaf documents your answer draws from.

## Claim rigor and strength

Every result in this KB is a node whose record says how trustworthy it is. When you ground an answer
on a result — and especially when assisting a derivation or research effort — surface its strength;
do not cite a leaf as if all results were equally solid.

**Where it lives.** Each result's node carries a `clm-xxxxxx` id, and `show` on that id returns its
record; the queries below resolve a result to its id.

**Derivation, lifts and caps.** `strength = min(max(derivation, every lift), every cap)`, where
`derivation = min(rigor, every participating premise)`, and `0` where none participates:

- **Premise** — a `supports` edge contributes `bearing × source strength`, a `founds` edge
  `bearing × source rigor`. Bearings below 1 compound down a chain, so the weak point may be a low
  bearing rather than a weak node.
- **Lift** — an `ana-` or *run* `exp-` lifting the claim contributes `bearing × lifter strength`, above
  the derivation.
- **Cap** — a `clm-`, `ana-` or *run* `exp-` refuting it caps it at `1 − bearing × refuter strength`;
  the smallest cap wins.
- **Exclusion** — an edge whose bearing or source strength is pending is left out: no contribution,
  no lift, no cap.

The `strength` `show` reports already includes all three, and they are not interchangeable for
derivation work: a claim solid via its *derivation* can be built on deeper, while one solid **only** via
a lift (weak derivation, strong lift) supports a conclusion yet does NOT license building a new
derivation on it.

**Pending does not propagate.** A claim no scoring pass has reached has a pending rigor, and where a
premise participates its strength is pending too unless a lift stands over it. Strength is computed
over the premises that remain — possibly higher than it will read once a left-out one is judged, and
`0` where none remains. A `0` has several causes, which `show` (`rigor`, `premise_count`) and `trace`
with `direction: in` tell apart: no premise at all, every premise unjudged, a zero in the minimum — a
judged `0.0` rigor or bearing, or a premise at `0` — or a refutation's cap. `find` by strength passes
over pending claims but lists those unjudged zeros: after a build, before any bearing pass, that is
every claim. A run `exp-` can float a pending-derivation claim to solid; a pending `ana-` never
poisons an otherwise-sound claim.

**Say which term, and what is unjudged.** When surfacing strength for a derivation or research effort,
say *which term* carries the strength — derivation, lift or cap — and point at the lifting `exp-`/`ana-`
or refuting `clm-`/`exp-`/`ana-` nodes — the evidence, and the lever for strengthening. When a claim
reads pending, or reads a value a left-out premise has yet to move, say so plainly and name which: the
result may well be sound, but its strength is *unassessed*, and flagging that uncertainty is not the
same as implying solidity.

**Query it through the index — don't grep.** The queries are operations of the one tool
`{clauses.MCP_TOOL_PREFIX}query`: `kbase://help/query` says what they share, and
`kbase://help/<operation>` gives each one's arguments. Route the user's need to an operation:

- **A result named in words** ("Proposition 4.3", "the Lyapunov result") — `find` by `title` resolves
  it to its id. The user never has to know or guess an id: look it up for them, and offer it when it
  is useful to them, but lead with the name and the strength, not the bare id.
- **One node's record** — `show`.
- **One hop of edges** — `edges` with the node's `id`.
- **The chain bearing on a claim, or what its strength reaches** — `trace`, `direction` `in` or
  `out`.
- **Shaky, high-leverage and unscored claims** — `stats` for the snapshot, `find` for the full lists.
- **Who cites a node** — `citations-of`. Surface a citation on request; do not follow it.

**Assisting derivations.** When the user builds or checks a derivation, trace the strength of the
chain it rests on (`trace` on the claim with `direction: in`: the whole chain, each edge's
contribution) and surface the **weakest link** explicitly — a weak node or a low bearing — e.g. "this
passes through `clm-yl5n5v` at strength 0.30, *do not build on, rework needed* — that is the
load-bearing weak point."

A `wrk-` id among the claim's edges (`edges` with the claim's `id`) is a premise contributing
`bearing × rigor`, with no derived strength of its own, so it sits on no strength band, and the
weakest link in a chain may be a work this corpus does not contain. Name the work itself as the weak
point when it is one — a chain that runs out of the corpus is a different exposure from a weak step
inside it, and neither stands in for the other. Where either score is pending, the edge is left out
of the claim's derivation, and the unsupplied score is what to report: `show` on the work's id gives
its title and `rigor`, and `edges` with the claim's `id` gives the `founds` edge's bearing. To reach
the work, `find` it by the citing leaf's own citation key, its `label`, rather than by its name. An
`axm-` id is an axiom: a `founds` premise contributing `bearing × 1.0`, its rigor `1.0` by rule.

## Cross-references

When you encounter a `> Related:` suggestion in a document:

Surface it explicitly: "There's a cross-reference to [topic name] in [domain B]. Want me to pull it in?"

Do not follow cross-references automatically. The user decides whether the additional context is worth
the token cost.

## Constraints

These are rules, not a role: nothing here is about what you *are*, and all of it binds every answer.

- You do not modify KB content. If the user identifies an error in a KB document, note it — do not fix
  it; landing the correction is `references/maintaining.md`'s job. The KB is a read-only reference
  during a reading session.
- You do not generate new mathematical content. You navigate to and reason about existing content. If
  asked to derive something not in the KB, say so explicitly and distinguish your reasoning from KB
  content.
- You do not re-score a claim, edit a node's record, or supply a rigor value: `score` grades and
  lands values, `references/maintaining.md` writes them, and a number you invent is a defect in the
  record.
- You do not speculate about content in documents you haven't read. If you don't know whether a topic is
  covered, navigate to find out — don't guess.""",
            ),
            SkillFile(
                path="references/building.md",
                body="""Launch a KB build over the LaTeX volume roots the user names in the background, relay what the
launch returns, and follow it with `status` on request and `cancel` on the user's word.

## What the build takes

The volume roots the user names are the whole input, one `volume-root` per source;
`kbase://help/build` states how they resolve and in what order the build takes them. Anything else
the user typed is not an input — not a further source, and nothing this reference carries into the
launch; say so rather than folding it into the call.

## The fast path

The same `build` call with `no-inference` true is the fast path; `kbase://help/build` states what it
drops. Offer it for a first look at what a KB over these sources holds, or for a run the user wants
before spending inference on a long build. State the trade when you offer it: this is the structure,
not a complete KB, and the fast run is never upgraded later — the full build afterwards is a start
over (*Resuming and starting over*, below) and keeps nothing of it.

## Launch

Call the `build` tool with one `volume-root` per source. Tell the user before you call it that every
stage boundary of the build is a commit in their repository.

The result holds a `wait` line. Run it as a background shell command in the same turn, as printed
rather than composed from the flags, and relay the outcome when it returns.

A refusal starts nothing: relay its items and their remedies, and the launch ends there. A
`check: provider` item is a configuration gap: call the `show-config` tool and relay its document
rather than reading the file yourself to explain the refusal, so the user can fix the file the item's
`path` names in the layer `show-config` reports. Then offer to set the provider up through
`configure-providers`, then `configure-models`, following the steps each result's `next` gives.

## Choosing models

When the refusal leaves `models.decision` or `models.text` unset and the user names no id, the
choice is the user's. Read `kbase://model-hints` for what each role wants.

An id the user names fills its role; for a role they leave open, propose one id `models` listed that
matches the capability `kbase://model-hints` states for it, and say what would move the choice —
the user can judge the material and the wall clock, and the session cannot. Say once if `models`
did not list one, then write what they chose with `configure-models`, each id under its role's
argument.

## Following it

`status` on the user's request: relay its `state`, the stage under `current` and the `resume` command
where it carries one. `cancel` only on the user's word, and relay what it returns.

## Resuming and starting over

- **A resume** is `build` with `resume` true.
- **Starting over** is the command `build-trail` gives for `started-at`, or removing `kb-root/`, and
  either is the user's to run. Relay the command, and the paths under `dirty` where `build-trail`
  lists any. Once the user has run it, call `build` with the volume roots they name — a fresh
  build.""",
            ),
            SkillFile(
                path="references/scoring.md",
                body="""Launch a score run in the background, relay what the launch returns, and follow it with
`status` on request and `cancel` on the user's word. `kbase://help/score` states what a run asks,
skips, lands and resumes.

## The model

Before any pass starts, the model that answers it is the user's decision, made knowingly. They know
the plan and the endpoint; you do not.

- **What would answer.** `show-config` reports the resolved `scoring` role; read it there rather than
  naming an id from memory. Where it resolves to no model, that is the gap to report, not a role
  for you to fill.
- **What the run costs.** Call `score` with `dry-run` true first, scoped as the run would be: it asks
  nothing. Give the user the count it returns.
- **The trade, in their terms.** The judgement the KB's numbers get, against the wall clock of the
  run and what each call costs on their plan. `kbase://model-hints` states what the scoring role
  wants — a default, written without knowledge of whose plan pays for it.
- **Wait.** Start the run once they pick — `scoring-model` on that call where the pick is not the
  configured role — or once they say to run with what is configured. Never run first and report the
  bill.

## Launch

Call the `score` tool, and run the `wait` line its result holds as a background shell command in the
same turn, as printed rather than composed from the flags. When it returns, report the run's outcome
from the document it prints, and relay its `resume` line where items remain rather than running it.
A refusal starts nothing: relay what it names.

`status` on the user's request: relay its `state`, the run's `counts` and its `resume` line where it
carries one. `cancel` only on the user's word, and relay what it returns.

## Filling in `founds` bearings

Where a `founds` edge's bearing is pending, or the user asks for those values, offer to take them:
the work or axiom lies outside the corpus, and you have not read it.

`edges` on the claim lists its edges and their bearings, and `show` gives either end's title. Name
the edge by both ends, `<work or axiom> → <claim>`, with both titles, and take the number the user
gives — one edge at a time, or a list. Write each bearing with `edit-edge`, and a work's rigor the
user gives with `edit-work`.

An edge the user gives no value for stays as it stands, and your reply names which are still open.

## What the user sees

Report the run's `counts` and the ledger it wrote, as the run names them. Where items failed, say
so and leave them to the run's `resume` line.""",
            ),
            SkillFile(
                path="references/maintaining.md",
                body=f"""You maintain an existing knowledge base. You take finished work and incremental corrections and land
them in the canonical tree *correctly* — claim-graph wiring, cross-references, and the verify loop —
leaving `verify` green. The reading route reads, reasons and reports;
you modify.

{
                    clauses.kb_orientation(
                        role="you land changes in a KB the build pipeline has already finished with — that pipeline is not rerun for "
                        "your work"
                    )
                }

{
                    clauses.kb_orientation_docs(when="before editing")
                } This file tells you how to *apply* the toolchain's rules when
editing; it does not restate them.

**The request's targets only.** You create files at the targets the request names, and nowhere else.
Output with no named home is an escalation — never a location you choose, and never a file you name
yourself.

## What you modify, and how

**You write by hand**: leaf body prose, math and tables, up-links, and cross-references.

**A leaf you author is your own.** Migrating `session/` work means writing whole leaves, and those
are yours end to end.

**Metadata goes through the `write` tool.** `kbase://help/write` states the batch and its outcomes,
and `kbase://help/<operation>` states each op.

**Whether a batch commits `kb-root/` is the user's call.** Passing `commit` is strongly encouraged:
it makes the batch undoable as one unit.

{clauses.KB_RUNNER_TARGETS}

## The two jobs

### Job A — incremental edit / correction
A leaf, a node's record, a dependency edge, or a cross-reference needs to change. Read the **primary
source** first: the leaf's body and any cited source, directly; a node's or an edge's current
state from `show` and `edges`, never from a status field or a summary. Make the minimal correct
change, then run the verify loop below.

### Job B — migrate finished work from `session/` into the canonical tree
`session/` holds working docs (discussion notes, rescore worksheets, captured-but-unplaced results).
Migration is: decide what is canonical, place it as leaf content at the right taxonomy position,
wire its claim-graph nodes, and leave the source doc behind (or note it for removal).

**Editorial boundary (default — surface, don't decide unilaterally):**
- **PARK, do not promote:** inbox / rolling-capture / audit-changelog / session-log material parks
  to `session/`; it does **not** become a leaf at a canonical path. (If a session doc is
  process residue, it stays process residue.)
- **Promote:** a finished, leaf-shaped *result/derivation* with a clear taxonomy home.
- When the canonical-vs-park call, or where a promoted leaf belongs in the tree, is **ambiguous**,
  stop and surface it to the human with your recommendation. Never invent a placement, and never
  open a new subtopic to hold work you are landing.

## Anatomy of a correct leaf (reference, not restated)

A leaf you add by hand carries what a built one does:
- The up-link, on every document you write below the entry point: `[↑ Parent Name](<parent>)` on
  the first line — `↑` is U+2191, the machine-checkable marker; `<parent>` is the parent document,
  spelled relative to the document carrying the link: the `index.md` of its own directory, or for an
  `index.md` itself the one a directory above. Directly under `kb-root/` that parent is
  `entry-point.md`, so a domain index up-links to `../entry-point.md`; there is no
  `kb-root/index.md` to point at.
- A statement marker per node the document hosts, placed by that node's add op.
- Cross-references use the `> Related:` blockquote form — never paraphrase the target.
- A node named in prose is a citation; `kbase://help/add-citation` states its forms.

Incremental edits preserve the existing structure; do not reformat beyond the change. **Preserve
author-adjudication markers verbatim** (e.g. author adjudication notes, walk-back annotations) —
never strip them in an edit or migration.

## Claim-graph wiring

When a migration or edit adds/changes a node:
- **Which premises a derivation rests on is yours to decide**: the `clm-` and `exp-` nodes it
  actually consumes, each a `supports` edge into the claim, and the framework premises — the axioms
  the KB's own `axioms.md` declares — each a `founds` edge.
- **A `founds` edge from a work** belongs only where the warrant genuinely leaves the corpus, never
  as a placeholder for a `clm-` you did not find, and it never stands in for an in-corpus
  dependency. The scores it leaves pending are work it creates, not a cost to weigh against leaving
  a real warrant off the graph.
- **Volume order is a heuristic, not a rule.** Dependencies *usually* point to more foundational
  material (earlier or common volumes), and an edge in the unusual direction (e.g. an earlier-volume
  claim genuinely resting on a later volume's theorem) is a smell worth a second look — but it is
  **allowed** if it reflects a real dependency and creates no cycle. Never drop or axiom-downgrade a
  real `clm-`/`exp-` premise merely because the target is in a "later" volume. If a cross-direction
  edge feels wrong, surface it (the claim may be mis-placed) rather than silently omitting the
  dependency.
- **A claim that should not exist** — a duplicate of one already in the graph, or one a correction
  withdraws — comes out with `remove-node`. Each dependent edge it removes was a warrant: re-point
  each one that still holds onto the claim that replaces it, or the dependent is left resting on
  nothing. `kbase://help/remove-node` states how.
- **An `exp-` node's edges** — `supports`, `lifts` or `refutes` — respect the `exp-`
  design/originate/control gate (re-analyses of outside data are `ana-`/`clm-`, never `exp-`).

## The verify loop (always, before you call it done)

After you edit a document's body directly, call `verify`, and follow each refusal's remedy. Done
means `verify` returns `done`. If you cannot get there, stop and report the failing check verbatim.

## Hazards (learned failure modes — do not relearn them)

- **The worktree-base-bug:** a KB edit made in a worktree, or on a branch, whose base is not the
  branch being maintained is an edit to a KB you cannot see — the worktree branches off
  `main`/merge-base, NOT the current feature branch, so your edits land on the wrong base and the KB
  you read back is stale. For KB maintenance on a feature branch, work **in-tree** with strict
  discipline: no branch switch, no stage.
- **Mechanical sweeps need a coverage gate:** if the task is "do X to all N items," state N from a
  query — `find`, with `path` for a subtree, or `stats` — do all N, and count one `done` or
  `unchanged` entry outcome per item before declaring done. Byte-green on a partial pass is a false
  pass.
- **Separate complex operations:** do not interleave two distinct complex edits (e.g. a content
  migration *and* a dependency-graph refactor) in one pass — finish and verify-green one, then start
  the next.
- **Plan against primary sources:** verify the leaf/source content before editing; never edit off a
  summary document's Key Results or a status field.

## One live writer

A KB has at most one writer at a time. Metadata — every `write` batch, anything that touches a
record, a register or the index — comes from that one writer, live and serially: kbase's derivation
after each write cascades a metadata change mechanically through the whole KB, and the batches are
fast, so a second writer gains nothing and puts the whole KB at risk. The user's task decides which
role you hold: where it asks you to land changes, you are the writer; where another session is
already writing this KB, you are the other role below.
- **Examine and hand back.** Read, decide what needs changing, and hand the change set — each change
  as the op to call and the values it takes — to the user or to the writer, who applies the changes
  in one coordinated pass. Run no write batch.
- **Leaf prose.** Leaf text may be edited in parallel, by more than one session at a time, each on
  leaves no other is editing, provided none changes metadata: no register, no statement marker, no
  up-link.""",
            ),
            SkillFile(
                path="references/scoring-system.md",
                body="""The scoring system — rigor and bearing, and how strength is computed edge by edge — is
specified in kbase's SPEC; a strength is read against its
[band ladder](https://github.com/benn-herrera/kbase/blob/main/PROJECT_DOCS/SPEC/10-metadata-format-version/the-band-ladder.md).""",
            ),
            SkillFile(
                path="references/installing.md",
                body=f"""Walk the user through installing or upgrading kbase, the executable the `kbase` MCP server runs.
This skill needs kbase {KBASE_MIN_VERSION} or later.

Show each command below for the user to run. Run one yourself only when the user asks you to run
that command.

## Platform

kbase installs through Homebrew on macOS and Linux. Native Windows has no supported install yet: say
so, and stop.

## Where kbase stands

`kbase --version` prints the installed version bare, with no `v` — `{KBASE_MIN_VERSION}`, say. What it
prints decides the next step:

| `kbase --version` | next step |
| --- | --- |
| no `kbase` found | install |
| a version earlier than {KBASE_MIN_VERSION} | upgrade |
| {KBASE_MIN_VERSION} or later | none to install; where the tools are not offered, restart the server |

## Install or upgrade

- Install: `brew install {KBASE_TAP_FORMULA}`
- Upgrade: `brew upgrade {KBASE_TAP_FORMULA}`

Then check `kbase --version` against the table again.

## Restart the server

The harness starts the `kbase` MCP server with the bare command `kbase`, found on `PATH`, and only
when the server starts: a kbase installed or upgraded since is not the one serving this session. Ask
the user to restart or reconnect the kbase MCP server in their harness. Its tools are offered once it
is running, and every other route needs them.

## Tools still not offered after a restart

With kbase {KBASE_MIN_VERSION} or later installed and the server restarted, tools still not offered
mean the harness process does not find `kbase` on its own `PATH`, which can differ from the `PATH` of
the user's shell. The user puts Homebrew's `bin` directory, `$(brew --prefix)/bin`, on the `PATH` the
harness starts with, then restarts the harness itself: the server inherits that `PATH` from it.""",
            ),
        ),
    ),
)
