"""kbase: the skill that carries the KB capability — a router, and one reference per route.

The router is the only text a session pays for before it knows what was asked: it locates the KB,
says what a repository with no KB is, and routes to one reference by the request. The two references
are read only when their route is reached, and the two specialist seats stay agents the router
dispatches.
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
            "papers, to index into one, or when they ask to grade a derivation that carries no score; NOT for "
            "questions about code, configuration, or documents, except a KB."
        ),
        body="""## Locate the KB

Before reading anything, establish where the KB is. The probes run from the directory you are standing
in, in this order:

1. `./kb-root/entry-point.md` **and** `./kb-root/.index/` both exist → the **KB root** is `./kb-root`
2. otherwise `./entry-point.md` **and** `./.index/` both exist → the **KB root** is `.`
3. otherwise there is no KB here — the outcomes below say what that means

Neither probe passing is a finding, not a failure. The `.index/` sibling is what the probes turn on: it
is what makes a directory a viable KB root rather than a section inside one. Do not search the tree for
a KB — section directories carry their own `entry-point.md`, and a search finds the wrong one.

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

## Route by the request

Every route below needs the `kbase` MCP server connected. If it is not, say so and stop — registering
it, which the install does, is the fix, not a second interface.

| the request | the route |
| --- | --- |
| answering from the KB, navigating it, or reporting a recorded claim's solidity | `references/reading.md` |
| building a KB over the LaTeX sources here | `references/build.md` |
| adding, correcting or migrating KB content | dispatch the `kb-maintainer` agent |
| grading a derivation that carries no score yet | dispatch the `kb-claim-scorer` agent |

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

## Claim quality and solidity

Every result in this KB is backed by a **claim-quality entry** recording how trustworthy it is. When you
ground an answer on a result — and especially when assisting a derivation or research effort — surface
its quality; do not cite a leaf as if all results were equally solid.

**Where it lives.** A leaf's frontmatter `claims:` field lists the claim-quality IDs (`clm-xxxxxx`) it
carries; each ID resolves to an entry in a `claim-quality.md` register (the root one and the per-volume
ones).

**Two solidity branches.** `solidity = max(derivation_solidity, experimental_solidity)`: the
**derivation branch** is `min(confidence, dependency solidities, cited works' strengths)` — the
**weakest link** in the claim's dependency cone (not a product down the chain; refactor-invariant),
raised by any `sup-` support (dep-gated); the **experimental branch** is the strength of any *run* `exp-`
strengthening the claim. The `solidity` on the entry already includes both, and the two are not
interchangeable for derivation work: a claim solid via its *derivation* can be built on deeper, while one
solid **only** via an `exp-` (weak derivation, strong experiment) supports a conclusion yet does NOT
license building a new derivation on it.

**Build-status by solidity band:**

| solidity | status |
|---|---|
| 0.85–1.00 | ok to build on |
| 0.65–0.85 | ok to build on, see caveats |
| 0.45–0.65 | use as input only, don't build deeper |
| 0.20–0.45 | do not build on, rework needed |
| 0.00–0.20 | refuted, do not use |

**`*pending*` means unassessed, not weak.** A claim no scoring pass has reached carries
`confidence: *pending*` and therefore `solidity: *pending*`. Pending propagates: a claim that depends on
a pending claim is itself pending regardless of its own confidence, and so is a claim resting on outside
work nobody has judged yet. Those three causes — its own rigor unscored, a dependency pending, a cited
work unjudged — take different remedies. A run `exp-` can float a pending-derivation claim to solid; a
`*pending*` `sup-` never poisons an otherwise-sound claim.

**Say which branch, and which pending.** When surfacing quality for a derivation or research effort, say
*which branch* carries the solidity and point at the supporting `exp-`/`sup-` nodes — the evidence, and
the lever for strengthening. When a result's claim is pending, say so plainly and name which of the
three causes it is: the result may well be sound, but its quality is *unassessed*, and flagging that
uncertainty is not the same as implying solidity.

**Query it through the index — don't grep.** Use the `kbase` server's query tools, which the harness
offers under the server's prefix — `{clauses.MCP_TOOL_PREFIX}find` — and the bullets below name each tool
without it.

- `find` with a `query` — **name/number → claim id.** Resolve a result the user names in plain
  language ("Proposition 4.3", "the Lyapunov result") to its `clm-id` + title + solidity. Use this
  whenever you (or the user) need an id — the user should never have to know or guess a `clm-` id;
  look it up for them, then chain into `show`/`deps`/`referenced-by`. Offer the id when it is useful
  to the user (e.g. so they can refer back to it), but lead with the name and solidity, not the bare
  id.
- `show` on a `clm-id` — solidity, build-status, and rationale for one claim, and its strengthen-by
  items under `strengthen_by`: each one a rework note — what would raise the claim — carrying its
  text and the ids it mentions, never a graph node.
