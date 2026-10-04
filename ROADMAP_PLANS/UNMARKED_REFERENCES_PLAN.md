# UNMARKED_REFERENCES_PLAN.md — unmarked prose references, found by one-letter asks over a mechanical shortlist

**Status: every owner decision is settled; ready to execute, not yet dispatched.** This is the
claim graph's next work after the letter-asks build that the baseline below measures.

**Paths** are repository-root-relative. The stage lives at `kb_tools/kb_claimgraph/`. The letter
asks, candidates, drafts, classification and build records are as `kb_tools/SPEC.md` and
`kb_tools/ARCHITECTURE.md` (The Claim Graph) state them; this plan cites them and does not restate
them (What this builds on).

**Seats.** **AR** architect, for a change to the stage table or to a decision here; **PC**
python-coder; **PE** prompt-engineer, for anything under `kb_tools/kb_driver/prompt-templates/`.

**Numbering.** **U1–U7** are the decisions, **I1–I18** the invariants, **R1–R5** the rows. Bold
inside a row marks a decision the row itself makes and records; elsewhere it marks the rule a coder
must not miss.

**What travels with a dispatched row**: this header, Standing rules, Where the stage is, What this
builds on, the decisions the row names, Invariants, the row, and the rows it is blocked on. Order
does not travel.

## Owner decisions

**1. K and the ranking (U3) — settled: `wm/statement` TF-IDF at K = 5.** The ranking is
`kb_tools/kb_claimgraph/shortlist.py` (words through `kb_write.ops.canonical_form` plus maths
symbols from inline and display maths, each node's statement on both sides, IDF over target
statements, cosine, ties to the lower target id, existing candidate pairs excluded), `K = 5`.

Measured on the ModernCorp build of 2026-10-03 (303 sources, 28 unmarked misses), misses reached
forward / either direction:

| Shortlist | Asks | Reached |
|---|---|---|
| TF-IDF `wm` K = 3 | 909 | 6 / 9 |
| TF-IDF `wm` K = 5 | 1,515 | 12 / 15 |
| TF-IDF `c9` K = 5 | 1,515 | 13 / 14 |
| embeddinggemma-300m, `fact checking` prompt, K = 3 | 909 | 11 / 11 |
| embeddinggemma-300m, `fact checking` prompt, K = 5 | 1,515 | 13 / 14 |
| TF-IDF `wm` 1 ∪ embedding 2 | ≤ 909 | 11 / 11 |

Embeddings were measured (nomicai-embed, embeddinggemma-300m, snowflake-arctic-embed-l-v2.0;
Qwen3-Embedding runs wrongly on oMLX and Nemotron-3-Embed-1B does not load there) and are not in
the build for now: at K = 5 they tie TF-IDF, their gain is fewer asks at K = 3 (about 600 asks,
≈ 10 minutes at W = 4) rather than more reach, and a union adds nothing over the embedding alone.
They stay as tools (`openai_chat.post_embeddings`, `measure-unmarked-shortlist.py --embed`) for
the next round. K is one constant; raising it waits on R5's yes rate.

**2. The leaf in the ask (U1) — settled: show the source's leaf.** The claim's own words ("this
escape", "the bound above") resolve against it (Evidence 4), at no measurable per-call cost. The ask
still asks about the claim's text, and U1's prose makes a pointer the claim does not take up a `B`.
`unmarked.tmpl.md` carries the leaf as a group slot. Revisit if the leaf leads readers to answer `A`
for pointers made only by neighbouring paragraphs.

**3. The list ask (U2) — moot.** It was the fallback if decision 1 ran over budget; it did not.

**4. The stage id — settled: `references-found`** (display "unmarked references found"), two
words like every other stage id. Stage ids are a contract: "an id is never renamed in place; a
change means a new id and a migration" (`kb_tools/kb_pipeline.py`, the frozen-vocabulary comment
above the stage table).

**Not blocking, and outside the toolchain:** the three server settings (Server settings, below).
Every time figure in this plan assumes none of them changes.

## In one paragraph

A third letter kind, `unmarked`: one ask per shortlisted ordered pair `(s, t)` — *does the text of
source claim `s` point at candidate `t`'s result without a cross-reference?* — `A` yes, `B` no,
default no candidate. All pairs cost 43,641 asks (37.6 h) on ModernCorp, so asks are bounded by a
**mechanical per-source shortlist**: each source claim's `K` best targets by TF-IDF similarity over
the whole build's node set, 197·K asks on ModernCorp. Pairs already candidates are excluded. No
locality filter applies: 20 of the 42 misses cross papers. Each yes becomes a candidate harvested
`unmarked` and goes to classification unchanged.

## Where the stage is

**Mechanically** (`--no-inference`): direction has one source, an anchor inside a `proof` bound to
the claim it proves. `ModernCorpDerivations.tex` states its derivations as 325 lines of prose with
zero proof environments, and prose carries no direction a parser can read. A minted equation node is
a **sink** — no edge originates at one — so for an equation target only existence is open. Under
`--no-inference`, `claims-discovered` is refused and `depends-attributed` writes every candidate's
draft.

**In place**, each stated in `kb_tools/ARCHITECTURE.md`, The Claim Graph:

- the node pass on paragraph letter asks (`claims-discovered`), with equations minted by their own
  stage (`equations-minted`) after the verdicts;
- the letter machinery (`letters.py`, `ask.py`) and the tool-less, thinking-off, one-turn reader
  (Module Inventory, `inference/`);
- classification of every candidate *supported by*, *in support of* or *mention*, with its record
  and resume (`attribute.py`, `classify.py`, `depends.py`);
- the naming filter (`attribute.names_no_premise`) and hand-named mentions (`hand_named.py`), the
  latter yielding 0 candidates on every staged corpus;
