# ACTIVE_PLAN.md — kb_tools adopts kbase's decision endpoint, cull stage, shortlist, cycle cut and write ops

**Status: complete.** Items 1 (`4e9adc1`), 2 (`6aef453`), 3 (`3d75495`), 4 (`33555f7`), 5
(`81d4813`), 6 (`8f11492`), 7 (`30e6ebd`), 8 (`259ebb7`), 9 (`d0840e5`) and 10 (the documents
and §4's proof tests) landed. D1 and D3 are decided (§3). kbase at
commit `5aab244` (2026-10-15) is the reference, and every quotation below holds at it. If kbase has
moved past `5aab244`, the plan is re-taken before the first dispatch. kbase
SPEC §2 fixes the roles: kb_tools' KB contract is what both toolchains build to; for the inference
layer, the tool interface and maintenance-op behaviour kbase is the canonical design and kb_tools
tracks it.

The work is one surface in ten items (§2), each its own commit. Items 1 and 2 are the largest
change: every claim-graph letter ask leaves the chat-completions path for one decision request to
the server's `systemone` endpoint, and the templates split into the state a question is asked over
and the question itself. Items 3, 4, 6 and 9 need neither; items 5, 7 and 8 need item 2.

## 1. The difference set

Each subsection states what kbase does, in its words where kb_tools must match them, then what
kb_tools does today, from its own files. The commands that settled the kb_tools side are given with
their answers, for the executing agent to re-run.

### 1.1 The letter asks: one decision request per ask

**kbase.** SPEC §5: "The letter asks are each one `POST <base-url>/systemone` request carrying a
closed-set question (`choice` or `noul`) and answered by probabilities over that set — no reply
text is parsed; the overview call remains one tool-less chat request answered from its prompt
alone." ARCHITECTURE §7: "the payload is `model`, `state`, `questions` — `questions` a JSON
object keyed by the question key, kbase sending exactly one question (`choice` or `noul`) whose
`criteria` carry the per-letter meanings the templates' bullet lists used to carry; the answer
comes back keyed the same way, probabilities over the offered letters, no reply text parsed. The
request is re-issued identically up to the chat attempt count on a transport error or retry-class
5xx, with no streaming and no incomplete-stream path. … a decision call has no system message."

The wire shape and rules, from kbase's `internal/model/decision.go` and `http_client.go`:

- URL and auth: `BaseURL` "is the API root; `chat/completions` and `models` hang off" it, and
  "the decision-model endpoint hangs off `Endpoint.BaseURL` beside chat/completions and models",
  so the decision URL is the base URL kb_tools already holds (with `/v1` in it) plus `/systemone`.
  Every request carries `Authorization: Bearer <key>`, as the chat path does.
- Request: `{"model": …, "state": …, "questions": {<key>: {"type": "choice"|"noul",
  "instructions": …, "criteria": {<option>: <guidance>}}}}`. Nothing else: no temperature, no
  `chat_template_kwargs`, no stream fields, no system message. `state` is the composed template
  text (§1.2); the key is the item's name, opaque to the server and echoed back. `criteria` is
  keyed by the offered letters for a `choice` question and by `"true"`/`"false"` for a `noul`
  question. The type `score` exists on the wire and is not sent until an ask uses it.
- Response: `{"model": …, "answers": {<key>: {"type": …, "choice"?: …, "noul"?: P(true),
  "confidence"?: …, "probabilities"?: {<letter>: p}}}, "usage": {"input_tokens": n,
  "output_tokens": n}}`. A `noul` answer carries `noul` alone; a `choice` answer carries `choice`
  and may carry `confidence` and `probabilities`. Unknown keys are ignored.
- Retry and refusal: the identical body re-issued up to the attempt count on a transport error, a
  429 or any 5xx, with no pause; any other 4xx returns at once. An answer arriving under a key the
  request did not ask is refused as server misbehaviour, not retried. A missing answer is not
  refused: the seam re-asks once and then defaults.
- Letter from answer (`internal/asks/call/call.go` `confidence`, `internal/asks/letters.go`
  `Decide`): a `choice` answer's `probabilities` where present, else `{choice: confidence}`; a
  `noul` answer with `0 ≤ noul ≤ 1` becomes `{true-letter: noul, other-letter: 1 − noul}` over
  a two-letter offer. The letter is the argmax over the *offered* letters, the first offered winning
  a tie; nothing decided is an unreadable reply. The re-ask is the identical question with attempt
  ordinal 2 keeping the two apart in the answer cache; a deterministic decision model answers it
  identically and the item defaults.
- Tiers: letter asks go to the decision tier, the overview call to the text tier; the two are two
  model ids (kbase SPEC §9.2 `[models] decision` / `text`). A SystemOne decision model is not the
  overview call's model, so kb_tools needs a second model variable (item 1).

**kb_tools today.** SPEC "The Driver's Contract": "Every model call a build makes is one tool-less
chat-completions request to the server its environment names — `API_BASE_URL`, `MODEL`,
`API_KEY_FILE` and `ALLOW_HTTP`, in `liaison_tools`' env format". The transport is
`kb_tools/inference/liaison_tools.py` `call_chat`; retry is the caller's — ARCHITECTURE's
`inference/` row: "**Policy is the caller's**: retry, a re-ask, where a bound's value comes from.
It knows no KB vocabulary." — and the loop lives in `kb_claimgraph/ask.py`. The reader is `ask.py`
`ask_without_tools`, a `LetterReader` returning a `Reply` whose `text` is parsed to one offered
character. `Reply.confidence` exists and `decide` already prefers it, but nothing fills it:

```
grep -n 'Returns no ``confidence``' kb_tools/kb_claimgraph/ask.py     → ask.py:368
grep -n 'confidence' kb_tools/inference/liaison_tools.py               → (nothing)
grep -n 'TRANSPORT_ATTEMPTS' kb_tools/kb_claimgraph/ask.py  → ask.py:66; the loop near 378
```

### 1.2 Templates split into a state and a question

**kbase.** A letter ask's template renders the *state* alone. The question lives in a question
file beside it, `questions/<kind>.question.yaml`, with `type`, `instructions`, `criteria` and, for
a `noul` question, `true-letter`; the offered letters reach both files only as composer constants
(`@!letter-…!@`). Provenance, from kbase's manifest: `paragraph`, `unmarked` and `classify` state
templates and the four question files derived from them are `kbase-authored` (derived from
kb_tools' templates); `colinear.tmpl.md` and `questions/colinear.question.yaml` are
`kbase-origin`; the overview template and its two fragments are `imported`, byte-identical to
kb_tools'.

Two meanings changed with the split, beyond the framing: the unmarked ask now asks whether the
source claim *continues the argument* the candidate is part of, read leniently, where kb_tools'
template asks whether it *leans on* the candidate; and the paragraph ask's `"false"` criterion
names a recap — "the paragraph retells a result without stating or deriving it here" — as
stating no result.

The three state templates, verbatim:

`paragraph.tmpl.md`:

````markdown
You are reading one document of a knowledge base a paragraph at a time.

## The document: `@!dyn.document!@`

Each label marks one sentence as the page shows it, or one display-maths block with its lines
beneath it; the label and its colon belong to this rendering, not to the document. A blank line
ends a paragraph, and a paragraph is named by the range of its labels. Unlabelled lines — headings,
and any block the document marks as a claim, a proof or a definition — are context only.

````````````markdown
@!dyn.body!@
````````````

## The paragraph

The paragraph is @!dyn.paragraph!@:

````````````markdown
@!dyn.paragraph-text!@
````````````
````

`unmarked.tmpl.md`:

````markdown
You are deciding whether the source claim continues the argument the
candidate claim is part of, where no cross-reference links the two. The
candidate claim may be stated in this document or in another; its line below
names where.

## The document: `@!dyn.document!@`

The source claim is stated in this document, and shown again below. The document is here so that
the source claim's words can be resolved: where the source claim says "this estimate" or "the
bound above", the document says which one.

````````````markdown
@!dyn.body!@
````````````

## The source claim

@!dyn.claim-line!@

````````````markdown
@!dyn.claim-text!@
````````````

## The candidate claim

@!dyn.candidate-line!@

````````````markdown
@!dyn.candidate-text!@
````````````
````

`classify.tmpl.md`:

````markdown
You are classifying one link between two claims of a mathematical text, a source claim and a
candidate claim, and you decide what the link means. The link rests on text belonging to the source
claim — its statement, a proof of it, or the prose around it.

## The source claim

@!dyn.claim-line!@

````````````markdown
@!dyn.claim-text!@
````````````

## The source claim's passages

Each passage below is text belonging to the source claim that one or more of its links rests on;
its P-number names it. A passage may point at a claim, or be the source claim's own text and point
at none.

@!dyn.reference-lines!@

## The candidate claim

@!dyn.candidate-line!@

````````````markdown
@!dyn.candidate-text!@
````````````

The link to the candidate claim rests on @!dyn.candidate-passages!@.
````

`colinear.tmpl.md`:

````markdown
The two claims below are shown in reading order, each as its line — naming the claim and where
it is stated — and its statement.

## The first claim

@!dyn.first-line!@

````````````markdown
@!dyn.first-text!@
````````````

## The second claim

@!dyn.second-line!@

````````````markdown
@!dyn.second-text!@
````````````
````

Its slots, filled by the composer for each item:

| Slot | Holds |
|---|---|
| `@!dyn.first-line!@` | the earlier claim's line, naming the claim and where it is stated |
| `@!dyn.first-text!@` | the earlier claim's statement, trailing newlines trimmed |
| `@!dyn.second-line!@` | the later claim's line |
| `@!dyn.second-text!@` | the later claim's statement, trailing newlines trimmed |

Its letters: `A` second adds nothing, `B` first adds nothing, `C` distinct, offered all three on
every item. First and second are reading order (§1.5); the record's `a` and `b` are id order, so a
verdict is recorded by id: letter `A` records `a-adds-nothing` where the second-shown claim is the
record's `a`, else `b-adds-nothing`; letter `B` the same for the first-shown claim; `C`, and an ask
with no readable letter after the re-ask, record `distinct`.

The five question files, text verbatim (comment lines dropped here; kb_tools stores the files byte
for byte, D1 in §3):

`questions/paragraph.question.yaml`:

```yaml
type: noul
true-letter: "@!letter-claim!@"
instructions: |-
  Does this paragraph state a result of its own?
criteria:
  "true": |-
    states a result: the paragraph itself asserts a theorem, a relation it
    derives, a bound, a condition under which something holds, or a conclusion
    it draws from an argument. A result stated in plain prose counts, and one
    sentence asserting it is enough.
  "false": |-
    states none: motivation, signposting, a recap — the paragraph retells a
    result without stating or deriving it here — notation, a definition, or
    narrative. A notation table or a section preamble states no result of its
    own.
```

`questions/unmarked.question.yaml`:

```yaml
type: noul
true-letter: "@!letter-points!@"
instructions: |-
  Does the source claim continue the argument the candidate claim is part
  of? Answer true if it does, false if it does not.
criteria:
  "true": |-
    The source claim continues the argument the candidate claim is part of:
    it builds on the candidate claim, applies it, or carries the same line of
    reasoning forward. Read this leniently — capture here is generous, and
    sharper judgment happens later. The connection may be loose, implicit or
    roughly stated: the candidate claim may be where a result the source
    claim uses or assumes is set out, where a condition or quantity it names
    by description ("the bound above", "this estimate", "the condition of
    the previous section") is set out, or where notation is introduced that
    the source claim then works with.
  "false": |-
    does not continue it: the source claim is not part of the same argument
    as the candidate claim. Answer false when the source claim stands apart
    from the candidate claim's line of reasoning — as when any of these
    holds:
    - The two claims share only a subject or notation.
    - The source claim merely mentions the candidate claim's subject — a
      passing nod, color, an aside — without the source claim's own
      reasoning building on or drawing from that mention.
    - Each claim states a result of its own; neither builds on the other.
```

`questions/classify-three.question.yaml`:

```yaml
type: choice
instructions: |-
  Does the source claim need the candidate claim, does the candidate claim
  need the source claim, or neither? Decide from what the two claims state
  and what the passages say one does with the other. That a passage points
  at the candidate claim without saying why, or does not point at it at all,
  is not evidence for any of the answers.
criteria:
  "@!letter-supported-by!@": |-
    supported by: the source claim needs the candidate claim to be true. The
    source claim's statement or its proof uses the candidate claim as a
    premise or a step.
  "@!letter-in-support-of!@": |-
    in support of: the candidate claim needs the source claim to be true. The
    source claim is a premise or a step for the candidate claim.
  "@!letter-mention!@": |-
    mention: neither needs the other. The source claim borrows a method from
    the candidate claim, refers the reader to it, compares itself with it, or
    recaps it.
```

`questions/classify-two.question.yaml`:

```yaml
type: choice
instructions: |-
  Does the source claim need the candidate claim — does its statement or its
  proof use the candidate claim as a premise or a step? If it does, choose
  supported by; if it does not — including when the passages show the
  candidate claim building on the source claim — choose mention. Decide from
  what the two claims state and what the passages say one does with the
  other. That a passage points at the candidate claim without saying why, or
  does not point at it at all, is not evidence for any of the answers.
criteria:
  "@!letter-supported-by!@": |-
    supported by: the source claim needs the candidate claim to be true. The
    source claim's statement or its proof uses the candidate claim as a
    premise or a step.
  "@!letter-mention!@": |-
    mention: the source claim does not need the candidate claim. The source
    claim borrows a method from the candidate claim, refers the reader to it,
    compares itself with it, recaps it — or the passages show the candidate
    claim building on the source claim.
```

`questions/colinear.question.yaml`:

```yaml
type: choice
instructions: |-
  Does one of the two claims add nothing to the other, or is each a step of its own? A step is what
  a claim adds to the argument: a conclusion, a construction, an estimate, or an application of a
  result. Compare only what each claim states. If the two claims each add nothing the other does
  not state, choose second adds nothing.
criteria:
  "@!letter-second-adds-nothing!@": |-
    second adds nothing: the second claim states no step that the first claim does not already
    state. For example, the second claim restates, paraphrases or glosses the first, motivates it,
    or comments on it — each only where it states no step of its own.
  "@!letter-first-adds-nothing!@": |-
    first adds nothing: the second claim states a step that the first does not, and the first
    claim states no step that the second does not already state. For example, the first claim
    announces, motivates or sketches the result the second states — each only where it states no
    step of its own.
  "@!letter-distinct!@": |-
    distinct: each claim states a step that the other does not. For example, the two claims state
    different results, or one applies or extends the other — each only where both claims keep a
    step of their own.
```

**kb_tools today.** `kb_driver/prompt-templates/` holds `classify.tmpl.md`, `paragraph.tmpl.md`,
`unmarked.tmpl.md`, `overview-passage.tmpl.md` and six fragments
(`classify-options-two`, `classify-options-three`, `letter-correction`, `overview-correction`,
`overview-system`, `reader-system`). The letter options and the closing question are in the
template bodies and the `classify-options-*` fragments; the re-ask appends `letter-correction`
carrying what came back; every letter ask carries `reader-system` as its system message. There is
no `questions/` directory and no co-linearity template:

```
command ls kb_tools/kb_driver/prompt-templates kb_tools/kb_driver/prompt-templates/fragments
grep -n 'FRAGMENT_SLOTS\|"correction": (None' kb_tools/kb_driver/prompt_templates.py
                                                   → prompt_templates.py:119, :137
grep -n 'LETTER_CORRECTION = \|CLASSIFY_OPTIONS_SLOT = \|READER_SYSTEM = ' \
  kb_tools/kb_claimgraph/ask.py                    → ask.py:151, :152, :77
```

### 1.3 The four write ops

**kbase.** `internal/write/values.go` `opFields`, as a table; `kb.Origins` is `cited`, `inferred`:

| Op | Fields (name, check, required) |
|---|---|
| `drop-claim-edges` | `id` claim id, required; `edge-class` edge class, optional |
| `drop-inbound-edges` | `id` claim id, required |
| `demote-claim-edge` (build-only) | `id` claim id, required; `target` claim id, required; `origin` one of `cited`/`inferred`, required; `context` prose, optional |
| `drop-claim-node` | `id` claim id, required |

Three are public subcommands; `demote-claim-edge` is build-only, absent from the public op list and
from `--help`, reachable only by the build. Semantics (kbase SPEC §8, §10):

- `drop-claim-edges` removes a claim entry's outgoing `depends-on` or `references` bullets, the
  class named by `edge-class` or, where none is, both; each bullet goes with its continuation lines,
  and a list's header goes where neither bullet nor other text is left. An absent list stands.
  `edge-class: demoted` is refused: demoted rows are `resolve-demoted`'s to remove. A re-issue is
  `unchanged`.
- `drop-inbound-edges` removes, from every register entry holding one, each `depends-on` or
  `references` bullet naming `id`, with its continuation lines, and a list's header where neither
  bullet nor other text is left; an entry naming no such bullet stands. A re-issue is `unchanged`.
- `demote-claim-edge` turns `id`'s existing `depends` edge naming `target` into a `demoted` row of
  the same entry carrying `origin`, which the build computes by the origin rule (§1.4). Where that
  row already stands with the same origin, it removes a `depends` bullet still standing beside it
  (`done`) and otherwise leaves the pair (`unchanged`); a row standing with the other origin is
  refused, naming both origins; a pair with neither a `depends` bullet nor a `demoted` row is
  refused.
- `drop-claim-node` deletes the claim node entirely: its register entry block, its claim-quality
  marker from every leaf carrying it (a leaf restated no-claim included), its id from every leaf
  claiming it, and every other entry's `demoted` row naming it. Refused, writing nothing, where any
  entry's `depends-on` or `references` still names the node; where the call would empty a leaf's
  `claims` list (the nodes one call drops from a leaf counted together), that being a no-claim
  decision `set-frontmatter` makes; and where, once those removals are composed, any line under
  `kb-root/` still names the node, each such line named as `path:line` (refresh's own roll-ups
  excepted). A re-issue removes whatever of the node still stands (`done`) and is `unchanged` where
  nothing does. The issuer restates a leaf hosting only the culled claim no-claim through
  `set-frontmatter` before the drop.

On `add-build-edges`, kbase ARCHITECTURE §6: "`add-build-edges` keeps its `demoted` list as op
vocabulary shared with kb_tools, and no build caller passes it."

**kb_tools today.** `kb_write/values.py` `OP_FIELDS` carries one build-only op, `add-build-edges`;
`kb_write/ops.py` `BUILD_OPS` holds it alone; none of the four exists; the public ops have
`kb_util.OP_*` tokens that a test holds equal to `OPS`:

```
grep -n '"drop-claim-edges"\|"drop-inbound-edges"\|"drop-claim-node"\|"demote-claim-edge"' \
  kb_tools/kb_write/values.py kb_tools/kb_write/ops.py                 → (nothing)
grep -n 'BUILD_OPS: Mapping' kb_tools/kb_write/ops.py                  → ops.py:3309
grep -n 'OP_ADD_DEPENDS_ON = \|OP_RESOLVE_DEMOTED = ' kb_tools/kb_util.py → kb_util.py:331, :335
grep -n 'is the one op over a cut' kb_tools/SPEC.md                    → SPEC.md:875
```

`tests/test_kb_write_ops.py` `test_every_op_of_the_surface_has_a_closed_values_vocabulary` asserts
the union of `ops.OPS`, `ops.READ_OPS` and `ops.BUILD_OPS` equals `values.OP_FIELDS`'s keys, so the
four rows and their registry entries land together.

### 1.4 The cull record and the origin rule

**kbase.** The cull record is the fourth tracked build record, `kb-build-cull.yaml` at the
repository root beside `kb-build-node-pass.yaml`, `kb-build-unmarked.yaml` and
`kb-build-classification.yaml`, committed with `kb-root/` at each stage boundary. SPEC §6: "The
cull record holds `about`; `entries`, one per co-linearity ask, sorted by `pass`, `a`, `b`, each
with `a` and `b` (the two claim ids, `a` before `b` in id order), `pass` (1 or 2), `verdict`
(`a-adds-nothing`, `b-adds-nothing` or `distinct`) and `outcome` (`answered`, `re-asked` or
`defaulted`); `culls`, sorted by `id`, each with `id` (a culled claim) and `into` (the claim it
was culled into); and `links`, sorted by `a`, `b`, every inferred link that survived the cull,
each with `a` and `b` (id-sorted, carrying no direction) and `harvest` (`unmarked`, `adjacent` or
`culled`). The declared pass writes it with every list empty."

`harvest`: `unmarked` is an unmarked-reference yes and `adjacent` an adjacency link, a link both
found recording `unmarked`; `culled` is a link a culled end's re-pointing onto its root produced,
a marked pair with a culled end included, which leaves the marked set and goes to attribution as an
inferred link. A re-pointed link equal to an untouched marked pair is dropped; one equal to an
untouched inferred link keeps that link's harvest.

The origin rule, SPEC §3: "An edge source → target was found with no mark where the unmarked
record answers (source, target) yes in that direction, or where the cull record's `links` hold its
pair either way round (§6). Of the build records beside `kb-root/` the sheet reads only the
unmarked record and the cull record's links, for that distinction; an absent record finds
nothing." SPEC
§10 applies it to a cut: "The origin is `inferred` where the build found the cut edge with no mark,
by §3's rule, else `cited`." kbase implements it once (`buildrecords.InferredLinks`) and calls it
from the sheet's edge provenance and from `demote-claim-edge`'s computed origin: a set of directed
pairs, every unmarked yes in the direction asked, every cull link both ways; membership is the
answer.

**kb_tools today.** Three record stems, no cull record, the sheet building the inferred set inline
from the unmarked record alone:

```
grep -n 'RECORD_STEMS' kb_tools/kb_load.py                 → kb_load.py:33 (three stems)
grep -n '_RECORD_STEMS_0_9_0' kb_tools/kb_migrate.py       → kb_migrate.py:34, frozen with 0.9.0
grep -rn 'kb-build-cull' kb_tools --include='*.py'         → (nothing)
grep -n 'UNMARKED_POINTS_LETTER' kb_tools/kb_pipeline.py   → kb_pipeline.py:451
grep -n 'inferred = (' kb_tools/claim_sheet.py             → claim_sheet.py:408
```

### 1.5 The shortlist: adjacency links, proximity slots, wildcard slots

**kbase.** SPEC §4: "Claims consecutive in one leaf's claim order are linked by rule, unasked
(adjacency links). The shortlist offers every source its proximity slots, its nearest targets
within its own paper, then its wildcard slots, its best targets anywhere by cosine less the
proximity picks; the slot counts are in ARCHITECTURE §12, and a proximity slot its paper cannot
fill stays empty. No pool holds a marked pair or an adjacency link. Each source's shortlist is its
own, so a pair both ends pick is asked both ways, and a yes in either direction makes one
undirected link." ARCHITECTURE §12: `shortlistProximityK` is 3, `shortlistWildcardK` is 2. The
wildcard ranking is kb_tools' TF-IDF cosine, summed in Python's order.

The planner, `internal/claimgraph/unmarked.go` `planUnmarked`: "Per source — every node but a
minted equation — its pool is every other node less the excluded links and every equation the
source states. Its proximity slots take the pool's nearest targets within its paper: nearest
locality first, then fewest places apart in the sequence of every node by position and id, a tie to
the earlier. Its wildcard slots take the pool's best by cosine, less the proximity picks, so a
target in another paper is reached there alone. A slot left unfilled stays empty." Locality is
same document, then same directory, then same paper. kb_tools' own-equation exclusion stays.

Reading order, `internal/claimgraph/order.go`: "`readingOrder` is every document reachable from the
entry point, in preorder over each document's children as it lists them"; a claim's position "is
where a claim sits in reading order: its document's index in `readingOrder`, and its line in that
document", where "a block or prose claim [sits] at its body's first line, an equation node at its
fence's first line, and a claim neither reaches last in its document". Items 5 through 8 share
this one definition.

**kb_tools today.** `kb_claimgraph/shortlist.py` `K = 5` and `top_k`; `kb_claimgraph/unmarked.py`
`plan` takes the best five by cosine over the pool less the source's own equations, as ordered
pairs, with no position input; no adjacency link; no proximity slot; no reading-order function:

```
grep -n '^K = ' kb_tools/kb_claimgraph/shortlist.py                     → shortlist.py:26
grep -n 'shortlist.top_k(pools, shortlist.K)' kb_tools/kb_claimgraph/unmarked.py → unmarked.py:73
grep -rni 'reading order' kb_tools --include='*.py'          → kb_readme.py only, unrelated
```

### 1.6 The stage `claims-culled`

**kbase.** Walked between `references-found` and `depends-attributed`. Its row spends its own
inference and is dropped under `--no-inference`: the stage is still walked, no ask is made, and the
cull record stands as the declared pass wrote it. SPEC §5, "Co-linearity cull":

> The stage removes prose claims that state no step a linked claim does not. Its candidates are the
> links — every marked pair, every pair the unmarked-reference ask answered yes in either
> direction, and every adjacency link (§4), each unordered — with at least one end a prose claim.
> Each candidate gets one co-linearity ask, shown both claims in reading order and offered three
> answers: the second adds nothing to the first, the first adds nothing to the second, or each is a
> step of its own. An answer naming a claim as adding nothing — answered, or answered after a
> re-ask — culls it into the other, except that a block claim or an equation node is never culled:
> where the answer names one, the prose claim of the pair is culled into it instead. One whose ask
> yields no readable answer after the re-ask is recorded `defaulted` and both claims keep. A claim
> several answers cull goes into the earliest of their partners in reading order; following those
> to a claim culled into nothing gives its root. A claim whose root is not the claim it was culled
> into is asked once more against its root and kept unless that answer names it as adding nothing;
> no claim is asked a third time. A culled claim is removed — its outgoing and inbound edges, then
> its register entry, its marker and its id in every leaf's `claims`, a leaf whose only claim it was
> restated no-claim with a fixed reason — and no edge is added. The stage asks no direction: every
> inferred link that survives, one with a culled end re-pointed onto that end's root, goes
> undirected to the cull record (§6) for dependency attribution. Under `--no-inference` the stage
> is still walked with its row dropped: no ask is made and the cull record stands as the declared
> pass wrote it.

The asks are grouped by the earlier claim in reading order for the first pass and by root for the
confirming pass. A cull removes a claim through, in order, `drop-claim-edges`, `drop-inbound-edges`
and `drop-claim-node`; a leaf hosting only the culled claim is first restated no-claim through
`set-frontmatter` with the fixed reason: "This document's claim states nothing that another claim
in the KB does not already state; that claim stands for both in the claim graph." The record is
written once, after the issue.

**kb_tools today.** No such stage; the stage table runs `references-found` straight into
`depends-attributed`, a test holds that adjacency, and an invariant says the node set is fixed
before any edge is drawn:

```
grep -n '"references-found",\|"depends-attributed",' kb_tools/kb_pipeline.py → 1218, 1225
grep -n 'ids.index("depends-attributed") - 1' kb_tools/tests/test_kb_pipeline.py → :503
grep -n 'the node set is fixed' kb_tools/kb_pipeline.py                        → :1139
grep -n 'claimgraph_invocation=' kb_tools/kb_pipeline.py     → the per-stage invocations
```

### 1.7 Attribution over every surviving link; one cycle cut

**kbase.** SPEC §5, "Dependency attribution":

> A captured link carries no direction; only this stage's ask gives it one, or rules it a mention.
> The candidates are every marked pair, directed as the text marks it, and every link of the cull
> record (§6) whose two claims no marked pair joins either way round, directed from its later claim
> in reading order to its earlier, an equation node always the target. Each candidate is asked once,
> offered *supported by*, *in support of* and *mention*, less *in support of* where containment
> directed the pair or its target is an equation node. *Supported by* writes a `depends` edge from
> source to target, *in support of* one from target to source, and *mention* a `references` edge. A
> candidate whose ask yields no readable answer after the re-ask, and every candidate under
> `--no-inference`, takes its draft: *supported by* where containment directed the pair, *mention*
> otherwise. The stage writes every edge its answers make, cycles included; last, every `depends`
> edge lying on a cycle is demoted (§10), before the stage's refresh and verify.

SPEC §10: "The cuts are the dependency-attribution stage's ring row — every `depends` edge on a
cycle once attribution has written its edges. The origin is `inferred` where the build found the
cut edge with no mark, by §3's rule, else `cited`." Nothing else cuts: no stage drafts a ring pair
*mention* for containment, and no stage cuts before attribution has written its edges. The
attribution row is `spendsInferenceInPart`: under `--no-inference` its asks are skipped and the
rest of the row runs. The cuts reach the register through `demote-claim-edge`.

**kb_tools today.** The candidates are the ordered pairs the unmarked ask answered yes; the cuts
are computed in memory over the classified edges and landed through `add-build-edges`' `demoted`
list:

```
grep -n 'def cuts' kb_tools/kb_claimgraph/classify.py          → classify.py:158
grep -n 'read_unmarked' kb_tools/kb_claimgraph/depends.py      → depends.py:197
grep -n 'def write_edges' kb_tools/kb_claimgraph/write.py   → write.py:415 (demoted parameter)
```

### 1.8 A reference's passage stops at the body's first line

**kbase.** `internal/claimgraph/attribute.go` `referenceLine`: "The passage never reaches above
the body's first line, and a reference above it has none." It takes the page's lines with
`pageBody` (`classify.go`), "pageLines with the index of the first line of the body, below the
frontmatter and the up-link line", returns `""` where `line < first`, and walks back to the
paragraph's start no further than `first`. `first` is `label.go` `bodyStart`. A paragraph that runs
straight on from the up-link line now gets its own lines only; a reference on the up-link or
frontmatter line gets no passage. The passages fill the classify state's `@!dyn.reference-lines!@`.

**kb_tools today.** `kb_claimgraph/attribute.py` `_reference_line` walks back to line 0, with no
lower bound; the body start already exists as `kb_claimgraph/label.py` `_body_start`, mirroring
`bodyStart`:

```
grep -n 'def _reference_line' kb_tools/kb_claimgraph/attribute.py   → attribute.py:717
grep -n 'while start > 0' kb_tools/kb_claimgraph/attribute.py       → attribute.py:766
grep -n '^def _body_start' kb_tools/kb_claimgraph/label.py          → label.py:159
```

## 2. The work, in order

Each item lands as its own commit with its tests and the document edits it invalidates;
`just test-changed` is the gate on each and `just sweep-python` runs at each checkpoint, as
`kb_tools/CONVENTIONS.md` has it. Coding goes to `python-coder` with THESIS, SPEC, ARCHITECTURE and
CONVENTIONS of `kb_tools/`; model-facing text — the question files, the state templates — is the
`prompt-engineer`'s to transcribe, and the prompt-engineer reviews each item's composed result as
served before first use: the composition (format, composer, no system message) is new even where
the text is kbase's. Stdlib only.

1. **The decision transport and its environment.** `kb_tools/inference/liaison_tools.py` gains
   `call_decision(state, question, *, model, timeout_seconds, capture)` beside `call_chat`: one
   JSON `POST` to `API_BASE_URL` + `/systemone` through `urllib`, bearer key as `call_chat`
   sends it, no streaming, the wire shape of §1.1, one attempt. It returns an `Outcome` that
   separates the retry class (transport failure, 429, 5xx) from a refusal (any other 4xx, or an
   answer under a key that was not asked) from success; retry is the caller's, in `ask.py`'s
   existing loop (`TRANSPORT_ATTEMPTS`), re-issuing on the retry class only. The environment gains
   `DECISION_MODEL`, the model the letter asks name; `MODEL` stays the overview call's.
   `check_environment(*, decision: bool)` requires `DECISION_MODEL` when `decision` is true:
   `kb_claimgraph/__main__.py` (line 186) passes true; `kb_driver/run.py` `_require_server`
   passes whether any step left to walk is a letter-ask step, which `kb_driver/steps.py` marks
   beside `calls_a_model`; the opening refusal (exit 14) names the variable like the others. The
   capture: per attempt, the request's model and the state's SHA-256 (never the state), the
   response body verbatim, the measured time and outcome; its reader, `read_decision_capture`,
   fills `CaptureStats` with the measured time, `usage.input_tokens` and `output_tokens` in the
   prompt- and completion-token fields, cached tokens `None` and reasoning attempts 0. Tests: a
   stub HTTP server in-test; the three outcome classes; the unasked-key refusal; the environment
   refusals; the capture round trip.

2. **Questions, the composer and the reader.** Order: the prompt-engineer copies the four
   question files of the existing kinds (`paragraph`, `unmarked`, `classify-three`,
   `classify-two`; `colinear`'s is item 5's, its letter slots arriving there) byte for byte into
   `kb_driver/prompt-templates/questions/` and the three state templates of §1.2 over the three
   template files; then the coder: `kb_yaml` gains the literal
   block scalar (`|`, `|-`, `|+`; content by indentation; the writer unchanged) so the files parse
   as written, the one addition the dialect needs — if a later file needs more, a vendored parser
   replaces `kb_yaml` whole rather than widening it again (D1);
   `kb_driver/prompt_templates.py` loads a question as it loads a template, fills `@!letter-…!@`
   from `kb_claimgraph/ask.LETTER_SLOTS`, and refuses a question whose filled `criteria` keys are
   not the offered letters (`choice`) or `true`/`false` (`noul`); `ALTERNATIVE_SLOTS` loses
   `"correction"` and `"classify-options"`, `FRAGMENT_SLOTS` loses `reader-system`, and the
   fragments `classify-options-two`, `classify-options-three`, `letter-correction` and
   `reader-system` are deleted with `ask.CLASSIFY_OPTIONS_SLOT`, `LETTER_CORRECTION`,
   `READER_SYSTEM` and the `dyn.returned` slot; a letter ask has no system message.
   `letters.LetterQuestion` gains the attempt ordinal; `letters.py`'s `question(returned)` and
   `compose(returned)` lose `returned`; `ask._capture_path` names the file by the ask and the
   ordinal, since the re-ask's prompt digest equals the first's. `ask.py`'s production reader
   calls `inference.call_decision` with the composed state and the kind's question keyed by the
   item name and returns a `Reply` whose `confidence` is §1.1's mapping and `text` empty;
   `letters.decide` is already the argmax. `kb_driver/call.py` keeps the overview call on
   `call_chat`. The composed-prompt goldens are re-pinned to the state texts; the record shapes
   (`kb_pipeline.ClassifyOutcome`, the unmarked and node-pass records) do not change. Then the
   prompt-engineer reviews one composed request per kind as served. The documents this item makes
   false land with it: `kb_tools/CONVENTIONS.md`'s "A model call is
   `inference.liaison_tools.call_chat` and nothing else", `kb_tools/ARCHITECTURE.md`'s "every call
   is `inference.call_chat`", and the replay `[doc]` string in `kb-testing/justfile`
   (`replay-claimgraph-asks`', naming the env's `MODEL`), and the roles of `DECISION_MODEL` and
   `MODEL` (letter asks; overview call) in `kb_tools/SPEC.md`, `kb-testing/README.md` and the
   `kb-driver-fixture` `[doc]` string, which item 1 states only as a requirement. `check_environment(decision=True)` still requires
   `MODEL` after item 1; whether a run whose only model calls left are letter asks needs it is
   settled here by what the run will call. Done when a build against a stub server shows every
   letter ask on `/systemone` and the overview call on `/chat/completions` (the overview call is
   made at `overview-drafted`, after `references-found`, so the walk runs past it).

3. **The four write ops.** `kb_write/values.py` `OP_FIELDS` gains the four rows of §1.3;
   `kb_write/ops.py` gains the three public ops in `OPS` and `demote-claim-edge` in `BUILD_OPS`,
   with the semantics and refusals of §1.3, `origin` a required value; `kb_util.py` gains the
   three `OP_*` tokens, their place in the token tuple (the tuple ending `OP_RESOLVE_DEMOTED,`)
   and a subparser block each, shaped as `resolve-demoted`'s (`grep -n 'OP_RESOLVE_DEMOTED'
   kb_tools/kb_util.py` → :335 the token, :352 the tuple, :1877 the subparser); dispatch needs no
   edit, since
   `_handle_write_op` looks the op up in `write_ops.OPS`.
   The op surface test of §1.3 is the gate. `kb_tools/SPEC.md` "The Write API's Contract" gains
   the three public ops and its sentence at line 875 becomes "`resolve-demoted` is the one public
   op over a cut; the build's `demote-claim-edge` makes one"; `kb_tools/ARCHITECTURE.md` "The
   Write API" names the build-only pair. The `kb-maintainer` definition
   (`adjagent/definitions/kb_maintainer.py`) names the write ops it may use; whether it learns the
   three public ops is the prompt-engineer's item, dispatched with this one.

4. **The cull record and the origin rule.** `kb_load.py` gains `CULL_STEM = "kb-build-cull"` in
   `RECORD_STEMS`; `kb_migrate._RECORD_STEMS_0_9_0` is frozen with that format and does not
   change. `kb_pipeline.py` gains `CullRecord` with the shape of §1.4, read and written like the
   three records, and the declared pass (`claims-declared`) writes it with every list empty.
   `kb_pipeline.inferred_links(unmarked, cull) -> Callable[[str, str], bool]` is the origin rule,
   the yes letter `kb_pipeline.UNMARKED_POINTS_LETTER`; `claim_sheet.py`'s inline set (line 408)
   is replaced by a call, and item 8's cut calls it. Tests: the record round-trips through
   `kb_yaml`; an absent record finds nothing; a cull link counts both ways and an unmarked yes
   one way.

5. **The co-linearity ask kind.** Order: the prompt-engineer copies `colinear.tmpl.md` and
   `questions/colinear.question.yaml` of §1.2 byte for byte from kbase's
   `internal/asks/prompt-templates/` — both files end without a trailing newline, which the code blocks
   above cannot show; the coder adds
   `ask.ColinearLetter` with `A`/`B`/`C`, `LETTER_SLOTS` entries `letter-second-adds-nothing`,
   `letter-first-adds-nothing`, `letter-distinct`, a `ColinearItem` (key, first and second claim
   with their statements, in reading order) and `colinear_asks`, with a golden; provenance is
   the ARCHITECTURE sentence of D3; the prompt-engineer reviews one composed request as served.

6. **The shortlist and adjacency links.** `kb_claimgraph/order.py` gives `reading_order(tree)`
   and `claim_positions(tree, graph, inventory)` by §1.5's definition, the one source items 5–8
   share. `kb_claimgraph/shortlist.py`: `PROXIMITY_K = 3`, `WILDCARD_K = 2` replace `K = 5`;
   `unmarked.plan` takes positions, offers each source its proximity slots by locality then by
   places apart with a tie to the earlier, an unfillable slot staying empty, then its wildcard
   slots by cosine less the proximity picks; the own-equation exclusion stays; a marked pair or
   an adjacency link is in no pool; adjacency links between consecutive non-equation claims of a
   leaf are made by rule and handed on with the yeses. The unmarked record's shape is unchanged.
   `kb_tools/ROADMAP.md`'s ask-count line ("197·K asks") is re-derived.

7. **The stage `claims-culled`.** `kb_pipeline.py`'s stage table gains the row between
   `references-found` and `depends-attributed`, `work_is_inference=True` with the stage still
   walked under `--no-inference`, its `claimgraph_invocation` and coverage check (the record
   present, its `culls` all absent from the register); `kb_claimgraph/__main__.py` gains the
   entry; `kb_driver/steps.py` gains its steps; `tests/test_kb_pipeline.py:503` asserts the new
   adjacency. `kb_claimgraph/cull.py` holds the pure planner (targets, roots, final culls over
   §1.6's rules) — including the letter-to-verdict mapping by id of §1.2, which kbase does inline
   in `cull.go`'s ask loop and item 5 therefore left here, with the `p<pass>-<id>` group names and
   the reading-order grouping — the issue through the three drop ops with the no-claim restatement and its fixed
   reason, and the record written once after the issue. The invariant "the node set is fixed
   before any edge is drawn over it" (`kb_pipeline.py:1139`, its test at line 385) is restated in
   code comment, test and `kb_tools/ARCHITECTURE.md`: the node set is fixed at `claims-culled`'s
   boundary, before attribution draws its edges; the cull removes nodes with their edges through
   the drop ops, and `kb_index_lib.scan_authored_ids`' keys change across it. Tests: planner
   cases for the block-claim exception, the earliest-partner rule, the root chase and the
   third-ask bar; an issue over an in-test KB.

8. **Attribution over cull links; the single cut.** `kb_claimgraph/attribute.py`'s candidates
   become every marked pair as the text marks it and every cull-record link no marked pair joins,
   directed later to earlier by `order.claim_positions` with an equation node always the target,
   the question `classify-two` where containment directed the pair or the target is an equation
   node; the ring draft *mention* for a containment-directed pair goes; after every edge is
   written through `add-build-edges`, every `depends` edge on a cycle is demoted through
   `demote-claim-edge` with its origin from `kb_pipeline.inferred_links`. Retired in the same
   change: `classify.cuts`' ring parameter and the in-memory cut, `Attribution.demoted`,
   `write.write_edges`' `demoted` parameter. `add-build-edges` keeps its `demoted` field as op
   vocabulary shared with kbase, and no build caller passes it. `kb_tools/SPEC.md`'s "demoted"
   bullet, which says a cut's origin reads the unmarked record alone, becomes the origin rule.

9. **The passage lower bound.** `kb_claimgraph/attribute.py` `_reference_line` takes the body
   start as `label.py`'s `_body_start` computes it, over the same marker-stripped, unquoted text
   (`_body_start` is private to `label.py` and nothing outside imports it today: `grep -rn
   '_body_start' kb_tools --include='*.py'` → label.py only; making it shared is the coder's call
   under `kb_tools/CONVENTIONS.md`), returns `""` for a
   line above it, and walks back no further than it (§1.8). Tests mirror kbase's
   `attribute_test.go` additions: a paragraph running on from the up-link line yields its own lines
   only; a reference on the up-link or frontmatter line yields no passage.

10. **The documents.** `kb_tools/SPEC.md` "The Driver's Contract": the chat-completions sentence
   becomes two, the overview call on chat completions and the letter asks on `systemone`, with
   `DECISION_MODEL` beside `MODEL`; "Claim-Graph Nodes and Edges" gains the origin rule and the
   cull record among the build records, no further. `kb_tools/ARCHITECTURE.md`: the Module
   Inventory row `inference/` (the environment, `check_environment`, the two captures and their
   readers), the stage table and its coverage checks, the records, the write API, the restated
   invariant, and the provenance sentence of D3. `kb_tools/CONVENTIONS.md`: a question file or a
   kbase-origin template is kbase's bytes, changed only by adopting kbase's change. Each lands
   with the item that invalidates it; this entry is the check that none was missed.

## 3. Decisions, made

- **D1, the question file format: kbase's YAML, byte for byte.** YAML is the KB's one metadata
  format by choice, and TOML was passed over for it. `kb_tools/kb_yaml.py` reads "the subset kbase
  writes (block mappings and lists, plain and double-quoted scalars, flow lists of scalars, `[]`
  and `{}`)", skips whole-line comments and reads double-quoted keys; the one construct in the
  question files it refuses is the literal block scalar (`grep -n '"|": "a block scalar'
  kb_tools/kb_yaml.py → kb_yaml.py:594`). Item 2 adds it. Should a later kbase file need more of
  YAML than that, kb_tools vendors a parser and retires `kb_yaml`'s reader whole; the partial
  parser is not widened a second time.
- **D3, where provenance lives: one sentence in `kb_tools/ARCHITECTURE.md` "The Driver"**,
  naming the two kbase-origin files and the seven kbase-authored ones at `5aab244` (kbase
  `internal/asks/provenance.yaml`: three state templates, four question files). A template has
  no comment syntax, so nothing goes in the files; a manifest waits for a second consumer.

## 4. Proof

Per item, its tests and `just test-changed` green. For D1: `kb_yaml.parse` over each of the five
question files yields `instructions` and every `criteria` value as kbase's text, the `|-` chomp
applied, and `kb_yaml`'s writer is unchanged. For the whole: a `--no-inference` build of the test
fixture walks eleven stages, the cull record is written empty at `claims-declared` and committed
at every boundary, and the sheet's provenance reads it; a build against a stub decision server
shows every letter ask as one `/systemone` request
with one question under the item's key and no system message, and the overview call as the one
chat request.

## Out of scope

The stage `claims-vetted`, its record `kb-build-vetting.yaml`, the ask kind `vetting` with its two
files and letters, and the elision bridges: kbase retired them and kb_tools does not adopt them.
The hit list. kbase's `providers.toml`/`config.toml`, its MCP server, its YAML values transport,
its exit-code table and its query paging: permanent divergences in kbase SPEC §4. A `score`
question type. No KB-contract change beyond what kbase SPEC §3, §6 and §10 state, as quoted in
§1.4 and §1.7.