- `deps` on a `clm-id` — the edges it holds, each with its relation, a `rests-on` pairing's
  applicability, and the edge's context. A `references` or `demoted` edge names a claim it does not
  rest on.
- `deps` with `inverse: true` — the nodes whose solidity this one enters: the claims resting on it,
  or for an `exp-`/`sup-` the claims it lifts. A claim that only references it, or whose edge to it
  was cut, is not returned.
- `gated-on` with an id — the claims whose strengthen-by notes mention that id. No reverse-dependency
  query reaches a note: `deps` with `inverse: true` never returns one.
- `referenced-by` on a `clm-id` — leaves that cross-reference this claim's home leaf (live
  reverse-navigation: "what else points here"). Surface on request; do not auto-traverse.
- `solidity-below` with a `threshold` — shaky claims
- `weak-points` — highest-leverage rework targets (shaky *and* load-bearing)
- `stats` — the summary dashboard

**A list result is capped, and says so.** A list query returns `limit` results from `offset` (default 50,
`0` means all) and reports `count` and `truncated`; where `truncated` is true, re-issue the query at the
offset plus what came back, before treating the list as complete.

**Assisting derivations.** When the user builds or checks a derivation, trace the solidity of the chain
it rests on (`deps` on the claim) and surface the **weakest link** explicitly — e.g. "this passes through
`clm-yl5n5v` at solidity 0.30, *do not build on, rework needed* — that is the load-bearing weak point."

A `work-` id among what `deps` returns is a gate term with no solidity of its own, so the band table does
not read against it, and the weakest link in a chain may be a work this corpus does not contain. Name the
work itself as the weak point when it is one — a chain that runs out of the corpus is a different exposure
from a weak step inside it, and neither stands in for the other. When such a claim reads `*pending*`, the
unsupplied score is what to report: `show` on the work's id gives its title and `strength`, and `deps` on
the claim gives the pairing's applicability. `find` does not reach works, so build the id from the citing
leaf's own citation key rather than searching for the work by name.

## Cross-references

When you encounter a `> Related:` suggestion in a document:

Surface it explicitly: "There's a cross-reference to [topic name] in [domain B]. Want me to pull it in?"

Do not follow cross-references automatically. The user decides whether the additional context is worth
the token cost.

## Constraints

These are rules, not a role: nothing here is about what you *are*, and all of it binds every answer.

- You do not modify KB content. If the user identifies an error in a KB document, note it — do not fix
  it; landing the correction is the `kb-maintainer` agent's job, dispatched from the router. The KB is a
  read-only reference during a reading session.
- You do not generate new mathematical content. You navigate to and reason about existing content. If
  asked to derive something not in the KB, say so explicitly and distinguish your reasoning from KB
  content.
- You do not re-score a claim, edit claim-quality content, or supply a rigor value: `kb-claim-scorer`
  grades, `kb-maintainer` writes, and a number you invent is a defect in the record.
- You do not speculate about content in documents you haven't read. If you don't know whether a topic is
  covered, navigate to find out — don't guess.""",
            ),
            SkillFile(
                path="references/build.md",
                body="""Launch a KB build over the LaTeX volume roots the user names in the background, relay what the
launch returns, and follow it with `status` on request and `cancel` on the user's word.

## What the build takes

The volume roots the user names are the whole input, each spelled relative to the repository root and
passed in the order given, one `volume-root` per source. The KB root is always `kb-root/`, a name the
tool hard-codes and takes no override for. Anything else the user typed is not an input — not a further
source, and nothing this reference carries into the launch; say so rather than folding it into the call.

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

When the refusal leaves `models.decision` or `models.text` unset and the user names no id, recommend
both from what `models` listed: for `text`, a small instruct model of the 9B-12B class — it writes the
overview passage, and a larger one earns its place only when inference is fast and the material is very
complex; for `decision`, a small or medium reasoning model — `clef`, `d3`, `openjev` or a flash sibling
— where the catalog holds one.

The decision model answers one ask per candidate link: many asks, each cheap. On a local endpoint a
flash sibling is the better default; take the full id where the endpoint is hosted or the user says
quality outranks wall clock.

Where `show-config` reports the entry's `decisions-flavor` as `systemone` — oMLX's surface — every id
`models` listed is accepted on the decision surface; under `decisions` the server accepts a narrow set
it alone names, so use only an id it names. A model built for reasoning nonetheless does better on
multiple-choice questions than a general instruct model.

Say what would move either choice — the larger text model, the non-flash decision id — because the
user can judge the material and the wall clock, and the session cannot.

Both ids go in the single `model-map` call above. An id the user names fills its role and this guidance
fills the other; a pair they name is used as given — say once if `models` did not list one, then write
what they chose.

## Following it

`status` on the user's request: relay its `state`, the stage under `current` and the `resume` command
where it carries one. `cancel` only on the user's word, and relay what it returns. A launch while a
build runs is refused (`lock`).""",
            ),
        ),
    ),
)
