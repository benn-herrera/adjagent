# CLAIM_GRAPH_LETTER_ASKS_DESIGN.md — every claim-graph ask is one decision, one letter, thinking off

**Specification for the node pass (`ACTIVE_PLAN.md` row C2's ask) and for classification (row
C6).** §1 holds the letter-ask decisions and the node pass's; §6 holds classification's own. Paths
are relative to the repository root; the stage is `kb_tools/kb_claimgraph/`. Seats: **PC**
python-coder, **PE** prompt-engineer. `ACTIVE_PLAN.md` standing rules 1–8 apply to every row and
are not restated.

**The direction this designs within:** every model ask in the claim graph becomes one decision,
answered with exactly one letter from a closed set the build offers, with thinking off. The shared
context goes first and the one question last, so asks that share context reuse the server's prefix
cache.

**Why (measured):** a ModernCorp build takes about 5 hours, and the claim-graph asks are nearly all
of it — 245 asks at a mean of 73 s (`ACTIVE_PLAN.md` C8). Each ask is a compound document task, and
the time is almost all reasoning: the capture
`kb-testing/test-data/transient/ModernCorp/.claude-temp/claimgraph/asks/000-…section-4.md.capture.jsonl`
line 487 reports `output_tokens: 4792` and `duration_api_ms: 81924` for a node-pass answer of a few
hundred characters, and line 485 carries `"type":"thinking"` blocks. A compound answer can also be
partly wrong and stop the stage. One paragraph left without a verdict after the re-ask failed a
5-hour build.

---

## 1. Decisions

### L1. Two ask kinds, one shape

| Kind | Unit (one ask) | Group (shared prefix) | Letters offered | Default if no valid letter |
|---|---|---|---|---|
| **paragraph** (node pass, `claims-discovered`) | one paragraph of readable prose | its leaf | `A` states a result · `B` does not | **unjudged** (L4) |
| **classify** (`depends-attributed`) | one edge candidate | its source claim | `A` supported by · `B` in support of · `C` mention — only the subset the candidate's class allows (§6 K2) | the candidate's **draft** (§6 K3) |

- **The letter-to-meaning table is fixed and has one definition per kind** (a `StrEnum` in code, the
  letters handed to templates as composer constants). Withholding a meaning removes its letter; it
  never relabels the others. A two-option classify question offers `A` or `C`, never `A` or `B`.
  This is what makes a renaming bug impossible: if subsets were relabelled, `B` would mean *mention*
  in one ask and *in support of* in the next, and the edge would be written backwards.
- **The answer is strict.** After stripping whitespace, the reply must be exactly one character, and
  that character must be one of the offered letters. Anything else counts as no valid letter
  (`kb_tools/CONVENTIONS.md`: "that format is ours, and its parser stays strict").
- **One re-ask of that single question, then the default.** The re-ask repeats the prompt with a
  correction placed after the question. The correction carries a fact computed from the first reply:
  what came back, truncated. The re-ask therefore shares the first ask's entire cached prefix. A
  default is recorded as defaulted, and the stage carries on. **Only a call that never completes
  stops the stage** (`ask.AskError`, after `TRANSPORT_ATTEMPTS`), exactly as today: no answer
  arrived, the cause is systemic, and defaulting every remaining item would hide a dead model behind
  what looks like a finished run.
- `report.AnswerFormatError` is deleted. With the letter parse, an unreadable answer is a recorded
  outcome rather than a raised stop, and nothing else raises that error (`kb_tools/AGENTS.md`, "Name
  the producer").

### L2. Which paragraphs the node pass asks — C2's rule, reused

The **readable region** is unchanged: `prose.excluded_lines`. The paragraphs are those of
`label.render` over that region (`prose.readable`), and **obligated** is unchanged:
`prose.obligated`.

- **Every obligated paragraph is asked.** That keeps C2's guarantee that every one gets a verdict.
- **Every other readable paragraph is asked if it holds at least one sentence that could open a
  claim.** The test is today's `identify._opens_a_claim`: at least `MIN_OPENING_WORDS` canonical
  words, and not inside a maths fence. This drops paragraphs that are pure markup, such as
  `<div class="center">` (S1/S3 in `…/asks/082-…the-kramers-contrast-the-punchline.md.prompt.md`),
  and two-word labels.
- **Not narrowed to obligated paragraphs only.** THESIS gap 1 covers any claim built in prose, and
  C2's node pass mints "a claim node per result that prose states" (`kb_tools/ARCHITECTURE.md`, The
  Claim Graph). Asking only the paragraphs that hold a reference would lose the prose claims the
  node pass exists to find. Those claims are most of C2's 509 prose claims, which were recorded as
  sentence-level records outside the obligated paragraphs.
- **Granularity becomes the paragraph.** A *yes* mints one claim whose span is its whole paragraph,
  the rule C2 already applies to verdicts. The sentence-start records — quote, label, extent, the
  per-claim re-ask — go away. A paragraph that states two results becomes one claim. This follows
  from the settled direction (one ask per paragraph), and it lowers the prose-claim count against
  C2. The node pass reports that count, and §8's C9 baseline reads it.

### L3. Claim titles are derived mechanically, not generated

A title's consumers need a **stable, unique, one-line label in the author's words**:

1. The register heading a person reads.
2. `write.land_leaf`'s resume key: a planned claim whose title the leaf's register already carries
   takes that id rather than a second one. A title regenerated after a crash could differ and mint a
   duplicate, so the key must be reproducible.
3. The claim line of a classify ask. The classify ask also carries the statement text itself (§4),
   so the title only labels.
4. Sheet box labels and `kb_cmd show`.
5. The C9 TF-IDF match over title plus statement (`kb-testing/tools/compare-to-pristine.py` line
   372).

None of them needs a summary. A generated title would also be the one model-typed string left
reaching the KB, would cost an open-ended ask per minted claim, and would bring back free-text
checks (one line, unique). So:

**Rule:** the title is the paragraph's first sentence that passes `_opens_a_claim`. Point-7 anchors
are reduced to their link text and point-10 citation spans to their rendered text: extend
`inventory._readable`, which already does the citation half, and do not add a second reduction. The
result is collapsed to one line and cut at the last word boundary within `TITLE_MAX_CHARS`, with `…`
where cut. If it equals a title the leaf already carries (block or earlier prose), append ` (¶<k>)`,
where `k` is the paragraph's 1-based position among the leaf's readable paragraphs. The rule is
deterministic, unique per leaf by construction, and bytes the author wrote. `TITLE_MAX_CHARS` is the
coder's choice and is stated once.

### L4. The defaults, argued per `kb_tools/AGENTS.md`

- **Paragraph → unjudged.** The verdict is recorded as `defaulted`, with a cause. `prose.standing`
  reads it as `UNJUDGED`, so its references fall to the prose fallback (source = every claim the
  document hosts) and still count toward equation minting. The alternatives are both worse:
  - *not-a-claim* drops every reference in the paragraph. That is a relationship declined silently,
    which `kb_tools/AGENTS.md` names as the wrong-cautious answer.
  - *claim* mints a node nobody judged.

  *Unjudged* is the state the graph already gives a paragraph no reading reached. A malformed letter
  is exactly that epistemic state, so this adds no new state for any consumer.
- **A yes-paragraph the write path cannot place** — no unique slice even across the whole paragraph
  (`identify._place`) — is also `defaulted`, cause `unplaceable`, and is named on a report line.
  Today it stops the stage. The constraint is mechanical, but it costs one paragraph and should not
  cost the build. Making a failure survivable is the act `kb_tools/AGENTS.md` leaves open.