- the pristine comparison, `kb-testing/tools/compare-to-pristine.py` (Standing measurement, below).

**The baseline build** (ModernCorp, Qwen3.8-Flash-Next on the local seat, `KB_READER_CONCURRENCY=1`,
2026-10-03, built at `ed63394`): **65.7 minutes**, all nine stages; 985 claim-graph calls, **zero
thinking blocks**.

- *Node pass:* 765 paragraph items in 162 leaf groups — 642 answered, 108 re-asked, 15 defaulted (no
  letter; 0 unplaceable). 888 calls, median 3.08 s, mean 3.84 s, `duration_api_ms` mean 3.58 s;
  56.4K output tokens; cache share 8.3%.
- *Classification:* 72 candidates in 44 source groups — 47 answered, 25 re-asked, 0 defaulted. 97
  calls, median 3.36 s; cache share 0%.
- *Graph:* 223 claim nodes (171 prose, 26 block, 26 equation); 52 `depends`, 18 references, and one
  classified 2-cycle demoted to two references.
- *Cost:* per-call overhead (wall less `duration_api_ms`) ≈ 0.3 s. The time is server prefill, which
  reuses no shared prefix on this model (Server settings).
- **Every re-ask observed was the model reasoning in prose before a letter.** That is what R4's
  template prose has to prevent, and why this plan budgets 1.16–1.35 calls per ask.

**Pristine comparison on the baseline build** (`.claude-temp/pristine-compare/summary.md`): 37 of 43
author claims matched; of 71 author edges, 1 recovered as `depends`, 1 `references` only, 5 shared
node, 19 endpoint unmatched, 45 nothing. Misses: **42 unmarked** (20 crossing papers, 22 within one)
and 4 marked. The 42 unmarked misses are this plan's target; the 19 unmatched endpoints are not
reachable by it.

## Server settings outside the toolchain

The diagnosis of the reader against the local oMLX server found three causes only the server's
configuration can remove. They are the owner's. The toolchain does not work around them (I6).

1. **Prefix reuse — boundary snapshots.** The server does no partial-prefix reuse on this model, so
   asks sharing a group's prefix are each prefilled whole (cache share 0% on classification, 8.3% on
   the node pass). Grouping by source pays only once this is enabled.
2. **Cache size — paged SSD cache (`--paged-ssd-cache-dir`, `OMLX_PAGED_SSD_CACHE_DIR`) or a
   larger memory budget.** The cache holds about 6 recent prompts.
3. **MCP tools off — `mcp.config_path` (`--mcp-config`, `OMLX_MCP_CONFIG`).** These names are from
   the oMLX 0.6 source; the server reports 0.7.0, so confirm them there. The server adds its MCP tools to every prompt (≈ 1.6K
   tokens). With thinking off the model also calls them; the reader's one-turn cap and its reading
   of a capped call's text (ARCHITECTURE, the `ask.py` row) already absorb that.

## Standing rules — on every row, not restated per row

1. **Best odds where certainty is not available; never provably wrong where it is**
   (`kb_tools/AGENTS.md`). The alternative to a rule that sometimes misfires is no rule and no
   result.
2. **Declining to record a relationship is not the cautious option.** It leaves the graph asserting
   the claim rests on nothing, silently, and no later pass is prompted to revisit it.
3. **A row that narrows or widens an inference step argues its scope against `kb_tools/THESIS.md`,
   in the report that lands it** (`kb_tools/AGENTS.md`).
4. **No stage exits on a model's opinion** (`kb_tools/CONVENTIONS.md`). Every stage exits on a
   comparison between two artifacts or a subprocess return code.
5. **No prompt reaches a model from a heredoc or an in-code string** (`kb_tools/CONVENTIONS.md`).
   Every prompt is a template, and its prose is PE's seat.
6. **A row reports its figure over the real narrowing**, read-only through `measure-kb-roots`
   (`kb-testing/justfile`), citing the script by path (`kb_tools/CONVENTIONS.md`, first bullet).
7. **Before and after on the same corpus**, edge counts split by relation. A row that moves
   `depends` reports what it moved from `references`.
8. `just test` green at handoff. `kb-testing/test-data/transient/` is read-only — copy rather than
   write. Scratch under `.claude-temp/`, never `/tmp`.

## The build's claim-graph order

Three phases, each finishing before the next begins.

1. **Nodes.** `claims-discovered` and `equations-minted` fix the node set until the build ends.
2. **Edge candidates**, from the fixed node set only, **complete for the whole corpus before the
   first classify ask**: every mechanical reference whose source text belongs to a node, less those
   in paragraphs judged not a claim and those the naming filter drops; hand-named mentions; and
   **unmarked references** — a mechanical per-source shortlist over the whole node set, each pair
   asked whether the source's text points at the target, a yes recorded as a candidate
   (`references-found`, U1–U6).
3. **Classification** of every candidate, however harvested (`kb_tools/THESIS.md`, gap 3).

## What this builds on — stated in the contract, cited here

- **One decision, one offered label, one re-ask, then the default; only a call that never completes
  stops a stage:** `kb_tools/SPEC.md`, The Driver's Contract, "Every claim-graph inference is one
  decision, answered by one label from a closed set the build offers."
- **The strict parse, `decide`, `ask_group` (first ask alone, then `KB_READER_CONCURRENCY` in
  flight), results in item order, the per-group ask record, `AskTotals`:** ARCHITECTURE, the
  `letters.py` row.
