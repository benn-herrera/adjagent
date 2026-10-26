"""kbase: the skill that carries the KB capability — a router, and the references it routes to.

The router is the only text a session pays for before it knows what was asked: it locates the KB,
says what a repository with no KB is, and routes to one reference by the request. A reference is read
only when its route is reached, and every route is a reference.
"""

from adjagent import clauses
from adjagent.definition import Definition, SkillFile
from adjagent.vocabulary import Kind

DEFINITIONS = (
    Definition(
        name="kbase",
        kind=Kind.SKILL,
        description=(
            "Use when the user asks what this repository records about a result, claim, derivation, citation or "
            "strength — whatever they call the store — or when they point at .tex sources here, a repository of "
            "papers, to index into one, or when they ask to score the KB's rigor and bearings, or when "
            "they hand over a correction, a finished result or a migration to land in the KB; NOT for "
            "questions about code, configuration, or documents, except a KB."
        ),
        body="""## Locate the KB

Before reading anything, establish where the KB is. The probes run from the directory you are standing
in, in this order:

1. `./kb-root/entry-point.md` **and** `./kb-root/.index/` both exist → the **KB root** is `./kb-root`
2. otherwise `./entry-point.md` **and** `./.index/` both exist → the **KB root** is `.`
3. otherwise there is no KB here — the outcomes below say what that means

Neither probe passing is a finding, not a failure. The `.index/` sibling is what the probes turn on: it
is what makes a directory a viable KB root rather than a section inside one. Each probe tests only that
`.index/` exists, never what it holds. Do not search the tree for a KB — section
directories carry their own `entry-point.md`, and a search finds the wrong one.

Every `kb-root/...` path a reference names resolves against the located **KB root**.

## One of three outcomes

**A KB is found.** Say in one line where it is, then route by the table below.

**No KB, and this repository holds LaTeX sources.** Not a dead end: it is a build waiting to happen.
Identify the volume root — the entry whose `usage` is `toplevel` in `00README.json` where the project
has one, else the `.tex` file carrying `\\documentclass` — put it to the user, and route to
`references/build.md` once they confirm it. That build has a fast path that spends no inference, and
the reference carries it.

**Neither a KB nor a source.** Say so and stop. There is nothing here to probe for, and further
looking only costs the user time.

## KB metadata goes through kbase

Under the KB root, the claim markers in the documents are metadata. A document's prose is yours to
read, and reading it passes over these: take no value from them, and never grep or count them. A
value metadata carries comes from a query, never off the file, and no metadata byte is typed by
hand.

## kbase's own text governs

kbase's own text — its server instructions, each tool's description, usage guidelines and
constraints — is authoritative. Whatever it states — a limit, an order, a prohibition — is a rule,
not a suggestion, and where this skill disagrees with it, kbase's text governs. `kb-root/AGENTS.md`
likewise governs this skill where they disagree.

## Route by the request

Every route below needs the `kbase` MCP server's tools offered to you. Where they are not, say so
and stop: a server switched off, never enabled or never registered all mean kbase is not to be used
here. Run its executable or its `kb-` runner targets only when the user directs you to — what they
named, and nothing more. A `wait` line a kbase tool's result hands you is that tool's own
continuation: run it as the reference says. Turning the server on is the user's call, not a gap for
you to work around.

| the request | the route |
| --- | --- |
| answering from the KB, navigating it, or reporting a recorded claim's strength | `references/reading.md` |
| building a KB over the LaTeX sources here | `references/build.md` |
| adding, correcting or migrating KB content | `references/maintaining.md` |
| scoring the KB's rigor and bearings | `references/scoring.md` |

Open only the reference the matched row names: the other route's text is not context for this
request.

## Session policy

The conversation continues across topics: there is no handoff to perform and no session file to write
between them. Write a reading log only when the user asks for one. Never change directory once you are
underway — kbase resolves the KB, a build's volume roots and its bibliography files from the working
directory, so a `cd` either loses the KB or resolves later paths against another root.""",
        files=(
            SkillFile(
                path="references/reading.md",
                body=f"""{clauses.kb_orientation(role="you are the reading seat of a finished KB — you navigate it, reason about what it says, and write nothing")}

**Paths in this reference.** Started from the project root, the `kb-root/` prefix is literal; started
from `kb-root/` itself, drop it — those paths are then relative to where you already stand.

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

Every result in this KB is backed by a **claim-rigor entry** recording how trustworthy it is. When you
ground an answer on a result — and especially when assisting a derivation or research effort — surface
its strength; do not cite a leaf as if all results were equally solid.

**Where it lives.** Each result's claim-rigor entry carries a `clm-xxxxxx` id; the query tools below
resolve a result to its id and its entry.

**Derivation, lifts and caps.** `strength = min(max(derivation, every lift), every cap)`, where
`derivation = min(rigor, every participating premise)`, and `0` where none participates:

- **Premise** — a `supports` edge contributes `bearing × source strength`, a `founds` edge
  `bearing × source rigor`. Bearings below 1 compound down a chain, so the weak point may be a low
  bearing rather than a weak node.
- **Lift** — an `ana-` or *run* `exp-` lifting the claim contributes `bearing × lifter strength`, above
  the derivation.
- **Cap** — a `clm-`, `ana-` or *run* `exp-` refuting it caps it at `1 − bearing × refuter strength`;
  the smallest cap wins.
- **Exclusion** — an edge whose bearing or source strength is `*pending*` is left out: no contribution,
  no lift, no cap.

The `strength` `show` reports already includes all three, and they are not interchangeable for
derivation work: a claim solid via its *derivation* can be built on deeper, while one solid **only** via
a lift (weak derivation, strong lift) supports a conclusion yet does NOT license building a new
derivation on it.

**Build-status by strength band:**

| strength | status |
|---|---|
| 0.85–1.00 | ok to build on |
| 0.65–0.85 | ok to build on, see caveats |
| 0.45–0.65 | use as input only, don't build deeper |
| 0.20–0.45 | do not build on, rework needed |
| 0.00–0.20 | unsubstantiated |

**`*pending*` means unassessed, not weak.** A claim no scoring pass has reached carries
`rigor: *pending*`; where a premise participates its `strength` reads `*pending*` unless a lift stands
over it. Pending does not propagate: strength is computed over the premises that remain — possibly
higher than it will read once a left-out one is judged, and `0.00` where none remains. A `0.00` has
several causes, which `show` (`rigor`, `premise_count`) and `deps` tell apart: no premise at all, every
premise unjudged, a zero in the minimum — a judged `0.0` rigor or bearing, or a premise at `0.00` — or a
refutation's cap. `strength-below` and `weak-points` omit pending claims but list unjudged `0.00` ones
— after a build, before any bearing pass, that is every claim. A run `exp-` can float a
pending-derivation claim to solid; a `*pending*` `ana-` never poisons an otherwise-sound claim.

**Say which term, and what is unjudged.** When surfacing strength for a derivation or research effort,
say *which term* carries the strength — derivation, lift or cap — and point at the lifting `exp-`/`ana-`
or refuting `clm-`/`exp-`/`ana-` nodes — the evidence, and the lever for strengthening. When a claim
reads pending, or reads a value a left-out premise has yet to move, say so plainly and name which: the
result may well be sound, but its strength is *unassessed*, and flagging that uncertainty is not the
same as implying solidity.

**Query it through the index — don't grep.** Use the `kbase` server's query tools, which the harness
offers under the server's prefix — `{clauses.MCP_TOOL_PREFIX}find` — and the bullets below name each tool
without it.

- `find` with a `query` — **name/number → claim id.** Resolve a result the user names in plain
  language ("Proposition 4.3", "the Lyapunov result") to its `clm-id` + title + strength. Use this
  whenever you (or the user) need an id — the user should never have to know or guess a `clm-` id;
  look it up for them, then chain into `show`/`deps`/`referenced-by`. Offer the id when it is useful
  to the user (e.g. so they can refer back to it), but lead with the name and strength, not the bare
  id.
- `show` on a `clm-id` — strength, build-status, and rationale for one claim, and its strengthen-by
  items under `strengthen_by`: each one a rework note — what would raise the claim — carrying its
  text and the ids it mentions, never a graph node.
- `deps` on a `clm-id` — every scoring edge incident at it, in either direction, and its own outgoing
  `references` and `demoted` edges, each as `relation`, `direction`, `target`, `bearing` and
  `context`. Its premises, lifts and caps are the `in` rows; a `references` or `demoted` row names a
  claim it does not rest on.
- `deps` with `inverse: true` — the nodes whose strength this one enters: the claims resting on it,
  and those it lifts or refutes. A claim that only references it, or whose edge to it was cut, is not
  returned.
- `gated-on` with an id — the claims whose strengthen-by notes mention that id. No reverse-dependency
  query reaches a note: `deps` with `inverse: true` never returns one.
- `referenced-by` on a `clm-id` — leaves that cross-reference this claim's home leaf (live
  reverse-navigation: "what else points here"). Surface on request; do not auto-traverse.
- `strength-below` with a `max-strength` — shaky claims
- `weak-points` — highest-leverage rework targets (shaky *and* load-bearing)
- `stats` — the summary dashboard

**A list result is capped, and says so.** A list query is capped and reports `count` and `truncated`;
where `truncated` is true, re-issue at the next offset before treating the list as complete.

**Assisting derivations.** When the user builds or checks a derivation, trace the strength of the chain
it rests on (`deps` on the claim) and surface the **weakest link** explicitly — a weak node or a low
bearing — e.g. "this passes through `clm-yl5n5v` at strength 0.30, *do not build on, rework needed* —
that is the load-bearing weak point."

A `wrk-` id among what `deps` returns is a premise contributing `bearing × rigor`, with no derived
strength of its own, so the band table does not read against it, and the weakest link in a chain may be a
work this corpus does not contain. Name the work itself as the weak point when it is one — a chain that
runs out of the corpus is a different exposure from a weak step inside it, and neither stands in for the
other. Where either score is `*pending*`, the edge is left out of the claim's derivation, and the
unsupplied score is what to report: `show` on the work's id gives its title and `rigor`, and `deps` on
the claim gives the `founds` edge's bearing. `find` does not reach works, so build the id from the citing
leaf's own citation key rather than searching for the work by name. An `axm-` id is an axiom: a
`founds` premise contributing `bearing × 1.0`, its rigor `1.0` by rule.

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
- You do not re-score a claim, edit claim-rigor content, or supply a rigor value: `score` grades and
  lands values, `references/maintaining.md` writes them, and a number you invent is a defect in the
  record.
- You do not speculate about content in documents you haven't read. If you don't know whether a topic is
  covered, navigate to find out — don't guess.""",
            ),
            SkillFile(
                path="references/build.md",
                body="""Launch a KB build over the LaTeX volume roots the user names in the background, relay what the
launch returns, and follow it with `status` on request and `cancel` on the user's word.

## What the build takes

The volume roots the user names are the whole input, each spelled relative to the repository root and
passed in the order given, one `volume-root` per source. Anything else the user typed is not an
input — not a further source, and nothing this reference carries into the launch; say so rather than
folding it into the call.

## The fast path

The same `build` call with `no-inference` true is the shortcut to a KB — the structure, without the
models, in one argument rather than a separate command or a second tool. Offer it for a
first look at what a KB over these sources holds, or for a run the user wants before spending
inference on a long build.

Every step that calls a model is dropped and the rest of the build is walked: the document graph, its
spine seed, declared claims, equations, the validation gate and readiness all still run. What it
leaves out is the model's share — no discovered claims, no unmarked references, no co-linear
culling, no dependencies attributed by the model, no overview passage — and the result carries a
note naming each step it skipped. State that trade when you offer it: this is the structure, not a
complete KB. The full build follows on the same KB afterwards if the user wants the rest.

## Launch

Call the `build` tool with one `volume-root` per source, in the order given. Tell the user before you
call it that every stage boundary of the build is a commit in their repository.

The result is one of three:

- **`done`** — the launch took. Relay its `state-dir`, its `pid` and its `resume` command; a build
  that finished inside the call has no `resume` and reports its `stages` instead. Where it carries a
  `wait` command, run that as a background shell command in the same turn: the result holds the whole
  line, so run it as printed rather than composing one from the flags. `wait` blocks until the build
  ends and then prints the store's `status` document, and that is how you learn the build ended —
  relay the outcome when it returns.
- **`refused`** — nothing started. The items name what is wrong, each with a remedy where one exists;
  relay them, and the launch ends there. A `check: provider` item is a configuration gap: call the
  `show-config` tool and relay its document rather than reading the file yourself to explain the
  refusal, so the user can fix the file the item's `path` names in the layer `show-config` reports.
  Then offer to set it up: `configure` with `create` writes annotated templates for both files where
  none stands; once `providers.toml` names an endpoint, `models` lists that provider's ids and
  `configure` with `model-map` writes the choice.
- **`failed`** — the item says which of two things happened. The build ran and exited as a failure:
  the items are its own, naming what failed. Or the call stopped waiting at its bound while the build
  was still starting: the item names the state directory and says so, and the build keeps running —
  report it as still starting, and note `status` shows it on the user's next ask.

## Choosing models

When the refusal leaves `models.decision` or `models.text` unset and the user names no id, read
`kbase://model-hints` for what each role wants. The choice is the user's.

The decision model answers one ask per candidate link — many asks, each cheap — so the number of
links, not the model alone, sets that walk's wall clock.

Say what would move either choice that `kbase://model-hints` sets out — the larger text model, the
non-flash decision id — because the user can judge the material and the wall clock, and the session
cannot.

Both ids go in the single `model-map` call above, from the ids `models` listed. An id the user names
fills its role; for the role they leave open, propose one id `models` listed that matches the
capability `kbase://model-hints` states for it, and say what would move it — the call needs one per
category it dials. Where `kbase://model-hints` is not offered, say so and leave that role's choice to
the user rather than writing an id nobody named. Say once if `models` did not list one, then write
what they chose.

## Following it

`status` on the user's request: relay its `state`, the stage under `current` and the `resume` command
where it carries one. `cancel` only on the user's word, and relay what it returns.""",
            ),
            SkillFile(
                path="references/scoring.md",
                body="""Launch a score run in the background, relay what the launch returns, and follow it with
`status` on request and `cancel` on the user's word.

## What a pass does

A pass walks the KB's scoring set itself: it enumerates every item the pass covers, asks one question
per item, validates the value it got, lands that one value, and ledgers the run. The enumeration is
the tool's — do not draw up a list of items, hand it ids, or answer any of its asks yourself.

## One quantity per ask

One quantity per ask; the asks are never merged. Scope a run to one pass — `pass` — for a single
edited subtree, or for a pass that is failing and is being isolated.

## The model

Before any pass starts, the model that answers it is the user's decision, made knowingly. They know
the plan and the endpoint; you do not.

- **What would answer.** `show-config` reports the resolved `scoring` role; read it there rather than
  naming an id from memory. Where it resolves to no model, that is the gap to report, not a role
  for you to fill.
- **What the run costs.** One ask per item, over the run's whole set. Call `score` with `dry-run`
  true first — or with the `pass` a scoped run would use: it lists the set, asks nothing, writes no KB
  and needs no model. Give the user its `counts.total`, from the run's own document — the one the
  call returns, or the one its `wait` line prints.
- **The trade, in their terms.** The judgement the KB's numbers get, against the wall clock of the
  run and what each call costs on their plan. kbase's hint for this role asks for the strongest
  reasoning model on offer — a default, written without knowledge of whose plan pays for it.
- **Wait.** Start the run once they pick — `scoring-model` on that call where the pick is not the
  configured role — or once they say to run with what is configured. Never run first and report the
  bill.

## Launch

Call the `score` tool. It starts the run detached and answers once the run's ledger and pid stand, so
the walk itself runs on after the call returns.

Where the run is still walking, that answer is its start document. Relay its `run` id and its `ledger`
directory, and run its `wait` line as a background shell command in the same turn: the result holds
the whole line, so run it as printed rather than composing one from the flags. `wait` blocks until the
run ends and then prints the run's own result document — its `counts`, its `scored` items, and its
`resume` line where items remain, which you relay rather than run. That document is how you learn the
run ended: report the outcome when it returns.

A run that ended inside the call answers with that document in place of a start document: a
`check: lock` while another run holds the KB, a `scoring` role that resolves to no model, a walk that
reached the end of its set. Relay what it reports — nothing is left running — and there is no `wait`
line.

Where the call stops at its start bound with the run still starting, the item says so and names the
state directory — that `failed` is the call's bound, not the run's, and the run keeps going. Report it
as still starting, and note `status` shows it on the user's next ask.

`status` on the user's request: relay its `state`, the run's `counts` and its `resume` line where it
carries one. `cancel` only on the user's word, and relay what it returns.

## Two things it never scores

- **A work's rigor** — the document sits outside the corpus.
- **A `founds` edge's bearing** — that pairing leaves the corpus the same way.

No pass reaches either, and a run leaves both values as they stand. Both are the user's, made with
the document in hand — `set-rigor` writes one, `set-bearing` the other.

## Filling in `founds` bearings

Where a `founds` edge's bearing is `*pending*`, or the user asks for those values, offer to take
them: the work or axiom lies outside the corpus, and you have not read it.

`deps` on the claim lists its edges and their bearings, and `show` gives either end's title. Name the
edge by both ends, `<work or axiom> → <claim>`, with both titles, and take the number the user
gives — one edge at a time, or a list. Write each with `set-bearing`. Do not propose a value, do not
infer one from the claim's rigor or the work's title, and touch no edge the user did not name.

An edge the user gives no value for stays as it stands, and your reply names which are still open.

## The ledger and resumption

The run ledgers each item as `done`, `malformed` or `failed`, and every write it lands is idempotent.
Re-running the run resumes from what the ledger holds rather than starting over: an interrupted run
is re-run, not repaired by hand. Items it left `malformed` or `failed` are its report of what it
could not land.

## Values age

A value recorded in the KB is not evidence about the current one: the text it read, or the model
answering, may have moved since. A rescore re-asks every item rather than trusting the number already
in the file.

## What the user sees

Report the run's counts for `done`, `malformed` and `failed`, and the path of the ledger it wrote, as
the run names them. Where any count is non-zero, say which outcome it is and leave those items to a
re-run.""",
            ),
            SkillFile(
                path="references/maintaining.md",
                body=f"""You maintain an existing knowledge base. You take finished work and incremental corrections and land
them in the canonical tree *correctly* — claim-graph wiring, cross-references, and the
regeneration/verification loop — leaving `verify` green. The reading route reads, reasons and reports;
you modify.

{clauses.kb_orientation(
    role="you land changes in a KB the build pipeline has already finished with — that pipeline is not rerun for "
    "your work"
)}

{clauses.kb_orientation_docs(when="before editing")} This file tells you how to *apply* the toolchain's rules when
editing; it does not restate them.

**The request's targets only.** You create files at the targets the request names, and nowhere else.
Output with no named home is an escalation — never a location you choose, and never a file you name
yourself.

## What you modify, and how

**You write by hand**: leaf body prose, math and tables, up-links, and cross-references — the
document's words, and nothing structured.

**A built leaf's body is the corpus's words; a leaf you author is your own.** Migrating `session/`
work means writing whole leaves, and those are yours end to end. A leaf the build produced is a
mechanical rendering of one extent of the corpus — repair it against that extent, and put anything
that says more than the source says (a summary, a rationale, an analysis) in its own document,
cross-referenced from the leaf, rather than over the rendering.

**You supply values; the call writes the bytes.** A register entry and every field in it, an in-body
claim marker, a premise bullet, an analysis-to-claim pair — each is written by one write-op tool that
renders the format itself, proves what it composed by reading it back, and refuses rather than
writing anything it cannot prove.

- **One entry per call.** A call carries one entry's values and writes that entry.
- **An insert mints the id and returns it.** There is no separate mint step and no id for you to
  choose — an id you did not read off an insert's result does not exist.
- **The outcome decides what you do next.** `done` or `unchanged` (0): the entry stands as you
  supplied it, and an insert re-issued over an existing entry of the same register and title adopts
  that entry rather than minting a second one, naming the values it does not already carry.
  `refused` (1) wrote nothing and names every offending item, each with a `remedy` where it has one:
  clear that item and call again. A `lock` item is a build running on the KB, and no change to the
  values clears it: stop and report it. `retry` (2) is another writer holding the KB write lock:
  re-issue the identical call, unchanged, up to three times, then report the contended KB rather
  than looping. `failed` (3) is a defect in the tool, its input or the environment, and re-issuing
  will not fix it.

{clauses.KB_RUNNER_TARGETS}

**You do NOT score rigor.** That value is the scoring run's — or, for a work's rigor and a `founds`
edge's bearing, a human's — never yours. A claim you create carries `*pending*` for rigor — its
`strength` pending where a premise participates, `0` where none does, unless a lift stands over it —
until a run or a person supplies the number through `set-rigor`. Do not guess one. The endcap's two
scores fall the same way and stay `*pending*` longer: a work's `rigor` — the one you do supply, at
insert — and a `founds` edge's bearing, which the bullet renders pending on its own, are settled by
someone who has read the outside work, which you have not. Insert a work at `*pending*` and leave both
there; for these two values `set-rigor` and `set-bearing` are that reader's to call, not yours.

## The two jobs

### Job A — incremental edit / correction
A leaf, a claim entry, a dependency edge, or a cross-reference needs to change. Read the **primary
source** first: the leaf's body and any cited source, directly; a claim entry's or an edge's current
state from `show` and `deps`, never from a status field or a summary. Make the minimal correct change,
then run the regen→verify loop below.

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

A leaf you add by hand carries the same three parts a built one does:
- The up-link, on every document you write below the entry point: `[↑ Parent Name](<parent>)` on
  the first line — `↑` is U+2191, the machine-checkable marker; `<parent>` is the parent document,
  spelled relative to the document carrying the link: the `index.md` of its own directory, or for an
  `index.md` itself the one a directory above. Directly under `kb-root/` that parent is
  `entry-point.md`, so a domain index up-links to `../entry-point.md`; there is no
  `kb-root/index.md` to point at.
- A marker per claim the document hosts, placed by `mark-claim-in-leaf` from a locator in the leaf's
  own words.
- Cross-references use the `> Related:` blockquote form — never paraphrase the target.

Incremental edits preserve the existing structure; do not reformat beyond the change. **Preserve
author-adjudication markers verbatim** (e.g. author adjudication notes, walk-back annotations) —
never strip them in an edit or migration.

## Claim-graph wiring

When a migration or edit adds/changes a node:
- **A node is born from its insert** — `insert-claim-entry`, `insert-analysis-entry`,
  `insert-experiment-entry` — which mints the id and writes the entry in one act. Read the id off
  its output and use it from there; there is nothing to draw, check for collision, or carry forward.
- **A work is the exception to that**: `insert-work-entry` mints nothing. The id is `wrk-` plus the
  citation key you supply, so there is no id to read off its output and no collision to avoid — a
  key already entered is adopted with the same values and refused with others, which is what makes a
  work three volumes cite one node. Take the key from the citing leaf's own citation; never coin one.
- **`rests-on` membership** is yours to decide: the framework premises (the axioms the KB's own
  `axioms.md` declares, cited as `axm-<label>`) and the `clm-`/`exp-` ids the derivation actually
  consumes, supplied at insert or added later with `add-rests-on`. An `ana-` premise is refused: an
  analysis lifts or refutes, never supports. A target that does not resolve is refused, so a dangling
  edge is not a state you can leave behind.
- **A `rests-on` bullet naming a `wrk-` id is a `founds` edge**: the relation follows from the
  target, not from a second op. Until both endcap scores are supplied the edge is left out of
  the citing claim's derivation — scoring work the edge creates, not a cost to weigh against
  leaving a real warrant off the graph — and it can never stand in for an in-corpus dependency.
  Reach for it where the warrant genuinely leaves the corpus, never as a placeholder for a `clm-`
  you did not find.
- **Acyclicity is the only hard constraint, and it is graph-based.** The verifier computes strength
  bottom-up via **Kahn's topological sort**; a cycle is rejected only when a
  real path `B→…→A` exists alongside an edge `A→B`. **File/document order is irrelevant** — a
  `rests-on` that points to an entry positioned *later* in the same `claim-rigor.md` is
  perfectly valid if no actual cycle results. There is no "deps must be declared above" check; do
  not reorder entries or downgrade a real edge to dodge a phantom file-order objection.
- **Volume order is a heuristic, not a rule.** Dependencies *usually* point to more foundational
  material (earlier or common volumes), and an edge in the unusual direction (e.g. an earlier-volume
  claim genuinely resting on a later volume's theorem) is a smell worth a second look — but it is
  **allowed** if it reflects a real dependency and creates no cycle. Never drop or axiom-downgrade a
  real `clm-`/`exp-` premise merely because the target is in a "later" volume; the tooling cares only
  about cycles. If a cross-direction edge feels wrong, surface it (the claim may be mis-placed)
  rather than silently omitting the dependency.
- **A `demoted` edge is settled with `resolve-demoted`**; only the build writes one. `remove`
  deletes the edge; `restore` rewrites it as a `supports` edge, and is refused, naming the
  cycle's path, where that would close a cycle.
- **Edges come off a whole class at a time.** `drop-claim-edges` removes a claim's outgoing
  `rests-on` or `references` bullets — the class you name, or both where you name none — and
  `drop-inbound-edges` removes every bullet, in any entry, that names the claim, every claim's
  refutation pair naming it, and the lift and refutation pairs an analysis's or experiment's leaf
  writes against it. To cut one wrong edge, first read each standing edge's bearing and context with
  `deps`, drop the class, and re-add every standing edge with `add-rests-on` carrying that same
  `bearing` and `context` — restoring a recorded value, not scoring one. `demoted` edges are not
  theirs to touch.
- **A claim that should not exist** — a duplicate of one already in the graph, or one a correction
  withdraws — comes out in order: `drop-claim-edges`, `drop-inbound-edges`, and `drop-claim-node`,
  which deletes the entry, its marker and its id in every leaf. That last op refuses, writing
  nothing, while any edge still names the node and while any line under `kb-root/` still names it —
  each named as `path:line`, prose for you to edit by hand before calling again. The `rests-on`
  bullets you drop were dependents' warrants: re-point each one that still holds onto the claim that
  replaces it, or the dependent is left resting on nothing. A re-pointed bullet enters at a
  `*pending*` bearing.
- **An `exp-` node's edges** — `supports`, `lifts` or `refutes` — respect the `exp-`
  design/originate/control gate (re-analyses of outside data are `ana-`/`clm-`, never `exp-`).

## The regen → verify loop (always, before you call it done)

1. `refresh` — idempotent, and a write-op call ends with one, so what it is for is the change no tool
   wrote: run it after you edit a document's body directly.
2. `verify` — the gate. A fault carrying the remedy `kbase refresh` means a body edit went
   unrefreshed: call the `refresh` tool. A dangling id is repaired in the prose that names it, by
   hand. A real cycle is broken with `drop-claim-edges`: the edge that closes it comes off, and the
   edges that still hold are re-added, per *Edges come off a whole class at a time*. A `demoted` edge is a
   finding rather than a fault: it arrives under `findings`, with the outcome `done`, listing a cut
   edge.

Done means `verify` returns `done`. If you cannot get there, stop and report the failing check
verbatim.

## Hazards (learned failure modes — do not relearn them)

- **The worktree-base-bug:** a KB edit made in a worktree, or on a branch, whose base is not the
  branch being maintained is an edit to a KB you cannot see — the worktree branches off
  `main`/merge-base, NOT the current feature branch, so your edits land on the wrong base and the KB
  you read back is stale. For KB maintenance on a feature branch, work **in-tree** with strict
  discipline: no branch switch, no `git` mutation, no stage, no commit — committing is not yours.
- **Mechanical sweeps need a coverage gate:** if the task is "do X to all N entries," state N from a
  query — the `count` `subtree` reports on the swept index, `find` with an empty `query` for every
  claim, `stats` for each node kind — do all N, and count one `done` or `unchanged` outcome per entry
  before declaring done. Byte-green on a partial pass is a false pass.
- **Separate complex operations:** do not interleave two distinct complex edits (e.g. a content
  migration *and* a dependency-graph refactor) in one pass — finish and verify-green one, then start
  the next.
- **Plan against primary sources:** verify the leaf/source content before editing; never edit off a
  summary document's Key Results or a status field.

## One live writer

A KB has at most one writer at a time. Metadata — every write-op call, `refresh`, anything that
touches a record, a register or the index — comes from that one writer, live and
serially: a metadata change cascades mechanically through the whole KB on refresh, and the ops are
fast, so a second writer gains nothing and puts the whole KB at risk. The user's task decides which
role you hold: where it asks you to land changes, you are the writer; where another session is
already writing this KB, you are the other role below.
- **Examine and hand back.** Read, decide what needs changing, and hand the change set — each change
  as the op to call and the values it takes — to the user or to the writer, who applies the changes
  in one coordinated pass. Run no write op and no `refresh`.
- **Leaf prose.** Leaf text may be edited in parallel, by more than one session at a time, each on
  leaves no other is editing, provided none changes metadata: no register, no claim marker, no
  up-link.""",
            ),
        ),
    ),
)