- **Candidate → its draft** (§6 K3): `supported-by` where containment settles the pair, `mention`
  elsewhere. This reproduces `--no-inference`'s answer, and mention is the majority answer for an
  open pair (K3's measurement).
- A `--no-inference` build is unchanged in kind. `claims-discovered` is refused, and
  `depends-attributed` writes every candidate's draft.

### L5. Prompt order, grouping and concurrency — so the cache is actually hit

**Order inside every prompt:**

1. The system prompt: the seat body plus `no-tools`. It is constant for the whole build.
2. The kind's constant instructions, including what each letter means.
3. The group's shared context.
4. **Last**, the question section, holding every per-item slot.
5. On a re-ask only, the correction after the question.

Every byte before the question section is identical across one group's asks. The question section
opens with a constant line, so the tokenisation at the boundary is identical too.

**This is a machine guarantee, so a test carries it.** A unit test over each dispatched letter
template asserts that every per-item slot (the kind's declared `ITEM_SLOTS`) appears after every
group slot in the template source, using `prompt_templates.slots_of`. A second test renders two asks
of one group and asserts the two prompts differ only after the question section's opening line.
Prose cannot keep this true; the test can.

**Sequencing:**

- **Node pass:** leaves in sorted order, as today.
- **Classify:** sources in ascending id (§6 K4).
- **Within a group:** the **first ask is issued alone** so the server prefills and caches the
  prefix. Then the rest of the group runs with `W` asks in flight.
- Groups run one after another. A leaf lands (`land_leaf`) and its record entry is written after its
  whole group is answered.
- Results are keyed by item and applied in item order, so concurrency never changes what is written
  or the record's order.
- `W` is read once from the reader configuration (L6), defaults to 1, and is set from P4.
  Cross-group pipelining is not specified; add it only if P4 shows idle server time between groups.

**Cache reuse is reported, not assumed.** Each stage's report carries the prompt tokens the server
reported as cached, against the total, for the second and later asks of each group. On the chat
route this is `usage.prompt_tokens_details.cached_tokens`, where the endpoint returns it; on the CLI
route it is `usage.cache_read_input_tokens` (the capture above shows both
`cache_creation_input_tokens` and `cache_read_input_tokens` reported). A route that silently defeats
caching shows up as a number, not as a mystery.

### L6. Thinking off: the controls on each route, and the route change

**The build's route today** is `claude -p` → `ANTHROPIC_BASE_URL=http://reaper.local:4000`
(`kb-testing/test-data/transient/kb-driver-local-inference-config-qwen3.env`). Three findings, each
from a file:

1. **The CLI's own control is a setting, and it is not proven to reach the model's chat template.**
   Claude Code's thinking is governed by its `alwaysThinkingEnabled` setting and the
   `MAX_THINKING_TOKENS` environment variable. Both stop the CLI requesting thinking. Neither sets
   Qwen's `enable_thinking` template flag, which the server applies unless the Anthropic-compatible
   endpoint maps the request onto it. Whether it does is not in any file here (probe P3).
2. **A SessionStart hook writes a per-call timestamp into every claim-graph call.** Capture line 2
   shows `hook_response` with
   `"additionalContext": "lastSessionEnd: … referenceTime: [Fri Oct  2 16:14:28 PDT 2026]"`. That
   context enters the conversation ahead of the prompt, so it changes on every call and defeats
   prefix reuse past the system prompt. `seat.READER_SETTINGS` disables memory but not hooks. **Fix:
   add `"disableAllHooks": true` to `READER_SETTINGS`**, beside `"alwaysThinkingEnabled": false`.
   (`--bare` would also skip hooks, but it is opt-in for its keychain cost.)
3. **The same server exposes an OpenAI-compatible route:**
   `API_BASE_URL=http://reaper.local:4000/v1` in
   `kb-testing/test-data/transient/reaper-qwen3.8-27B.env`. On that route the thinking control is
   explicit: `chat_template_kwargs.enable_thinking` (`liaison_tools/post-openai.py` lines 458–459;
   `liaison_tools/SPEC.md` line 29). The route also carries the controls a letter ask needs and the
   CLI cannot express: `temperature: 0`, so the reply is the argmax and equivalent to a classifier's
   top label; `max_tokens` of a handful; no process spawn per ask; and, later, the classifier read
   (L8).

**Decision: the build route for local inference becomes a direct OpenAI-compatible POST, added to
`kb_tools/inference/` as a second transport** (stdlib `urllib`; no new stdlib exception). It sends:

- `model`
- `messages: [system, user]`
- `temperature: 0`
- `max_tokens: LETTER_MAX_TOKENS` (a small constant set from P1)
- `stream: false`
- `chat_template_kwargs: {enable_thinking: false}`

It returns the reply text, an `Outcome`, and the usage block. One classification of how a call ended
still lives in `inference/`: HTTP 4xx is not retryable (a configuration fault, the class
`CLI_REJECTION` names); 5xx, connection errors and timeouts are retryable.

**The CLI route stays** as the harness-portable route — for a cloud model, and for every test that
substitutes the invoker — with the two settings above. Which route a run uses is read at the point
of use (`kb_claimgraph/__main__.py`) from the environment the driver inherits. The names below are
single-sourced as constants in `inference/`:

- `KB_READER_BASE_URL` — its presence selects the chat route.
- `KB_READER_MODEL`
- `KB_READER_API_KEY_FILE` — optional.
- `KB_READER_CONCURRENCY` — `W`.

**This is not a copy of `liaison_tools/post-openai.py`, deliberately.** `kb_tools` installs into a
consumer stdlib-only and alone (`kb_tools/SPEC.md`, Corpus Invariants), and `liaison_tools` does not
ship with it. The two POSTs share a wire format, not a package. The kb_tools one carries no
streaming, no tool calls and no usage file.

### L7. Records, so a stop never discards answered asks

- **Node-pass record** (`kb_pipeline.NODE_PASS_RELPATH`), changed as follows:
  - `Judgement` gains `defaulted`, with a `cause` from the closed set `{no-letter, unplaceable}`.
  - Verdicts are recorded for **every asked paragraph**, not only obligated ones. The record is the
    build's statement of what was read.
  - `LeafEntry.reason` is deleted. A read leaf that mints nothing keeps the frontmatter reason it
    already carries (L9).
  - `LeafOutcome.UNANCHORED` is deleted, together with the `stage-C-unanchored` line: nothing can
    fail to anchor any more.
  - Granularity stays per leaf (`planned` → `landed`). A stop mid-leaf costs at most one leaf's
    worth of one-token asks.
- **Classification record**, new: `kb_pipeline.CLASSIFICATION_RELPATH` =
  `kb-build-classification.json` at the repo root. It follows the node-pass record's pattern and
  placement, and its reader and writer are `kb_pipeline`'s for the same import-direction reason.
  - Per candidate, keyed by `(source, target)`: the offered letters, the letter or null, the outcome
    (`answered` / `re-asked` / `defaulted` / `drafted`), and `confidence` where a reader supplied
    one (L8).
  - It is written atomically after each source group. A resume asks only candidates it does not
    hold. Nothing produces a recorded pair that is no longer a candidate, because the node set is
    fixed at `equations-minted`. So no code checks for that case.
  - It is kept at the build's end, swept into the boundary commit by `_record`'s `git add -A`, as
    the node-pass record already is.
  - It is part of classification, not separable from it. Without it a stop discards every classify
    ask already answered, which breaks `kb_tools/SPEC.md`'s Driver's Contract ("Expensive work
    that succeeded is never discarded") at thousands of asks on the arXiv corpus (§2).

### L8. The classifier seam

The seam lives in `kb_claimgraph/letters.py` (new):

```
LetterQuestion(kind, group, item, prompt, offered: tuple[str, ...])
Reply(text: str, confidence: Mapping[str, float] | None)
class LetterReader(Protocol):
    def __call__(self, question: LetterQuestion) -> Reply: ...   # raises AskError on a call that never completed
```

- **The stage owns every decision. The reader owns only the call.** `letters.decide(reply, offered)`
  works as follows:
  - Where `confidence` is present, the letter is the argmax over the *offered* letters.
  - Otherwise, it is the strict parse (L1).
  - The re-ask, the default and the record are the stage's.
- Two generative readers ship: the CLI route and the chat route. Both return `confidence=None`.
- **What makes a "System One" classifier read (oMLX `choice` structured read, in review upstream) a
  drop-in:**
  1. The prompt and offered letters are computed before any reader exists. A `choice` reader sends
     the same prompt with `offered` as the choice list, and returns the per-label probabilities as
     `confidence`.
  2. Nothing downstream reads anything but one letter and an optional distribution.
  3. Cost per item is already the unit of design, so nothing about the stages changes.
- **Not built:** no `choice` request, no oMLX-specific code, no configuration for one.
- **How confidence could feed best-odds defaults later** (`kb_tools/ROADMAP.md` entry, §5):
  - A classify answer whose top-label margin is below a threshold falls to the draft.
  - A paragraph *yes* below a threshold falls to unjudged.
  - Before any threshold is chosen, the recorded confidences give the calibration evidence.

  Recording the distribution costs one optional field now. Acting on it is deferred until there is
  data.

### L9. What leaves the KB's metadata

- The model-authored no-claim sentence goes. A leaf hosting no claim block whose paragraphs mint
  nothing keeps `assemble.BLOCKLESS_REASON`, which the declared pass already wrote, and `land_leaf`
  writes no frontmatter change for it. That reason "says only that it carries none"
  (`kb_tools/SPEC.md`, Leaf Bodies Are Derived). Whether the leaf was read is build record, never KB
  metadata — the same paragraph of the SPEC. The SPEC sentence giving the reason to inference
  changes (§3).
- `NOTHING_FURTHER`, the `may_decline` distinction and `SUBSTITUTED_NO_CLAIM_REASON` go with it.

---

## 2. Ask counts and the latency model

### Counts — how each figure was produced, so a coder can re-run it

| Corpus | Stage | Asks (first asks; re-asks extra) | Command and result |
|---|---|---|---|
| ModernCorp | node pass | **≤ 597** (obligated: 123) | `Glob kb-testing/test-data/transient/ModernCorp/.claude-temp/claimgraph/asks/*.md.prompt.md` → 87 leaf prompts (the C2-era node pass; `086`/`087` are one leaf asked twice). `Grep` multiline `\n\nS[0-9]+: ` count over them → **597** paragraph starts. Multiline `\n[^S\n][^\n]*\nS[0-9]+: ` → **0**, so every labelled paragraph begins after a blank line and 597 is the paragraph count. `Grep ^S[0-9]+: ` → 2139 sentences. Upper bound: it includes markup-only paragraphs (L2's filter drops them) and the duplicate leaf. Obligated = 123 (`ACTIVE_PLAN.md` C2). |
| ModernCorp | classify | **≈ 180–260** over ≈ 70–150 sources | `Glob kb-testing/test-data/transient/ModernCorp/.claude-temp/claimgraph/asks/*-clm-*.prompt.md` → 75 files: 73 sources plus two re-asks (`073-clm-c3w1ps` repeats `023`, `074-clm-culzi7` repeats `027`). `Grep '^- \`clm-' --count` over those 75 → 338 lines; less one claim line per file, 263 candidate lines; less the two re-asks' 6 + 4, **253 candidates over 73 sources** (C8 run, before C4's filter). C4 removed 22 % of candidates across 54 roots (2238 → 1741). Add the 6 proof-directed pairs (C4 row) and 0 hand-named (C5 row). Exact figure: M0. |
| arXiv 50 + ModernCorp fixtures (54 roots) | classify | **≈ 2733 +** | C4 row: 1741 open candidates + 992 settled `depends` (each now a proof-directed candidate, §6 K2), over `--no-inference` builds. Prose claims from a node pass add sources and candidates. Exact figure: M0. |
| arXiv | node pass | **not measured** | M0 counts readable paragraphs, obligated paragraphs and paragraphs passing the opener filter per kb-root. |

### Per-ask latency model (each assumption is a probe)

```
T_warm  = t_call + tail_tokens / R_prefill + n_out · t_decode           (prefix cached)
T_first = t_call + (uncached_prefix + tail_tokens) / R_prefill + n_out · t_decode
T_stage = Σ_groups [ T_first + (n_group − 1) · T_warm / W_eff ]
```

- `t_call` is ≈ 0.05 s on the chat route. On the CLI route it is the process start plus Claude
  Code's own request handling (**P5**).
- `R_prefill` and the cache hit come from **P2**. `W_eff` (throughput gain at `W` in flight) comes
  from **P4**.
- `n_out` = 1 letter plus whatever the template's end-of-turn costs (**P1**).

**Worked figure (chat route, W = 1, assumed R_prefill = 1000 tok/s).** For ModernCorp this gives **≈
12 minutes of claim-graph inference against ≈ 5 hours today.**

| Stage | Assumed shape | Arithmetic | Time |
|---|---|---|---|
| Node pass | prefix ≈ 3K new tokens per leaf; tail ≈ 250 tokens (`T_warm` ≈ 0.3 s) | 87 × 3.3 s + 510 × 0.3 s | ≈ 7.4 min |
| Classify | ≈ 150 source groups at ≈ 1.5 s first ask | plus ≈ 100 warm asks | ≈ 4.3 min |

Two comparisons:

- **Without cache reuse**, every ask pays a full prefill of 3–8K tokens. ≈ 850 × 5 s ≈ 70 min, so
  caching is worth roughly 6× on top of thinking-off.
- **The CLI route** adds `t_call` × 850. At P5's figure that term decides whether the CLI route is
  viable for local builds at all.

---

## 3. Contract-document and plan changes (land with the rows named)

**`kb_tools/SPEC.md`**

- *Leaf Bodies Are Derived*, "What is said about a leaf is inference's still: which registered
  claims it establishes, or the reason it establishes none" → which claims it establishes is
  inference's, decided paragraph by paragraph; a leaf establishing none carries the mechanical
  reason. (L3 row.)
- *The Driver's Contract*, after "The build authors the claim graph and grades none of it", a new
  paragraph (L2 row):
  - Every claim-graph inference is one decision answered by one label from a closed set the build
    offers.
  - An answer that is not one of the offered labels is asked once more and otherwise takes the
    item's stated default, recorded as defaulted. The defaults: a paragraph is unjudged; a candidate
    takes its mechanical draft.
  - Only a call that does not complete stops a stage.
- *Claim-Graph Nodes and Edges* (L4 row):
  - "**Recording a reference is not answering the dependency question**" (the paragraph after the
    three `references` properties) → the classification rule. Every edge candidate is classified
    *mention*, *supported by* or *in support of*, offered only what the graph can carry: an
    equation target is never offered *in support of*, nor is a pair containment directs.
    *Mention* is a `references` edge. The other two are a `depends` edge in the classified
    direction and no `references` record. A build that cannot classify a candidate records its
    mechanical draft.
  - The first `references` property: a claim named by its printed name and number with no `\ref`
    is a reference too. Its source is the claim whose body carries the mention.
  - The ring paragraph ("**This is also where a ring of derived dependency edges lands**") extends
    from containment-derived edges to classified edges **directly**: a classified edge set that
    closes a cycle demotes every edge on the cycle to `references`, with no re-ask first (§6 K5).
- *Document-Tree Contract*, point 6, second paragraph (L4 row): containment supplies direction *for
  the draft*; where a classification runs, a proof-contained pair is asked *supported by* or
  *mention*.

**`kb_tools/ARCHITECTURE.md`**, *The Claim Graph*:

- **Section intro (L4 row):** the `--pass 2` sentence "authors the dependency edges" → "classifies
  every edge candidate".
- **Section intro and node-pass paragraphs (L3 row):**
  - "one ask per leaf" → one letter ask per asked paragraph (L2).
  - "Verdict completeness is the one strong check" → every obligated paragraph carries exactly one
    recorded verdict, `defaulted` included.
  - The node-pass record paragraph: verdict values, causes, no `reason`, no `unanchored`.
  - "Discovery's checks are weak by construction": the quote and widening language goes; placement
    uniqueness stays.
- **Module rows:**
  - `label.py`, `identify.py` and `prose.py` (L3 row).
  - `ask.py` and a new `letters.py` (L2 row); `report.py`, where `AnswerFormatError` goes (L2 row).
  - `attribute.py` (L4 row): the narrowing produces classed candidates and drafts and selects
    nothing; the sentence saying no question is asked about a containment-settled pair goes.
  - `hand_named.py` (L4 row): "Candidates only … nothing asks about or records the rest" → merged,
    classified and recorded like every other candidate.
  - `depends.py` (its report lines) and a new `classify.py` (L4 row); the Driver paragraph that
    names `ask.ModelSelector` (L4 row).
  - `inventory.py`, where "a poorer heading in `ask.py`'s enumeration" stays true.
- **Module Inventory, the `inference/` row (L1 row):** two transports; `READER_SETTINGS` gains
  `alwaysThinkingEnabled: false` and `disableAllHooks: true`; the `KB_READER_*` names. The row
  currently states that no caller can name a model; on the chat route `KB_READER_MODEL` does. That
  is an open owner question: either the env names the served model, as `ANTHROPIC_DEFAULT_*_MODEL`
  already does for the CLI route, or the seat's pin is mapped through per-pin env keys.

**`kb_tools/CONVENTIONS.md`** — keep the byte-exactness file names in the "caller-selected
alternative" bullet accurate (L5 row).

**`kb_tools/ROADMAP.md`** (L4 row):

- Confidence-fed defaults (L8).
- A cycle re-ask, if ring demotions of classified edges prove frequent (M1 reports the count).
- Sub-paragraph claim granularity, if the paragraph unit proves too coarse against C9.

**`ACTIVE_PLAN.md`** (the change's last row, as plan bookkeeping):

- **C2:** the row's "Designed in … which is this row's specification" sentence → the ask is this
  design's L2, one letter per asked paragraph. The rest of the node pass is stated where it landed:
  `kb_tools/ARCHITECTURE.md`, The Claim Graph, for the readable region (`prose.excluded_lines`),
  the node-pass record (`kb_pipeline.NODE_PASS_RELPATH`, as L7 changes it) and equation minting as
  its own stage (`equations-minted`).
- **C6:** the specification is this document, executed by §7's rows. The row's "sorted and
  deduplicated so nothing says which candidate a passage bears on" → each candidate names the
  passages carrying its own reference or mention (§6 K1). Its done-when's "byte-exactness tests for
  the answer blocks" → L5's pins on the rendered prompts.
- **C8:** gains "thinking off, chat route for local inference".

No root contract document changes.

---

## 4. Template interface for the prompt-engineer

PC lands functional templates in L2. PE then owns the prose (L5) against this interface, which the
parse and the slot-order test hold mechanically.

**Shared rules for both kinds:**

- Every per-item slot sits in the final section, after every group slot (L5's test).
- That section opens with a constant line, the same in every ask of the kind.
- Letters reach a template only as composer constants. A template spelling `A` would be a second
  definition of a string the parse holds the seat to (`ask.py`'s marker rule, unchanged).
- The final instruction line's meaning is fixed: *answer with exactly one letter, one of the offered
  ones, and nothing else.* PE owns its wording.
- `@!correction!@` is the last slot. Its alternatives are `None` (first ask) and `letter-correction`
  (re-ask; a fragment carrying `@!dyn.returned!@`, ending without a newline per
  `kb_tools/CONVENTIONS.md`).

### `paragraph.tmpl` (dispatched)

| Part | Slots | Content |
|---|---|---|
| group | `@!dyn.document!@` | the leaf's path |
| group | `@!dyn.body!@` | `label.render` text of the leaf, labelled sentences, excluded blocks shown unlabelled — as today's `identify.tmpl` body |
| constant | `@!letter-claim!@` = `A`, `@!letter-not-a-claim!@` = `B` | — |
| item | `@!dyn.paragraph!@` | the paragraph's label range (`Render.span_of(paragraph).locator`) |
| item | `@!dyn.paragraph-text!@` | that paragraph's labelled lines, repeated next to the question. With thinking off, restating the item where the answer is produced is worth a paragraph's prefill. |
| item | `@!correction!@` | — |

**What the label prose must convey:**

- **A**: the paragraph itself asserts a result — a theorem, a derived relation, a bound, a condition
  under which something holds, a conclusion drawn from an argument. A result stated in plain prose
  counts.
- **B**: it does not — motivation, signposting, recap of a result stated elsewhere (in this document
  or another), notation, definition, narrative.
- The whole-document judgement today's `identify.tmpl` carries — a notation table or a section
  preamble states no result of its own — still applies, now per paragraph.
- Whether the letter definitions sit before or after the body is PE's call. After the body costs one
  definition block of prefill per leaf and puts the definitions next to the question.

### `classify.tmpl` (dispatched)

| Part | Slots | Content |
|---|---|---|
| group | `@!dyn.claim-line!@` | the source, `ask._claim_line`'s shape |
| group | `@!dyn.claim-text!@` | the source's statement: block content, its prose paragraph, or its equation fence |
| group | `@!dyn.reference-lines!@` | every passage of this source's candidates, numbered `P1:` …, sorted, deduplicated (`attribute._reference_line`, generalised to `(document, line)` so a hand-named mention can use it) |
| constant | `@!letter-supported-by!@` = `A`, `@!letter-in-support-of!@` = `B`, `@!letter-mention!@` = `C` | — |
| item | `@!dyn.candidate-line!@` | the candidate, `_claim_line`'s shape |
| item | `@!dyn.candidate-text!@` | the candidate's statement, same three forms |
| item | `@!dyn.candidate-passages!@` | the passage numbers carrying this candidate's reference or mention, e.g. `P2, P5`. This is a mechanical fact: the anchor's own paragraph. |
| item | `@!classify-options!@` | alternative: `classify-options-three` (A, B, C, with the letter instruction) or `classify-options-two` (A, C), chosen in code from the candidate's `offered` |
| item | `@!correction!@` | — |

**What the prose must convey:**

- **A, supported by:** the source needs the candidate to be true.
- **B, in support of:** the candidate needs the source to be true.
- **C, mention:** neither — a borrowed method, a pointer, a comparison, a recap.
- Silence in a passage is not a mention.
- A question names the letters it admits.
- Why a question offers two letters is PE's call to state or omit (proof containment settled
  direction; an equation is a sink).

**Fragments:**

- Registered in `prompt_templates.ALTERNATIVE_SLOTS`: `correction: (None, "letter-correction")` and
  `classify-options: ("classify-options-three", "classify-options-two")`.
- `no-tools` is unchanged.
- Every `identify-*`, `ask-correction`, `depends*` fragment and template is deleted (§5).

---

## 5. What is deleted

Root `CONVENTIONS.md`: "obviated code is deleted, not parked." Whatever
`tests/test_orphan_name_sweep.py` reports orphaned after these deletions goes in the same row. That
is expected to include `kb_driver/envelope.py` names only `ask.py` called, and
`kb_write.ops.resolve_excerpt` / `nearest_excerpt` if `identify` was their only caller.

- **`ask.py`:**
  - The marker constants and block names: `ANSWER_*`, `PROSE_*`, `CLAIM_*`, `NO_CLAIM_*`,
    `NOTHING_FURTHER_*`, `PARAGRAPH_*`, `NONE_OF_THESE_*`.
  - `LEVELS`, the four template constants, `CLAIM_EVIDENCE` and the old alternative names.
  - `compose_prompt`, `compose_cycle_prompt`, `parse_answer`, `answer_block`, `ModelSelector`,
    `compose_identify_prompt`, `parse_identify_answer`, `identify_answer_block`,
    `compose_claim_reask_prompt`, `parse_claim_reask_answer`, `ModelIdentifier`, `_fence_labels`,
    `_identify_correction`, `_claim_records`, `_records_of`.
  - **Kept:** `AskError`, `_put`, `TRANSPORT_ATTEMPTS`, `_claim_line`, `SEAT`, `NO_TOOLS`, and
    `ask_without_tools`, which becomes the CLI `LetterReader`.
- **`identify.py`** (C-inf):
  - Removed: `Record`, `Verdict`, `Answer`, `Trigger`, `Unresolved`, `Telemetry`, `Identifier`,
    `ReAsk`, `Checked`, `ANSWER_RETRY_BUDGET`, `VERDICT_RETRY_BUDGET`, `REASK_CEILING`,
    `CALL_BUDGET`, `SUBSTITUTED_NO_CLAIM_REASON`, `_resolve`, `_went_nowhere`, `_neighbourhood`,
    `_at`, `_labelled`, `_Anchor`, `_extent`, `_judged`, `missing_verdicts`, `_record_placements`,
    `_check_reason`, `_check`, `check_answer`, `_failure_report`, `_ask_document`, `infer_claims`,
    `Reading.may_decline` and `standing_reason`.
  - **Kept:** C-mech (`block_claims`, `check_block_coverage`, `unmarked_documents`),
    `MIN_OPENING_WORDS` / `_opens_a_claim` (now L2's filter and L3's title source), `_unique_slice`,
    `_with_marker`, `_place`, `ProseClaim`.
- **`attribute.py`** (the selection ask and the cycle re-ask): `Question`, `Selector`, `_ask`,
  `check_membership`, `references_beyond`, `PARSE_RETRY_BUDGET`, `CHECK_RETRY_BUDGET`,
  `CALL_BUDGET`, and the selector half of `attribute_dependencies`, which moves to `classify.py`.
- **`report.AnswerFormatError`** (L1). **`kb_pipeline`:** `LeafEntry.reason`,
  `LeafOutcome.UNANCHORED`.
- **Templates:** `depends.tmpl`, `depends-cycle-reask.tmpl`, `identify.tmpl`,
  `identify-claim-reask.tmpl`; fragments `ask-correction`, `identify-display-maths`,
  `identify-no-display-maths`, `identify-reask-{nowhere,several,disagreed}`,
  `identify-missing-verdicts`, `identify-no-claim-{admitted,refused}`,
  `identify-{verdicts,no-verdicts}`.
- **`kb-testing/tools/compare-claimgraph-asks.py`** and its `compare-claimgraph-asks` recipe. The
  tool compares answers in the old formats. It imports `ask.parse_answer` from the fixture's
  installed copy, so it dies with the first restage on the new toolchain, and the done-when makes no
  agreement comparison.

---

## 6. Classification — candidates, classes, drafts and writes

Phase 3 of the build's claim-graph order (`ACTIVE_PLAN.md`, "The build's claim-graph order") is
one classification over every edge candidate, however harvested. It answers THESIS gap 3
(`kb_tools/THESIS.md`): edge existence and direction, with exactly three options. It replaces stage
D's selection ask, which is the two-meaning special case of the same question (*supported by* or
*mention*); §5 lists what goes with it.

### K1. One candidate record, whatever harvested it

```
Candidate(source: ClaimNode, target: ClaimNode, offered: tuple[Relation, ...],
          draft: Relation, passages: tuple[str, ...], harvests: frozenset[Harvest])
```

- **Identity is the ordered pair `(source.id, target.id)`.** The source is the claim whose text
  carries the reference or the mention (SPEC's `references` direction rule, unchanged). Two
  harvests reaching one pair **merge** into one candidate: passages unioned, `offered` the
  intersection, `draft` per K3. The merge replaces `hand_named`'s subtraction of pairs a reference
  already reached (`attribute.narrow`'s `hand_named=` argument).
- **`passages` are the candidate's own:** the paragraph of each anchor or mention that produced it.
  That is a mechanical fact about the candidate, and the classify ask names them per candidate
  (`@!dyn.candidate-passages!@`, §4). The group's `@!dyn.reference-lines!@` is their union over
  the source's candidates, sorted and deduplicated.
- `Harvest` is `{reference, hand-named}`; C7 adds its own member. **Nothing branches on it** except
  report counts: the class is computed from the pair, never from how it was found.
- `Relation` is a closed `StrEnum`: `supported-by`, `in-support-of`, `mention`. The classify letter
  table (L1) maps `A`, `B`, `C` onto it one to one.
- No class field travels past the narrowing. `offered` and `draft` are what everything downstream
  reads; the class name is report vocabulary only.

### K2. Classes and offered subsets, computed once in `attribute.narrow`

`narrow` is the one function holding the facts a class is made of: whether proof containment
settled the source end (`_source_end`'s `directed`), which route settled the target end, and the
target node. It computes each provenance's class, and K1's merge yields the candidate's `offered`.

| Class | Test (on facts `narrow` already holds) | `offered` |
|---|---|---|
| proof-directed | `_source_end` returned `directed=True` (the anchor sits in a proof bound to a subject) | `supported-by`, `mention` |
| equation target | `target.equation is not None` (a minted equation node; an `eqref` that resolves *through* to a block's claim or a proof's subject is a claim target, not this) | `supported-by`, `mention` |
| claim to claim | neither of the above | `supported-by`, `in-support-of`, `mention` |
| target resolves to no node | — | **not a candidate** |

- **The offered table is one mapping, total over the class enum** (`kind_table` style), defined
  once in `attribute.py`. Every subset contains `supported-by` and `mention`, so an intersection is
  never empty and the draft is always offered.
- **"Resolves to no node" is unrepresentable rather than branched on** (`kb_tools/AGENTS.md`, "Name
  the producer before you write the refusal"). `narrow` already `continue`s on an anchor with no
  target or no node, `_target_end` returns `()` for its refusals, and `hand_named.printed_claims`
  joins only nodes. A `Candidate` requires a `ClaimNode` target, so no code checks for the case.
- **Equation target.** An equation node is terminal (SPEC, Claim-Graph Nodes and Edges), so an edge
  originating at one is provably wrong. The table keeps *in support of* off such a question, and
  L1's strict parse treats `B` there as no valid letter.
- **A proof-directed provenance excludes *in support of* for the whole pair** (the intersection).
  A proof of `s` citing `t` while `t` rests on `s` is circular unless it is a mention, and mention
  is offered.

### K3. The draft, and `--no-inference`

`draft` is `supported-by` where the narrowing **settles** the pair (`directed and route is not
None` in `attribute.narrow`) and the pair is on no containment ring (`cycle_edges`); it is
`mention` everywhere else. The two tests differ: a proof-directed pair whose target fell to the
multi-claim fallback is *offered* the proof-directed subset but *drafted* `mention`.

With no reader, every candidate takes its draft. That reproduces the current `--no-inference`
output, except that hand-named candidates are recorded as `references`: they are references made
without `\ref` (THESIS gap 2). C5 measured 0 hand-named candidates on every staged corpus, so the
figure does not move.

**Best odds, measured.** Of the 253 open pairs the C8 ModernCorp run asked about (§2), the model
selected roughly 85 as dependencies: that run's 91 `depends` (`ACTIVE_PLAN.md` C8) less the 6
containment settles (C4 row). That is about a third, so `mention` is the majority answer for an
open pair, and containment's direction is the mechanical answer for a settled one. Neither default
leaves the pair unrecorded.

### K4. Order inside `depends-attributed`

1. Harvest: `narrow` over references, the C4 filter, `hand_named.harvest`, and, once C7 lands,
   C7's candidates read from wherever C7's own stage records them.
2. Merge and class every candidate (K1, K2).
3. Containment-ring demotion over the drafts (`cycle_edges`, unchanged; it decides drafts only).
4. Classify: one letter ask per candidate, grouped by source in ascending source id (L5), each
   group recorded as it completes (L7).
5. Acyclicity over the classified edge set; every edge on a remaining cycle is demoted (K5).
6. One `write_edges` batch.
7. Gate G.

- **Harvest completes for the whole corpus before the first ask**, so no group is composed from a
  partial candidate set.
- C7 spends inference to harvest, so it is a stage of its own ahead of `depends-attributed` (SPEC,
  The Driver's Contract: a boundary behind every inference-spending step). Classification only
  reads its output.
- **Reused unchanged:** the narrowing's source-end and target-end rules, the C4 word filter, the
  fragment refusal, `cycle_edges`, `check_acyclic` and `_cycle_path`; `_reference_line` as the
  passage source, generalised to `(document, line)` so a hand-named mention can use it;
  `write.write_edges`; the stage name (`depends-attributed`), its invocation (`--pass 2`) and its
  `--no-inference` semantics (`kb_tools/ARCHITECTURE.md`, The Driver: the tool's own flag, not a
  dropped row).

### K5. Failures and cycles

Per `kb_tools/AGENTS.md`: best odds where certainty is not available, never provably wrong where
it is, and a result is weighed against what replaces it — here, a stop that discards every ask the
stage already spent (SPEC, The Driver's Contract: expensive work that succeeded is never
discarded).

| What happened | Outcome |
|---|---|
| A call never completes (`ask.AskError`, after `TRANSPORT_ATTEMPTS`) | **The stage stops** (L1) |
| A reply carries no valid letter, or a letter outside the candidate's `offered` | One re-ask of that candidate, then its draft (L1), named on the report |
| The classified edge set closes a cycle | **Every edge on a cycle is demoted to `references`** (`cycle_edges` over the final set), named on the report. There is no cycle re-ask. |

- The ring rule is SPEC's existing one, extended from containment-derived edges to classified ones.
  It keeps every relationship and gives up only the direction the cycle disproves.
- There is no cycle re-ask because it would be the only ask putting other answers in front of the
  seat, and it would need a template of its own. M1 reports the ring-demotion count; the re-ask is
  a ROADMAP entry (§3) for the case where that count proves frequent.
- A demoted or defaulted candidate is recorded, never dropped. The report says which and how many,
  with a zero form (`kb_tools/kb_claimgraph/depends.py`'s existing practice).

### K6. What each letter writes: one record per candidate

| Letter | Meaning | Written |
|---|---|---|
| `A` | supported by | `depends` source → target |
| `B` | in support of | `depends` target → source; it lands in the target's register entry, since `write_edges` already keys by edge source |
| `C` | mention | `references` source → target; class and direction rule unchanged |

- **A candidate answered `A` or `B` carries no `references` record** (`ACTIVE_PLAN.md` C6: "mention
  leaves the `references` edge"). One function maps `(candidate, relation)` to its record; the
  write, the acyclicity check and the report all read that function.
- `references_beyond`'s same-direction subtraction is deleted (§5). It would leave an *in support
  of* pair's `references` record standing, because the `depends` edge runs the other way.
- `(s, t)` and `(t, s)` may both be candidates, in two sources' groups. Agreeing answers dedupe on
  the edge; disagreeing ones form a cycle and take K5's path.
- No new `relation` value and no schema change: `DependsOnEdge.relation` keeps its five classes.

---

## 7. Rows

| Row | What | Seat | Files owned | Blocked on | Done when |
|---|---|---|---|---|---|
| **M0** | Read-only count script. Per kb-root: readable paragraphs, obligated paragraphs, paragraphs passing the opener filter (= node-pass asks); candidates by class × harvest, distinct sources (= classify groups), drafts by relation. Reads `prose`, `identify._opens_a_claim` and today's `attribute.narrow`. After L4 it reads the candidate records instead. | PC | `kb-testing/tools/measure-letter-asks.py` | — | Runs through `measure-kb-roots` on the current tree; §2's table filled with exact figures |
| **L0** | Probe instrument. `replay-claimgraph-asks.py`'s fixed `CALL_SETTINGS` become flags (`--thinking on\|off`, `--max-tokens`, `--temperature`), and each capture records `usage.prompt_tokens_details.cached_tokens` where returned. Recipe `[doc]` updated. | PC | `kb-testing/tools/replay-claimgraph-asks.py`, the `replay-claimgraph-asks` recipe line in `kb-testing/justfile` | — | P1, P2, P4 answered (§9) |
| **L1** | Transport. The chat route (`inference/chat.py`, new) and its outcome mapping. `READER_SETTINGS` gains `alwaysThinkingEnabled: false` and `disableAllHooks: true`. The `KB_READER_*` constants. ARCHITECTURE `inference/` row. | PC | `kb_tools/inference/{chat,seat,__init__}.py`, `kb_tools/tests/test_inference.py`, `kb_tools/ARCHITECTURE.md` (that row) | P1 | `just test` green. A chat call over a substituted opener sends `enable_thinking: false`, `temperature: 0`, `max_tokens`; 4xx is classified not retryable, 5xx/timeout retryable. A CLI reader argv carries both settings keys. |
| **L2** | Letter machinery. `letters.py`: question, reply, `decide`, one re-ask, group runner (warm-first, then `W` in flight, results in item order), per-group ask record (the prefix once, each item's tail, reply, letter, outcome, duration, usage). `ask.py` rewritten: compose both kinds, letter constants, the CLI and chat `LetterReader`s, route selection. Functional `paragraph.tmpl`, `classify.tmpl` and fragments; `prompt_templates` registry. Deletions in §5 for `ask.py`, `report.py` and templates. SPEC Driver's Contract paragraph; ARCHITECTURE `ask.py`/`letters.py`/`report.py` rows. | PC | `kb_tools/kb_claimgraph/{letters,ask,report}.py`, `kb_tools/kb_driver/prompt_templates.py`, `kb_tools/kb_driver/prompt-templates/**`, `kb_tools/tests/test_kb_claimgraph_ask.py`, `kb_tools/tests/test_kb_driver_prompt_templates.py`, `kb_tools/{SPEC,ARCHITECTURE}.md` (those parts) | L1 | `just test` green. The slot-order and shared-prefix tests (L5) pass for both kinds. Over a fixed reader: a malformed reply re-asks once with the correction after the question, then defaults; a reply outside `offered` is malformed; a transport failure raises `AskError`; a reader returning `confidence` is decided by argmax over offered letters. |
| **L3** | Node pass on letters. `identify.py`: asked paragraphs (L2), mechanical titles (L3), placement, verdicts with causes. `discover.py`: per-leaf group, plan, land, report lines (letters answered / re-asked / defaulted by cause, cached-token share, prose claims minted). `prose.standing`: `defaulted` → `UNJUDGED`. `kb_pipeline` node-pass record changes (L7). `__main__.py` wiring. SPEC "What is said about a leaf"; ARCHITECTURE node-pass paragraphs and the `label`/`identify`/`prose`/`discover` rows. | PC | `kb_tools/kb_claimgraph/{identify,discover,prose,__main__,inventory}.py`, `kb_tools/kb_pipeline.py` (node-pass record), `kb_tools/tests/test_kb_claimgraph_{nodepass,cinf,claim_naming}.py`, `kb_tools/tests/test_kb_pipeline.py`, `kb_tools/{SPEC,ARCHITECTURE}.md` (those parts) | L2 | `just test` green. Over a fixed reader: every obligated paragraph is asked whatever its words; a markup-only unobligated paragraph is not asked; a defaulted obligated paragraph's references follow the unjudged rule (not dropped); an unplaceable yes is recorded `defaulted/unplaceable` and the stage continues; titles are unique per leaf and identical across two runs; a stop after leaf *k* resumes asking from leaf *k+1*. |
| **L4** | Classification on letters (§6). `attribute.py`: candidates, classes, drafts, merge, per-candidate passages (K1–K3). `classify.py` (new): groups by source, letter asks, defaults, classification record (L7), acyclicity → ring demotion (K4, K5), one label→record mapping (K6). `depends.py` report lines (by label, defaulted, drafted, demoted, cached-token share). `hand_named.py` merge. `steps.py` comment. Measurement scripts given the new shape. SPEC Claim-Graph edits (§3); ARCHITECTURE rows; ROADMAP entries. | PC | `kb_tools/kb_claimgraph/{attribute,classify,depends,hand_named}.py`, `kb_tools/kb_pipeline.py` (classification record), `kb_tools/kb_driver/steps.py`, `kb_tools/tests/test_kb_claimgraph_{pass2,claim_naming}.py`, `kb-testing/tools/measure-claim-naming.py`, `kb_tools/{SPEC,ARCHITECTURE,ROADMAP}.md` (those parts) | L2 (L3 for the record file, if it is edited in sequence) | `just test` green. Each class is offered its own letters, asserted on the composed prompt. `B` writes target→source and no reference. An equation candidate answering `B` is malformed and drafts. A classified 2-cycle demotes both edges to `references` and is named on the report. A stop mid-stage resumes asking only unrecorded candidates. With no reader, M0 over the 54 kb-roots shows `depends` identical per root (§8 invariant 13). |
| **L5** | Templates. PE rewrites `paragraph.tmpl`, `classify.tmpl`, `letter-correction`, `classify-options-{three,two}` against §4. PC pins byte-exactness on rendered prompts (first ask and re-ask, both kinds, both option sets). | PE, then PC for the pin | the templates and fragments; the pin tests in `test_kb_claimgraph_{cinf,pass2}.py`; `kb_tools/CONVENTIONS.md` file-name accuracy | L3, L4 | The pins pass; the slot-order test still passes; PE's report records each prompt read end to end |
| **L6** | Replay on the new records. `replay-claimgraph-asks.py` replays per-group ask records through the production `LetterReader`s on either route (`--route cli\|chat`), reporting per-ask latency, cached tokens and letters, and drops its `liaison_tools` import. Deletes `compare-claimgraph-asks.py` and its recipe. | PC | `kb-testing/tools/replay-claimgraph-asks.py`, `kb-testing/tools/compare-claimgraph-asks.py`, `kb-testing/justfile` (both recipes) | L2 | Replays a fixed recorded group on both routes under `just -f kb-testing/justfile replay-claimgraph-asks …`; P3 and P5 answered with it |
| **L7** | Resume without restaging. `kb-driver-fixture` gains a `--resume` leading flag: it skips `stage-fixture` and launches the same `kb_driver run` (sources recomputed as now), which resumes from the ledger. | PC | `kb-testing/justfile` (that recipe), `kb-testing/README.md` (its usage line) | — | Over a fixture whose build was stopped mid-stage, `--resume` continues from the ledger's position; without the flag, behaviour is unchanged |
| **M1** | The owner's measure. A ModernCorp build via `just -f kb-testing/justfile kb-driver-fixture test-data/transient/ModernCorp <env with KB_READER_*>`, run to completion, with wall time recorded. Report: per-stage ask counts, mean and median per-ask time, cached-token share, defaults by cause, ring demotions, nodes by kind, edges by relation. Then `compare-to-pristine.py` through `measure-kb-roots` (C9). Baseline, not a target. | PC (run), owner (judge) | report only; `ACTIVE_PLAN.md` C2/C6/C8 rows per §3 | L5, L6, L7 | The build completes; wall time and both reports are in the landing report, citing both scripts by path |

**Order:** M0 and L0 first; both are read-only and settle §9's probes before approval. Then L1 → L2
→ L3 ∥ L4 → L5 → L6. L7 can run any time. M1 comes last.

**Shared working tree:** `kb-testing/justfile` and `kb-testing/README.md` carry uncommitted edits by
another hand (git status at design time). L0, L6 and L7 touch them, and those rows edit the lines
they own only.

---

## 8. Invariants and the failure modes they prevent

1. **Every byte before an ask's question section is identical across its group.** *Prevents:*
   per-item text drifting forward in a template and silently turning every ask into a full prefill.
   *Held by:* L5's two tests, plus the cached-token share on every stage report.
2. **No transport injects per-call content ahead of the prompt.** *Prevents:* the SessionStart
   timestamp (L6 finding 2) or any later per-call reminder defeating the cache. *Held by:*
   `disableAllHooks` on the CLI route; the chat route sends only what `letters` composed. Reported
   cache share again.
3. **One letter→meaning table per kind; subsets withhold letters, never rename them.** *Prevents:*
   reversed `depends` edges from a relabelled subset.
4. **Every item ends with exactly one recorded outcome** — answered, re-asked, defaulted (with
   cause), or drafted — **and a malformed reply never stops a stage.** *Prevents:* the measured
   failure, a 5-hour build lost on one unjudged paragraph.
5. **A paragraph default never drops a reference** (defaulted → `UNJUDGED`). *Prevents:* defaulting
   to not-a-claim, a silent loss of relationship.
6. **Concurrency changes nothing that is written.** Results are keyed by item, landed in item order,
   and the records are sorted. *Prevents:* nondeterministic KB bytes or record diffs between two
   runs that got the same answers.
7. **Thinking is off by construction on the chat route** (`enable_thinking: false`,
   `max_tokens: LETTER_MAX_TOKENS`). *Prevents:* the build quietly returning to 5 hours. *Held by:*
   L1's test on the request body, plus completion tokens ≤ `LETTER_MAX_TOKENS` in the ask records.
8. **The first ask of a group completes before the rest are issued.** *Prevents:* `W` concurrent
   cold prefills of the same prefix.
9. **The stage exits only on a comparison or a return code** (`kb_tools/CONVENTIONS.md`). No letter
   decides whether a stage succeeded.
10. **Every candidate reaching `classify.py` has `offered ⊇ {supported-by, mention}` and
    `draft ∈ offered`.** *Prevents:* an empty intersection after a merge, or a default the question
    never offered. *Held by:* K2's one offered table.
11. **No `depends` edge originates at an equation node, and each candidate yields exactly one
    record** (K6). *Prevents:* a provably wrong edge out of a sink; an *in support of* pair keeping
    its `references` record beside the reversed `depends` edge.
12. **The class is a function of the pair's facts**, never of its harvest or of `reference_type`.
    *Prevents:* a hand-named and a referenced candidate for one pair being offered different
    letters.
13. **With no reader, `depends` per kb-root is identical before and after this change;
    `references` differs by the hand-named count alone.** *Prevents:* the draft rule drifting from
    the current mechanical answer. *Held by:* L4's done-when (M0 over the 54 kb-roots).

**Failure modes in classification a coder is likely to hit:**

- **Classing on the route instead of the target.** `BY_EQUATION` also resolves an `eqref` to a
  block's claim or a proof's subject; only `target.equation is not None` is a sink. Branching on
  the route denies *in support of* to ordinary claims.
- **Conflating "offered proof-directed" with "drafted `depends`".** A proof-directed pair whose
  target fell to the multi-claim fallback is offered two letters and drafted `mention` (K3).
  Getting this wrong moves `depends` under `--no-inference`; invariant 13 catches it.
- **Writing *in support of* the wrong way, or leaving the `references` record beside it.** Route
  every record through K6's one mapping function; never reuse a same-direction subtraction.
- **Breaking the measurement scripts silently.** `kb-testing/tools/measure-claim-naming.py` reads
  `narrowed.edges` / `.references` / `.questions`. Give it the new shape, or `-` fields per its own
  rule that a field the code under measurement does not carry reads `-`.
- **Keeping tests that encode the old contract.** In `test_kb_claimgraph_pass2.py`,
  `test_containment_settles_the_edges_a_proof_directs_and_no_model_is_asked` and
  `test_edges_containment_settles_are_never_also_asked_about` become "drafted without a reader,
  asked with one". The claim-naming tests asserting hand-named candidates are "neither asked nor
  recorded" change likewise.

**Deliberately not specified** (the coder's choice, and genuine flexibility rather than a buried
assumption):

- `TITLE_MAX_CHARS` and `LETTER_MAX_TOKENS` beyond "small" — P1 bounds the latter.
- The record JSON field names beyond L7's content.
- The ask-record file layout beyond L2's content.
- The HTTP timeout value.
- Whether `letters.py` and the two readers share a module with `ask.py`, provided `ask.py` holds
  every template choice and `letters.py` holds every decision.

---

## 9. Probes — before approval (execution-only assumptions)

| # | Assumption | How | Settles |
|---|---|---|---|
| **P1** | The server at `http://reaper.local:4000/v1` honours `chat_template_kwargs.enable_thinking=false` for `Qwen3.8-Flash-Next`: the first generated token is the answer, with no reasoning content and no empty `<think>` block emitted as output. | L0: `replay-claimgraph-asks <env> --thinking off --max-tokens 8 --temperature 0 --ask <one stem>`, using an env file naming the build's model. Read `completion_tokens` and `text`. | Whether L1's chat route turns thinking off; `LETTER_MAX_TOKENS` |
| **P2** | The server keeps a prefix cache across requests and reports it, and its prefill rate is near the model's assumption (1000 tok/s). | L0: replay one ask twice (the second run after deleting its capture). Compare `duration_ms` and `cached_tokens`. Prefill rate = `prompt_tokens / duration` on the cold call. | L5's whole premise; the latency model's `R_prefill` |
| **P3** | On the CLI route, `alwaysThinkingEnabled: false` stops the server emitting thinking, and `disableAllHooks: true` removes the SessionStart context. | L6 `--route cli` on one group. In each capture, look for `"type":"thinking"` and `hook_response`; read `output_tokens` and `cache_read_input_tokens` on the second ask. | Whether the CLI route is viable for local builds, or cloud and tests only. Not design-changing: the chat route is the local build route either way. |
| **P4** | Concurrency raises throughput on this server, and `W` asks in flight after a warm prefix all hit the cache. | L0: `--concurrency 1` vs `4` vs `8` over a fixed set of asks; total wall time and per-ask `cached_tokens`. | `W`'s default; whether cross-group pipelining is worth specifying |
| **P5** | The per-ask overhead of a `claude -p` process. | L6 `--route cli`: wall time per ask minus the result event's `duration_api_ms` | The CLI-route term of the latency model |
| **P6** | `kb_driver run`, launched over a fixture whose ledger records stages, resumes rather than refusing, with the same `--source` arguments. | L7's done-when, run on a stopped fixture | Whether L7 needs more than skipping `stage-fixture` |

---

## 10. Acceptance criteria

- Every claim-graph model ask offers a closed set of letters and accepts exactly one of them. No
  claim-graph template or parse handles any other answer format.
- A reply outside the offered set never stops a stage: it is asked once more, then defaulted, and
  the report counts defaults by cause in the zero form. A call that never completes still stops it.
- On the chat route every claim-graph request carries `enable_thinking: false`, `temperature: 0` and
  a small `max_tokens`. No ask record shows more completion tokens than that cap.
- The second and later asks of a group report a cached prompt-token share that P2 makes a target for
  (stated in M1's report). Two asks of one group differ only in their question section.
- A paragraph's default never drops its references; a candidate's default is its draft.
- Every obligated paragraph carries exactly one recorded verdict at the node pass's end.
- Every candidate, from any harvest, is classified or takes its draft, and the report says which,
  per count.
- A proof-contained pair is asked (*supported by* or *mention*) when a reader runs, and is written
  `depends` unasked when none does.
- Each candidate class is offered only its letters. `supported by` writes `depends` source→target,
  `in support of` writes target→source, and `mention` writes `references`; one record per candidate.
- A `--no-inference` build's `depends` edges are unchanged on every staged kb-root.
- A stop mid-stage, in either stage, resumes asking only items its record does not hold.
- Replacing generation with a per-label classifier read needs a new `LetterReader` and no change to
  either stage, the records or the write.
- **Owner's measure:** a ModernCorp build via `kb-driver-fixture` completes, with wall time
  recorded, and the C9 comparison against `ModernCorpPristine` is reported. Both are judged on their
  own terms.