- **One letter→meaning table per kind, letters only as composer constants, every per-item slot after
  every group slot, the shared-prefix tests, `letter-correction`:** ARCHITECTURE, the `ask.py` row.
  Alternatives end without a newline and the byte pins live where `kb_tools/CONVENTIONS.md` ("A
  caller-selected alternative ends without a newline") lists them.
- **The reader** — seat's pin through `claude -p`, no tools, no MCP, no memory, thinking off, hooks
  off, one turn: ARCHITECTURE, Module Inventory, `inference/`.
- **`Candidate`, `Harvest`, the classes and `OFFERED`, drafts, the merge of two harvests of one
  pair, `written`:** ARCHITECTURE, the `attribute.py` row; the classification rule,
  `kb_tools/SPEC.md`, Claim-Graph Nodes and Edges, "Every edge candidate is classified …".
- **The classification record, its resume, its empty write by the declared pass, ring demotion of
  classified edges:** ARCHITECTURE, the `classify.py` row.
- **A boundary behind every step that spends inference:** `kb_tools/SPEC.md`, The Driver's Contract,
  "Expensive work that succeeded is never discarded, and that is what decides where a stage boundary
  falls." Build state outside `kb-root/`: same section, "Build state never enters `kb-root/`."
- **`references` direction — the source is the claim whose text carries the reference:**
  `kb_tools/SPEC.md`, Claim-Graph Nodes and Edges, the first `references` property.

## Decisions — the unmarked-reference ask

### U1. The ask: a third letter kind

| Kind | Unit (one ask) | Group (shared prefix) | Letters offered | Default if no valid letter |
|---|---|---|---|---|
| **unmarked** (`references-found`) | one shortlisted ordered pair `(s, t)` | its source claim `s` | `A` the text of `s` points at `t` · `B` it does not | **no candidate** (U4) |

- **It decides existence only** — `kb_tools/THESIS.md` gap 2. Direction and dependency stay with
  gap 3: a yes is classified like any other candidate (U6). The ask never offers *supported by* or
  *mention*.
- **"Points at" is the reference relation, not a dependency.** The claim's own text names the other
  result by description, restates it, applies it, assumes it as a condition, or uses notation the
  candidate introduces for what it states. A shared subject or shared standard notation is not
  pointing.
- **`UnmarkedLetter`** is a `StrEnum` in `ask.py`: `POINTS = "A"`, `DOES_NOT = "B"`. It reaches the
  template only as the composer constants `letter-points` and `letter-does-not-point`. The kind is
  `letters.Kind.UNMARKED`.
- **Order:** groups by source in ascending id, as classification's; within a group, `ask_group`'s
  order. Results go in item order.

**Template interface — `unmarked.tmpl.md`** (PC lands it functional in R2, PE owns the prose in R4):

| Part | Slots | Content |
|---|---|---|
| group | `@!dyn.document!@`, `@!dyn.body!@` | the source's leaf path and its `label.render` text — the body the node pass showed (`identify.reading_of(...)`'s render). Present only if owner decision 2 keeps the leaf |
| group | `@!dyn.claim-line!@`, `@!dyn.claim-text!@` | the source: `ask._claim_line`, and its statement (`classify.statements`) |
| constant | `@!letter-points!@` = `A`, `@!letter-does-not-point!@` = `B` | — |
| item | `@!dyn.candidate-line!@`, `@!dyn.candidate-text!@` | the target: `_claim_line`, `classify.statements` |
| item | `@!correction!@` | `None` or `letter-correction` (the existing fragment, unchanged) |

The prose conveys: **A** — the source claim's own words draw on the candidate's result with no
cross-reference. **B** — they do not. The leaf, where shown, is there so the claim's words can be
resolved; a pointer elsewhere in the leaf that the claim's text does not take up is a **B**. The
question asks about the claim's text, not whether the two claims are related. The slot-order and
shared-prefix tests already run over every `letters.Kind`: in
`kb_tools/tests/test_kb_claimgraph_ask.py`, `rg -n 'parametrize\("kind", list\(letters.Kind\)\)'`
returned three tests on 2026-10-03, so they cover this kind once it composes.

### U2. The exception considered and declined: a list ask

One ask per source could list its `K` targets and take several letters back: 197 asks on ModernCorp
at any K, against 197·K (985 at K = 5, 2,955 at K = 15). It is declined:

- It breaks `kb_tools/SPEC.md`'s "every claim-graph inference is one decision, answered by one
  label" (The Driver's Contract).
- It reintroduces the compound answer the letter asks removed: an answer partly wrong has no
  item-level default.
- The per-label classifier seam (`letters.LetterReader`'s `confidence`) has no multi-label form.

It returns only through owner decision 3. If parked instead, it goes in `kb_tools/ROADMAP.md` (R3),
with its measured trade.

### U3. The shortlist — the mechanical draft gap 2's inference refines

- **The pool for source `s`** is every node of the build other than `s`, less every pair whose
  unordered form `attribute.narrow` already returns as a candidate. Sources are every node that is
  not a minted equation: an equation is a sink and has no body. Targets include equation nodes.
  Nothing branches on kind here; classification offers an equation target `A`/`C` as it does today.
- **No locality filter.** No document, section, paper or reading-order bound enters the pool (I14).
- **Rank** by cosine similarity of TF-IDF vectors between `s`'s text and each target's statement,
  IDF computed over the target statements, ties to the lower target id; take the top `K`. `K` is one
  named constant in `shortlist.py`. **Its value and the ranking are owner decision 1**; the
  recommendation is wm/statement at K = 5.
- **Tokens (wm):** words from `kb_write.ops.canonical_form`, the incumbent fold. It drops maths, so
  maths symbols are added from inline spans and display fences — inline spans through `kb_links`'s
  inline-maths pattern, made public; fences through `Inventory.fences`. The source side is the
  statement alone unless decision 1 picks a `+leaf` variant.
- **The production ranking is the one measured.** Once R2 lands, the measurement script ranks
  through `shortlist.py` rather than its own copy, so the curve it prints describes the stage.
- **Deterministic by construction** (I13). The stage computes the shortlist once and records it;
  `depends-attributed` never recomputes it (I18).
- **Scope, argued against `kb_tools/THESIS.md`** (standing rule 3): "Inference refines a mechanical
  draft. It never produces one." Asking all pairs would have inference produce gap 2's candidate set
  from nothing; the shortlist is the draft and the ask judges it. What the narrowing costs is the
  pairs ranked below `K`, about which nobody is asked (`kb_tools/AGENTS.md`, "Inference is
  downstream of the odds"). R1 measured that cost against the 42 misses and against all pairs
  (Evidence 1).

### U4. Default: no candidate

A pair whose ask and single re-ask return no offered letter is recorded `defaulted` and yields no
candidate. This is not declining to record (standing rule 2): a similarity score is not evidence
that the text points anywhere, and without a reading the pair is in the state every pair outside the
shortlist is in — the same argument that makes a defaulted paragraph unjudged. If the default were
`A`, an unread pair would enter the graph as a `references` edge through classification's *mention*
draft.

### U5. The stage, its record and resume

- **Stage `references-found`** (owner decision 4), display "unmarked references found", between
  `equations-minted` and `depends-attributed`: after the node set is fixed and before harvest
  completes. `work_is_inference=True`, `mints_nodes=False`. Invocation
  `ClaimgraphInvocation(which_pass=2, scope=CLAIMGRAPH_SCOPE_UNMARKED)`; `__main__` accepts a scope
  on pass 2. Steps `unmarked.build` (`spends_own_inference=True`) and `unmarked.record`
  (`ADVANCE_STEP`), on the pattern of `discover.build` / `discover.record` in
  `kb_tools/kb_driver/steps.py`. A stage of its own because SPEC puts a boundary behind every step
  that spends inference (What this builds on).
- **Record `kb_pipeline.UNMARKED_RELPATH`** = `kb-build-unmarked.json` at the repo root. Reader and
  writer are `kb_pipeline`'s, with the node-pass record's placement and import direction. It holds
  the planned shortlist (ordered pairs), written before the first ask; and per pair the offered
  letters, the letter or null, and the outcome (`answered` / `re-asked` / `defaulted`).
  - The per-pair entry has `kb_pipeline.CandidateEntry`'s shape: **one pair-keyed letter-record
    codec, two paths** — not a second copy of `write_classification` / `read_classification`.
  - Written atomically after each source group. The declared pass writes it empty, beside its
    `kb_pipeline.write_classification(repo_root, kb_pipeline.ClassificationRecord())` in
    `kb_claimgraph/build.py`, so a record an earlier build left is never read. Kept at the build's
    end.
- **Resume** asks only shortlisted pairs the record does not hold. An answered pair stays valid even
  if a later toolchain shortlists differently: the answer is a fact about the text, so
  `depends-attributed` reads every `A` in the record.
- **Exit** (standing rule 4): the stage recomputes the shortlist and compares it with the record;
  every shortlisted pair must carry an outcome. Ledger coverage takes
  `kb_pipeline._check_claims_discovered`'s shape: no planned pair without an outcome,
  `asserts_own_work=True`, so `--no-inference` excuses it.
- **`--no-inference`**: the build row is dropped and the record stays as the declared pass wrote it,
  empty. `depends-attributed` then sees no unmarked candidate (I12).

### U6. Joining classification

- `attribute.Harvest` gains `UNMARKED = "unmarked"`. Report counts read it and nothing else (I17).
- `narrow(..., unmarked: Iterable[tuple[str, str]] = ())`: each recorded `A` pair is reached with
  `offered = OFFERED[_class_of(directed=False, target=t)]` — claim to claim `A`/`B`/`C`, equation
  target `A`/`C`. Its passage is `_reference_line` at `(s.document, first line of s's body)`, using
  `hand_named.bodies`' first line — the claim's own paragraph, because a yes cites the claim's text.
  Draft: *mention*.
- `depends.py` reads the record's `A` pairs and hands them to `narrow`. The existing
  `stage-D-candidates` line already counts by harvest.
- A merge with a reference or hand-named provenance of the same pair is the generic merge path.
  U3's exclusion means it does not occur in practice, and no code checks for it.

### U7. Report lines (zero form)

- Shortlist: sources, `K`, pairs planned, pairs excluded as existing candidates.
- `letters.AskTotals` over the stage's groups.
- Yeses: count, and by locality of the pair (same document / same directory / same paper / cross
  paper) — the figure R5 reads.
- Every defaulted pair, by name.

## Ask counts

Per call: **3.1 s** median at `W = 1` with no prefix reuse, and **1.16–1.35 calls per ask** for
re-asks (the baseline build; Where the stage is). The cost is per call, not per prompt token: the
node pass's asks carry whole leaves at a median of 3.08 s, the classify asks carry none at 3.36 s,
so a shorter prompt saves nothing measurable.

**ModernCorp** (R1, `.claude-temp/unmarked-shortlist/roots.tsv`): 223 nodes (171 prose, 26 block,
26 equation), so 197 sources; 72 existing candidates, which take 93 ordered pairs out of the pool.
Every source's pool exceeds 50 targets, so top-K is exactly 197·K. Each unit of `K` is 197 asks,
≈ 12–17 minutes.

| Scope | Asks | Hours at 3.1 s | Misses reachable |
|---|---|---|---|
| All pairs | 43,641 | 37.6 | 42 / 42 |
| All pairs within one paper | 7,497 | 6.5 | 22 / 42 |
| All pairs within one directory | 2,431 | 2.1 | 11 / 42 |
| All pairs within one document | 439 | 0.4 | 3 / 42 |
| Top-K, K = 5 | 985 | 0.8 | 9–15 / 13–20 (range over the four rankings, Evidence 1) |
| Top-K, K = 8 | 1,576 | 1.4 | 13–20 / 16–24 |
| Top-K, K = 15 | 2,955 | 2.5 | 21–26 / 25–30 |

Ranking beats locality at every budget: top-K at K = 8 reaches up to 24 misses for 1,576 asks;
every pair within one paper reaches 22 for 7,497.

**arXiv-50** is fifty separate builds, one KB per paper (`no-inference-kb-driver-arxiv-paper` in
`kb-testing/justfile`), so pairs never cross papers there. It was not staged when R1 ran, and its
per-root figures are unmeasured; R1's script prints them once `stage-arxiv-corpus` and
`no-inference-kb-driver-arxiv-corpus` have restaged it (R5).

## Evidence — what was measured, and how to re-run it

**1. The shortlist's recall curve (R1).** `kb-testing/tools/measure-unmarked-shortlist.py`,
read-only, run as

```
just -f kb-testing/justfile measure-kb-roots tools/measure-unmarked-shortlist.py
```

It reads every handed kb-root through production code (`tree.read` → `inventory.scan` →
`graph.read` → `classify.statements`, `attribute.narrow` over the node-pass record) and writes
`roots.tsv`, `misses.tsv`, `curve.tsv` and `summary.md` under `.claude-temp/unmarked-shortlist/`.
"Reached" means some ordered pair `(s, t)`, `s` among a miss's matched sources and `t` among its
matched targets (`.claude-temp/pristine-compare/edges.tsv`), is on `s`'s shortlist: the ceiling the
stage can deliver on that miss, not a yes and not a recovery. Misses reached on ModernCorp, forward
/ either direction:

| K | Asks | Hours at 3.1 s | c9/statement | c9/statement+leaf | wm/statement | wm/statement+leaf |
|---|---|---|---|---|---|---|
| 1 | 197 | 0.2 | 1 / 5 | 0 / 3 | 4 / 6 | 2 / 4 |
| 2 | 394 | 0.3 | 5 / 8 | 4 / 6 | 6 / 8 | 5 / 7 |
| 3 | 591 | 0.5 | 7 / 10 | 6 / 9 | 7 / 10 | 7 / 9 |
| 5 | 985 | 0.8 | 15 / 20 | 9 / 13 | 13 / 19 | 9 / 14 |
| 8 | 1576 | 1.4 | 20 / 24 | 15 / 20 | 17 / 23 | 13 / 16 |
| 10 | 1970 | 1.7 | 20 / 24 | 19 / 24 | 17 / 24 | 17 / 21 |
| 15 | 2955 | 2.5 | 21 / 26 | 26 / 29 | 26 / 30 | 22 / 25 |
| 20 | 3940 | 3.4 | 24 / 29 | 26 / 30 | 27 / 30 | 28 / 30 |
| 30 | 5910 | 5.1 | 30 / 31 | 29 / 32 | 31 / 33 | 32 / 33 |
| 50 | 9850 | 8.5 | 35 / 37 | 35 / 37 | 35 / 37 | 37 / 39 |

Reading it: the 42 misses are not independent — misses sharing a matched endpoint cross the cutoff
together, so a step of 4–6 can be one target. Differences of 2 or fewer between rankings at one K
are within that. Per-miss ranks for every variant are in `misses.tsv`.

**2. Locality of the 42 unmarked misses**, nearest matched pair (same file, `summary.md`): same
document **3**, same directory **8**, same paper **11**, cross paper **20** — the pristine
comparison's 20 cross / 22 within a paper. Any scope narrower than the corpus gives up the 20 by
construction. The list is in the Appendix.

**3. Shared notation reaches some cross-section misses but is not selective.** Of the six misses
whose target is F-σ2 (our `clm-22w0n0`, which states `\sigma_2 < 1`), three have a source whose body
carries `\sigma_2` (p1bot1 through `clm-123rud` and `clm-s8z7yi`; 4mabb3 through `clm-c0yd98` and
`clm-sbqtiv`; ahxthv through `clm-rk89ar` and `clm-dazj6e`), and three do not (3a3zmf through
`clm-nbn4vj`; xaji0y through `clm-f57sib` and `clm-ziubye`, whose leaf holds the symbol outside both
bodies; 2f8d1t, whose source documents hold none). The symbol occurs in 38 files corpus-wide, so it
is weighted (IDF) rather than matched bare.

**4. A source's leaf carries pointers its body only takes up.** Miss 8350hb → edadyx: the source
`clm-dsmmec` restates "decay is marginal and easy"; the pointer to "the firm-scale healthy-to-zombie
escape of Part 2 … marginal … no exponential barrier" is the preceding paragraph, which is not a
claim. The target body `clm-uuut93` shares the rare terms *Arrhenius*, *zombie* and *logarithmic*.
This is why U1 shows the leaf in the ask (owner decision 2). In the ranking the leaf barely moves
it: that pair ranks 11 under wm/statement and 9 under wm/statement+leaf, and neither `+leaf`
variant leads overall at K ≤ 10. Node-to-document mapping:
`.claude-temp/pristine-compare/ours-nodes.tsv`.

**5. The pristine comparison's matching limits what R5 can show.** 13 of the 42 misses run through a
match scoring at most 0.385 (`.claude-temp/pristine-compare/claim-matches.tsv`): `clm-22w0n0` at
0.301 (six misses), `clm-vef0d0` at 0.301 (two), `clm-761j0u` at 0.385 (five). On those 13, a change
in edge recall measures the match as much as the stage.

**Incumbent search** (2026-10-03):

- *TF-IDF / cosine:* `Grep '(?i)tf-?idf|cosine|idf\b'` over the repository's `*.py` returns
  `kb-testing/tools/compare-to-pristine.py` and R1's script, nothing else. Production cannot import
  `kb-testing/`, so `shortlist.py` carries the weighting — about a dozen lines.
- *Word fold:* `kb_write.ops.canonical_form`. It drops maths.
- *Inline maths:* three private copies exist — `kb_links._INLINE_MATH_RE`,
  `kb_docgraph/text.py` `_MATH_SPAN`, `kb_docgraph/partition.py` `_INLINE_MATH`. `kb_claimgraph`
  already imports `kb_links` (`kb_claimgraph/tree.py`, `from .. import kb_index_lib, kb_links`). The
  stage uses that one, made public, and adds no fourth. R1's script holds its own copies of the
  inline and fence patterns; R2 deletes them. Collapsing the two `kb_docgraph` copies is a separate
  bug fix, not this plan's.
- *Display fences:* `Inventory.fences`. *Leaf render:* `identify.reading_of`. *Statement:*
  `classify.statements`.

## Standing measurement: the pristine comparison

**Re-run after each change that moves nodes or edges; not chased.** It measures the build against
`ModernCorpPristine`'s KB, the author's own hand-refined graph — a reference for direction, not a
score to maximise. Claim recall: each author claim matched to our nodes by statement text (TF-IDF
over title + statement, threshold 0.3), one-to-many allowed, matches listed. Edge recall: per author
edge, our `depends` edge, a `depends` path, a `references` edge only, or nothing. Misses split three
ways: marked in the text the pipeline reads (pipeline miss), stated only in prose (this plan's
target), not carried by the text (unreachable, reported as such); the first split is mechanical.

- **Tool:** `kb-testing/tools/compare-to-pristine.py` through `measure-kb-roots`, outputs to
  `.claude-temp/pristine-compare/`.
- **Baseline:** the baseline build's figures in Where the stage is.
- **Each re-run** reports the numbers and the per-claim and per-edge tables against the previous
  baseline.

## Contract-document changes (land with the rows named)

**`kb_tools/SPEC.md`** (R2):

- *Claim-Graph Nodes and Edges*, the first `references` property ("Direction comes from the markup,
  not from judgement"). After the hand-named sentence, add: a claim whose text points at another
  claim's result with neither cross-reference markup nor a printed name — by description,
  restatement, or that claim's own notation — is a reference too, **where a build's reading finds
  it**. The build proposes such pairs mechanically, asks of each whether the source's text points at
  the target, and records a candidate only for a yes; its source is the claim whose text was read.
  Then scope "Nothing infers it and nothing is asked about it" to references the markup or a printed
  name carries.
- *Every edge candidate is classified*: no change; "however the build found it" already covers this.
- *The Driver's Contract*, "Every claim-graph inference is one decision …": the defaults gain "a
  pair proposed as an unmarked reference is not one".

**`kb_tools/ARCHITECTURE.md`**:

- The `kb_claimgraph/` row of the Module Inventory and The Claim Graph intro: "four invocations"
  becomes five, adding `--pass 2 --scope unmarked` (R2).
- Every stage enumeration naming `depends-attributed` gains `references-found` (R2).
  `rg -n 'depends-attributed' kb_tools/ARCHITECTURE.md` returned 9 lines on 2026-10-03; the
  enumerations are among them.
- "The discovered graph is a lower bound by construction": a dependency never cross-referenced is
  visible only where the shortlist proposes it (R2).
- Module rows: new `shortlist.py` and `unmarked.py`; `ask.py` and `letters.py` (third kind);
  `kb_pipeline.py` (record, stage) (R2); `attribute.py` and `depends.py` (the unmarked harvest)
  (R3).

**`kb_tools/CONVENTIONS.md`** (R4): the byte-exactness pin list in "A caller-selected alternative
ends without a newline" gains the `unmarked.tmpl.md` pin.

**`kb_tools/ROADMAP.md`** (R3): the list ask (U2), parked with its measured trade, unless owner
decision 3 adopted it.

No root contract document changes.

## Invariants and the failure modes they prevent

Carried from the letter asks and classification, and binding on the new kind:

1. **Every byte before an ask's question section is identical across its group.** *Prevents:*
   per-item text drifting forward and turning every ask into a full prefill. *Held by:* the
   slot-order and shared-prefix tests (`test_kb_claimgraph_ask.py`) and the cache share on every
   stage report.
2. **No per-call content enters ahead of the prompt.** *Prevents:* a hook's timestamp defeating the
   cache. *Held by:* `disableAllHooks` in the reader's settings, and the reported cache share.
3. **One letter→meaning table per kind; subsets withhold letters, never rename them.** *Prevents:*
   `B` meaning one thing in one ask and another in the next.
4. **Every item ends with exactly one recorded outcome — answered, re-asked or defaulted — and a
   malformed reply never stops a stage.** *Prevents:* a build lost on one unread pair.
5. **Concurrency changes nothing that is written.** Results keyed by item, landed in item order,
   records sorted. *Prevents:* different records between two runs with the same answers.
6. **The model is the seat's pin, reached through `claude -p` alone.** No claim-graph code names a
   model, a server URL or a sampling parameter. *Prevents:* a second route to the model growing back
   for one control. *Held by:* one `LetterReader`, built on `seat.ask_reader`.
7. **Thinking-off is observed on every build, not assumed.** Every stage report counts thinking
   blocks and output tokens over its asks, in the zero form. *Prevents:* the build quietly
   returning to hours of reasoning.
8. **The first ask of a group completes before the rest are issued.** *Prevents:* `W` concurrent
   cold prefills of one prefix.
9. **A stage exits only on a comparison or a return code.** No letter decides whether a stage
   succeeded.
10. **Every candidate reaching classification has `offered ⊇ {supported-by, mention}` and `draft ∈
    offered`.** *Prevents:* an empty intersection after a merge, or a default never offered.
11. **No `depends` edge originates at an equation node, each candidate yields exactly one record,
    and the class is a function of the pair's facts** — never of its harvest. *Prevents:* a
    provably wrong edge out of a sink; one pair offered different letters by two harvests.
12. **With an empty unmarked record — `--no-inference`, or no `A` answered — `depends` and
    `references` per kb-root are identical to a build without the stage.** *Prevents:* the join
    changing anything but what a yes adds. *Held by:* R3's done-when.

New with this plan:

13. **The shortlist is a pure function of the tree and the fixed node set** — no model, clock or
    iteration order — and ties break on target id. *Prevents:* a resume asking a different pair
    set. *Held by:* a test computing it twice, once over a permuted node order.
14. **The pool is every node but the source, less existing-candidate pairs. No document, section,
    paper or reading-order filter enters it.** *Prevents:* a cheap local scope silently cutting the
    20 cross-paper misses. *Held by:* a fixture whose best-ranked target is in another volume and
    earlier in reading order.
15. **An unmarked ask decides existence only.** Classification asks every yes exactly as it asks any
    other candidate. *Prevents:* gaps 2 and 3 merging into one ask whose direction the
    classification record never holds.
16. **Only `A` yields a candidate.** `B` and `defaulted` yield none, and each is recorded.
    *Prevents:* unread pairs entering the graph through *mention* drafts.
17. **`Harvest.UNMARKED` is read by report counts alone.** Class, offered letters and draft come
    from the pair (I11). *Prevents:* per-harvest letter sets.
18. **Every shortlisted pair carries one recorded outcome before the stage exits, and
    `depends-attributed` reads unmarked candidates from the record only.** *Prevents:* a second
    shortlist computation disagreeing with the first.

**Failure modes a coder is likely to hit:**

- Recomputing the shortlist in `depends.py` (I18).
- Writing the score's maths tokens with a fourth inline-maths regex.
- Putting a per-item slot (the target) ahead of the leaf body; the slot-order test catches it.
- Defaulting to `A` (I16).
- Branching `offered` on `Harvest.UNMARKED` (I17).
- Forgetting the declared pass's empty record, so `--no-inference` reads a stale one.
- Treating pass 1 as the only scope-bearing pass in `__main__`.
- Leaving the measurement script on its own ranking copy after R2, so the curve stops describing
  the stage.

## Module skeleton

| Module | Owns | Must not |
|---|---|---|
| `kb_claimgraph/shortlist.py` (new) | tokens (`canonical_form` words + maths symbols), TF-IDF over target statements, per-source top-K over the pool, `K` | ask, record, read `Harvest`, filter by locality |
| `kb_claimgraph/unmarked.py` (new) | the stage pipeline: entry gate (`conform.pass_two_gate`), inventory, graph, `narrow` (for exclusions), shortlist, the plan in the record, groups via `letters.ask_group`, the record per group, exit comparison, report | classify, write under `kb-root/`, mint |
| `ask.py` / `letters.py` | `unmarked_asks`, `UnmarkedLetter`, slots / `Kind.UNMARKED` | decide (`ask.py`); know the kind's meaning (`letters.py`) |
| `kb_pipeline.py` | stage row, invocation, scope constant, `UNMARKED_RELPATH`, the shared pair-letter record codec, coverage | import `kb_claimgraph` |
| `attribute.py` / `depends.py` | `Harvest.UNMARKED`, `narrow`'s `unmarked=` / reading the record's `A` pairs | branch on harvest |

Dependency direction: `unmarked` → `shortlist`, `ask`, `letters`, `attribute`, `classify`
(`statements`), `identify` (`reading_of`), and `kb_pipeline` for the record. `shortlist` imports
`kb_links`, `kb_write.ops` and `inventory` only.

## Rows

| Row | What | Seat | Files owned | Blocked on | Done when |
|---|---|---|---|---|---|
| **R1** | **Landed.** The shortlist's measured curve over ModernCorp: locality ceilings, misses reached per K for four rankings forward and either direction, asks per K per root. | PC (run) | `kb-testing/tools/measure-unmarked-shortlist.py` | — | Evidence 1 and 2 carry its output; arXiv-50 figures follow its restage (R5) |
| **R2** | The stage (U1, U3–U5, U7). `shortlist.py`; `unmarked.py`; `ask.unmarked_asks`, `UnmarkedLetter`, `Kind.UNMARKED`; functional `unmarked.tmpl.md`; `kb_links` inline-maths pattern made public; `kb_pipeline` stage, invocation, record (shared codec with the classification record), coverage; `build.py` writes the empty record; `steps.py` two rows; `__main__` pass-2 scope. The measurement script ranks through `shortlist.py`, its own tokenizers, weighting and maths patterns deleted, and its `SECONDS_PER_ASK` comment cites the measured figure rather than a plan. SPEC `references` property and Driver's-Contract default; ARCHITECTURE intro, stage enumerations, lower-bound paragraph, module rows. | PC | `kb_tools/kb_claimgraph/{shortlist,unmarked,ask,letters,build,__main__}.py`, `kb_tools/kb_links.py` (that name), `kb_tools/kb_pipeline.py`, `kb_tools/kb_driver/steps.py`, `kb_tools/kb_driver/prompt-templates/unmarked.tmpl.md`, `kb_tools/kb_driver/prompt_templates.py` (if the registry needs it), `kb_tools/tests/test_kb_claimgraph_{unmarked,ask}.py`, `kb_tools/tests/test_kb_pipeline.py`, `kb_tools/tests/test_kb_driver_steps.py`, `kb-testing/tools/measure-unmarked-shortlist.py`, `kb_tools/{SPEC,ARCHITECTURE}.md` (those parts) | Owner decisions 1, 2, 4 | `just test` green. The slot-order and shared-prefix tests pass for `unmarked`. Over a fixed reader: the shortlist is identical twice and over a permuted node order (I13); a cross-volume, earlier-in-reading-order target is shortlisted (I14); pairs already candidates are not; `B` and defaulted pairs are recorded and yield nothing; a stop after group *k* resumes asking from group *k+1*; `--no-inference` drops the row and leaves the record empty; the stage table keeps `mints_nodes` contiguous, ending at `equations-minted`. The script, re-run through `measure-kb-roots`, prints the production ranking's reach at the chosen K beside R1's figure for that variant, naming any miss that moved |
| **R3** | The join (U6). `Harvest.UNMARKED`; `narrow`'s `unmarked=`; `depends.py` reads the record's `A` pairs; ARCHITECTURE `attribute`/`depends` rows; ROADMAP list-ask entry. | PC | `kb_tools/kb_claimgraph/{attribute,depends}.py`, `kb_tools/tests/test_kb_claimgraph_pass2.py`, `kb-testing/tools/measure-letter-asks.py` (by-harvest counts), `kb_tools/{ARCHITECTURE,ROADMAP}.md` (those parts) | R2 | `just test` green. An `A` pair becomes a candidate offered its class's letters, drafted *mention*, its passage the source's first paragraph, and counted under `unmarked` on `stage-D-candidates`; a claim-to-claim one answered `B` writes target → source. With an empty record, `measure-letter-asks.py` over every staged root shows `depends` and `references` identical to before (I12) |
| **R4** | Template prose. PE rewrites `unmarked.tmpl.md` against U1's interface, against the baseline's re-ask cause: the model reasoning in prose before its letter. PC pins byte-exactness (first ask and re-ask). | PE, then PC for the pin | `kb_tools/kb_driver/prompt-templates/unmarked.tmpl.md`; the pin in `kb_tools/tests/test_kb_claimgraph_unmarked.py`; `kb_tools/CONVENTIONS.md` pin list | R2 | Pins pass; slot-order test passes; PE's report records the prompt read end to end |
| **R5** | The owner's measure. ModernCorp built as the baseline was (`just -f kb-testing/justfile kb-driver-fixture test-data/transient/ModernCorp <local-inference env>`, `KB_READER_CONCURRENCY=1`), to completion, wall time recorded. Report: the stage's asks, re-asks, yeses by locality, defaults, seconds per call, added wall time; classification's added asks and the relations unmarked candidates took; then the pristine comparison, with the 42 misses split by reached / answered yes / recovered, read against R1's ceiling and Evidence 5. Then R1's script over a restaged arXiv-50 (`stage-arxiv-corpus`, `no-inference-kb-driver-arxiv-corpus`) for its per-root ask counts. | PC (run), owner (judge) | report; the active plan's Where the stage is | R2, R3, R4 | The build completes with zero thinking blocks; the stage reports, the pristine comparison and arXiv-50's ask counts are in the landing report, citing each script by path |

## Order

- **The owner's decisions 1, 2 and 4**, then **R2 → R3**. R4's prose may start once R2 lands the
  functional template; its pin follows R2.
- **R5** last, then the pristine comparison over its build.

## Deliberately not specified

- The TF-IDF variant's exact weighting beyond "IDF over target statements", provided R2's re-run
  states the production ranking's reach against R1's.
- The maths-symbol grammar beyond "identifiers from inline and display maths".
- Record field names; report line names.
- Whether `shortlist.py` and `unmarked.py` are one module. Two is suggested, so the mechanical half
  is testable with no reader.
- The template's prose.

## Out of scope

- **A locality-scoped pool** (I14).
- **The list ask**, unless owner decision 3 adopts it.
- **A transport to the model other than `claude -p` on the seat's pin** (I6), and any sampling
  control it would carry.
- **A per-label classifier read**: the seam takes one; none is built or configured.
- **Directing an open pair mechanically.** Direction is classification's question.
- **Any stage that asks a model whether the work is good enough** (standing rule 4).
- **Collapsing the two `kb_docgraph` inline-maths copies** — a separate bug fix.
- **Definitions as nodes, and claims using a defined term as candidates for depending on them** —
  parked: both halves land together or neither; revisit on a corpus where definitions carry the
  dependency weight. Detail and scope: `kb_tools/ROADMAP.md` item 12.
- **Rendering.** `ROADMAP_PLANS/CLAIM_GRAPH_LEGIBILITY_PLAN.md`.

## Appendix — the 42 unmarked misses by nearest-pair locality

Pristine ids, source → target (`.claude-temp/pristine-compare/edges.tsv`; per-miss ranks in
`.claude-temp/unmarked-shortlist/misses.tsv`).

- **Same document (3):** 3a3zmf→8mdd4v, 4vvyit→070eop, xswnie→070eop.
- **Same directory (8):** 0btn32→4mabb3, 3a3zmf→6dpbhs, 4mabb3→fsig2a, ahxthv→6dpbhs, ahxthv→xaji0y,
  p1bot1→fsig2a, rbu4fq→ge7d9n, se74eq→0btn32.
- **Same paper (11):** 1xvw8e→2f8d1t, 1xvw8e→no9kuq, 51c08a→no9kuq, 5q33sr→no9kuq, 8350hb→2f8d1t,
  edadyx→6y9evs, f58f7y→rbu4fq, p274z2→5q33sr, p274z2→ifdgf7, p2sen1→p2brc1, rm0s46→070eop.
- **Cross paper (20):** 070eop→se74eq, 0btn32→ge7d9n, 2f8d1t→6y9evs, 2f8d1t→ahxthv, 2f8d1t→fsig2a,
  3a3zmf→0btn32, 3a3zmf→6y9evs, 3a3zmf→fatta1, 3a3zmf→fsig2a, 6y9evs→se74eq, 8350hb→6y9evs,
  8350hb→edadyx, 8mdd4v→fatta1, ahxthv→fsig2a, ifdgf7→6y9evs, m3u77v→se74eq, no9kuq→6y9evs,
  p2fi1a→se74eq, rbu4fq→4mabb3, xaji0y→fsig2a.
