# CLAIM_GRAPH_CONSTRUCTION_PLAN.md — the edges a corpus states and this stage does not find

**Paths** are repository-root-relative. The stage lives at `kb_tools/kb_claimgraph/`.

**Seat.** **AR** architect for a change to the stage table; **PC** python-coder; **PE**
prompt-engineer for anything under `kb_driver/prompt-templates/`. Nothing here is a contract-doc
change unless a row says so.

**Bold marks a decision the row itself must make and record.** It is not emphasis.

**What travels with a dispatched row**: this header, the Standing rules, the Where the stage is
section, the row, and the rows it is blocked on. The Order section does not travel.

## What produced this

Rendering is pinned, not abandoned — its plan is `ROADMAP_PLANS/CLAIM_GRAPH_LEGIBILITY_PLAN.md` and
its rows are ready to run. The sheet is legible enough to show someone as unfinished. A graph that
records a claim resting on nothing when the corpus says otherwise is the more expensive defect,
because every consumer downstream — solidity, the orphan block, the sheet itself — reads that
silence as a fact.

**This plan is not about making the mechanical stage guess.** Where it declines to direct an edge,
the markup does not settle the direction: a reference inside a claim's text establishes that one
claim names the other, not whether it uses it or which way dependence runs. It writes the
`references` edge either way, carried on `ClaimEntry.references` rather than `depends_on`, entering
no solidity computation and still being put to the model. Nothing is discarded there.

**The rebuild that established the figures above is done.** It replaced a fixture whose installed
toolchain predated a whole build stage; the claim count more than doubled and the equation route
appeared. What survived the rebuild is the subject of this plan. `stage-fixture`
(`kb-testing/justfile`) restages a consumer with a fresh install of the current agent set, so a
fixture cannot again run code older than the tree.

**C3 and C4 below carry figures taken before it**, from `kb_tools/ROADMAP.md` item 12 and from a
50-paper arXiv survey. Neither has been re-measured against a current build, and a row that acts on
one re-takes it first.

## Where the stage is

Measured over `ModernCorp` rebuilt on the current toolchain, `--no-inference`. The figures that
preceded this rebuild described a fixture whose installed toolchain predated
`kb_claimgraph/equation.py` by six days; they are void.

    62 nodes    26 block-hosted claims, 34 minted equations, 2 works
    50 edges    44 references, 4 depends, 2 rests-on
    243 anchors, 80 of type eqref — 64 in prose with no hosting block, 16 in a claim block

**Mechanical extraction is complete for this corpus.** Direction has one source: an anchor inside a
`proof` bound to the claim it proves. Seven proof environments yield ten anchors, less two proof
heads and three targets resolving to no node, less one duplicate — four edges. Nothing is lost
between the corpus and the graph.

`ModernCorpDerivations.tex` is the tell: 325 lines of derivation across fourteen prose sections and
zero proof environments. The corpus states its derivations as prose, and prose carries no direction
a parser can read.

A minted equation node is a **sink** — a stub standing for a labelled fence, with no body from which
anything could originate. Zero of the 24 edges touching one originate from it. So for an equation
target, direction is settled by the representation and only existence is open.

Under `--no-inference` the `claims-discovered` stage is refused outright, and `depends-attributed`
runs with no selector. Four is therefore the complete mechanical output, not a shortfall against
one.

## Standing rules — on every row, not restated per row

1. **Best odds where certainty is not available; never provably wrong where it is**
   (`kb_tools/AGENTS.md`). A mechanical rule that is usually right earns its place; the alternative
   to a rule that sometimes misfires is no rule and no result.
2. **Declining to record a relationship is not the cautious option.** It leaves the graph asserting
   the claim rests on nothing — a different wrong answer, arrived at silently, which no later pass
   is prompted to revisit.
3. **A row that narrows or widens an inference step argues its scope against `kb_tools/THESIS.md`,
   in the report that lands it** (`kb_tools/CONVENTIONS.md`).
4. **No stage exits on a model's opinion.** Every stage exits on a comparison between two artifacts
   or a subprocess return code; a new stage does not get to add a third kind.
5. **No prompt reaches a model from a heredoc or an in-code string.** Every prompt is a template
   under `kb_driver/prompt-templates/`, and a change to one is the prompt-engineer's seat, not a
   coder's.
6. **A row reports its figure over a real narrowing**, not over a grep of built leaves: `tree.read`
   → `inventory.scan` → `graph.read` → `attribute.narrow`, read-only, through `measure-kb-roots`
   (`kb-testing/justfile`), citing the script by path.
7. **Before and after on the same corpus**, with the edge counts split by relation. A row that moves
   `depends` reports what it moved from `references`, since an upgrade is not a new fact.
8. `just test` green at handoff. `kb-testing/test-data/transient/` is read-only — copy rather than
   write. Scratch under `.claude-temp/`. Never `/tmp`.

## The build's claim-graph order

Three phases, each finishing before the next begins. The rows below each belong to one.

1. **Nodes.** One node-finding pass decides every node the build will have. Claims marked by
   environments, equations and definitions come in mechanically. Prose that holds a reference and
   sits in no block that minted a claim is evaluated for claimhood, in the same pass as claim
   discovery and nowhere else. At the end of the pass the node set is fixed until the build ends.
2. **Edge candidates**, from the fixed node set only:
   - every mechanical reference whose source text belongs to a node;
   - a reference inside text judged not to be a claim is dropped;
   - C4 filters targets no premise relation can hold;
   - C5 finds hand-numbered mentions mechanically;
   - C7 finds unmarked prose references by inference, within the bodies of established claims.
3. **Classification.** Every candidate, however it was harvested, is classified as mention,
   supported by or in support of (THESIS gap 3).

## Rows

| Row | What | Blocked on | Done when |
|---|---|---|---|
| **C2** | **Landed.** With inference on ModernCorp (Qwen3.8-Flash-Next): 567 nodes (509 prose claims), 295 edges (93 `depends`), all 123 obligated paragraphs judged — read with C8's caveat. **The node pass is the one home for claimhood.** Claim discovery (`claims-discovered`) and the claimhood evaluation of reference-bearing prose become a single node-finding pass. It reads the prose outside claim-bearing blocks, proofs and definitions in every document, whether or not the document hosts blocks: THESIS gap 1 is any claim constructed in prose, and discovery's restriction to block-free documents is an artifact of how it was built, not a scope. Every paragraph holding a reference in that prose is guaranteed a verdict. The unit is the paragraph, asked once however many references it holds. Yes mints a claim whose span is the paragraph. No marks the paragraph not-a-claim, and its references are dropped in phase 2. Stated now in `kb_tools/ARCHITECTURE.md`, The Claim Graph: one ask per leaf, a build-owned node-pass record outside `kb-root/` holding verdicts and read state, equation minting as its own stage after the verdicts. Seats: PC for the pass, then PE for its templates against the interface PC records | — | One stage mints every prose claim. Each reference-bearing prose paragraph outside a block has a recorded verdict. The node set is unchanged by any later stage. ModernCorp before and after, nodes by kind (standing rule 7) |
| **C8** | **Landed.** ModernCorp with inference on Qwen3.8-Flash-Next, all ten stages: 245 claim-graph asks (node pass and attribution), every one a single turn with zero tool calls; mean 73 s per ask, almost all of it reasoning tokens (about 5K output against a few-hundred-character verdict); 582 nodes, 261 edges (91 `depends`). **A claim-graph ask is answered from its prompt and nothing else.** The asks are narrow by design: each shows the seat exactly the document and candidates it is to judge. A seat that can run tools reaches past that — reading neighbouring leaves, the LaTeX sources — so its answer depends on what it chose to look at, which varies by run and by model, and the judgment is made on evidence the design excludes. Every `kb_claimgraph` ask therefore runs with no tools. The mechanism keeps the expert bench plug-and-play: the seat's definition body, extracted under the Guest-Extraction Contract, becomes the system prompt (`--system-prompt`, replacing Claude Code's default scaffolding) with a no-tools line appended from a template fragment, and all built-in tools are disabled (`--tools ""`); no `--agent`, so no granted-then-denied tool mismatch reaches the model. `--bare` is opt-in. Seats PC, then PE for the fragment | — | A claim-graph call cannot invoke a tool, established by a test at the invocation seam. A node pass over ModernCorp shows one turn per ask |
| **C9** | **Run once, kept as a baseline; not chased.** First result: 38 of the author's 43 claims matched, 2 of 71 edges recovered as `depends`; misses mostly unmarked in the LaTeX, 13 crossing papers. Script `kb-testing/tools/compare-to-pristine.py`, run through `measure-kb-roots`; outputs to `.claude-temp/pristine-compare/`. Re-run after C6, C7 and C8 land; no per-miss diagnosis until the large gaps are closed. **Measure the build against the author's own graph.** `ModernCorpPristine`'s KB is canonical for that corpus — converted from LaTeX, then hand-refined and hand-expanded by the author, with the LaTeX regenerated from it. Its 43 claims and 71 `depends` edges are a reference for direction, not a score to maximise: reproducing one author's organisation is not the goal. Report claim recall (each author claim matched to our nodes by statement text, one-to-many allowed, matches listed for review) and edge recall (for each author edge: our `depends` edge, a `depends` path, a `references` edge only, or nothing). Split each miss three ways: marked in the text our pipeline reads (a pipeline miss), stated only in prose (C7's recall target), or not carried by the text at all (unreachable by design, reported as such). The first split is mechanical; the second and third need a reading pass. Seat PC for the script | — | The numbers and the per-claim and per-edge tables, through `measure-kb-roots` (standing rule 6) |
| **C6** | **Classification offers each candidate only what the graph can carry.** Every candidate is asked mention / supported by / in support of, with the offered subset chosen in code from the candidate's class before the template is filled. *Source inside a proof* — supported by or mention; containment settles direction, not existence, and these are written as `depends` unasked today. *Equation target* — supported by or mention; an equation is a sink. *Claim to claim* — all three. *Target resolves to no node* — not asked. Supported by writes `depends` source→target; in support of writes it target→source; mention leaves the `references` edge. Carries `ask.py`'s evidence passages, which are sorted and deduplicated so nothing says which candidate a passage bears on. Seats: PC for the classing and subsets, PE for the template | C2 | Each candidate class is offered its own subset. ModernCorp before and after with edges split by relation (standing rule 7). Byte-exactness tests for the answer blocks pass |
| **C7** | **An unmarked prose reference between established claims is found by inference.** THESIS gap 2's inference half: a claim's body leaning on another claim without `\ref` or a printed name. Each claim's body is checked against every other established claim: arguments reach across sections and in both reading orders, so any narrower scope cuts real edges. That is one ask per claim, with the list of all claims shared across the asks and placed first so it caches; context grows with the corpus, call count does not. **The ask itself is not designed** | C2 | Designed before it is dispatched |
| **C3** | **Parked.** Yield measured over 53 kb-roots (arXiv corpus + ModernCorp): 35 definition blocks, 14 titled, 17 labelled; exact title matches give 24 claim→definition candidate pairs over 20 claims in 3 papers, and 2 of the 133 edgeless claim blocks would gain one. Building it needs an id rule for definitions (unnumbered `\newtheorem*`, unstable positional ids — the source label is a new id grammar), a layering move (`kb_index_lib` cannot import `kb_claimgraph.inventory`), and a decision on whether its candidates are asked. Revisit on a corpus where definitions carry the dependency weight. **A definition is a node, and a claim using a defined term is a candidate for depending on it.** Both halves land together or neither: **9 orphaned claims** name a definition as their antecedent with no node for the answer to be, and **15 of 129** claims reach `narrow` with an empty candidate set. Scoped by region — a claim's own *statement block*, never surrounding prose — with rarity across the corpus's claim statements weighting the match. A match produces a **candidate**, never an edge | — | Detail and scope are `kb_tools/ROADMAP.md` item 12, which this row executes rather than restates |
| **C4** | **Landed.** `Anchor.preceding_word`, filtered by `attribute.names_no_premise` (`STRUCTURAL_KINDS` — a fixed list, sectioning units, floats and footnotes being no display name — plus the classified `NOT_A_CLAIM_TARGET` names); applies only where the target fell to a fallback route, never to an identifier or equation route and never to a settled pair. Over 54 kb-roots (`kb-testing/tools/measure-claim-naming.py`): candidates 2238 → 1741 (−497), questions 556 → 519, `references` 2258 → 1761 by the same pairs, `depends` 992 → 992 in every root. ModernCorp 253 → 77 candidates, 73 → 51 questions, `depends` 6 → 6. **The word before an anchor is never captured.** `tree.ANCHOR_RE` takes three attributes and stops; `Anchor` has no field for the rendered text or the noun preceding it. `Lemma`, `Theorem` and `Proposition` name claim-bearing targets; `Figure`, `Table` and `Section` name things no premise relation can hold. **This is a filter, not a director** — it removes candidates that cannot be dependencies, which is cheaper than asking about them and does not touch what containment refuses to direct | — | Candidate count before and after, and the count of questions the narrowing puts to the model. No `depends` edge may appear or disappear |
| **C5** | **Landed; zero candidates on the staged corpora.** `kb_claimgraph/hand_named.py`, carried on `Attribution.hand_named`, neither asked nor recorded. Measured through `kb-testing/tools/measure-claim-naming.py`: 0 candidates in every one of the 50 arXiv papers (49 built, 2609.10514v1 partial) and in ModernCorp (26 block and 525 prose-claim bodies scanned). Corpus-wide, one hand-written name sits inside a node body and it joins nothing. The mentions the raw count found sit in unjudged prose or in proofs, neither a node body, or name a cited work's result — *Theorem 3 of* `\cite{…}` outside the bracket, skipped beside the bracketed form. Proof bodies hold 0 joining mentions. Where a paper numbers within sections, the reader's own counter prints a different number on the display line (*Proposition 1.3* renders *Proposition 17*), so that mention cannot join. **A claim named by hand is an edge candidate.** A mention of a claim by its printed name and number with no `\ref` — "follows directly from Lemma 4.6", "This proves Theorem B" — is THESIS gap 2, found mechanically. A match is a candidate only where it joins: some block in the corpus renders that exact name and number on its display line, or a claim the node pass minted carries it as its title. The claim names are the corpus's own display names, never a fixed list. The number is `(?:[A-Z]\|\d+)(?:\.\d+)*[a-z]?` — any dotted depth, a leading letter for headline and appendix results, a sub-item suffix left uncaptured. List continuations ("Lemmas 2 and 3") yield one candidate each. A match inside a citation span is skipped, so `\cite[Theorem 2.4]{…}` never counts. Scanned only within the bodies of the fixed node set. Candidates only, classified by C6. A raw-source count over the 50-paper arXiv corpus found about 15 internal naked mentions in 4 papers, 2 of them lettered, against 6,144 `\ref`-family uses; the row re-measures through the sanctioned channel. Seat PC | — | Candidate count by paper over the arXiv corpus (standing rule 6). A mention that joins nothing produces nothing, and no `depends` edge appears without C6 |

## Out of scope

**Directing on containment mechanically.** Containment in a claim settles the source end and nothing
about dependence. That question is C6's ask, and the `references` edge is recorded either way.

**Any stage that asks a model whether the work is good enough.** Standing rule 4.

**Rendering.** `ROADMAP_PLANS/CLAIM_GRAPH_LEGIBILITY_PLAN.md`, pinned deliberately.

## Order

**C4 first**, being cheap and independent: it reduces what the model is asked without changing what
the mechanical stage concludes.

**C5 beside C4**: both read the name and number around a reference, one to filter candidates and the
other to find them. Its title join to node-pass claims arrives with C2.

**C8 next, before any further inference run is read for quality.** Until the asks are tool-less, a
verdict may rest on evidence outside its prompt.

**C2, then C6, before any measurement of inference quality.** Until the pairing is readable, a wrong
answer cannot be attributed to the seat rather than to the ask.

**C7 once its ask is designed**, after C2. It only adds candidates, which C6 classifies like any
other, so it may land before or after C6.

**C3 last in delivery**, being the largest and the only one adding a node kind's source. Delivery
order is not pipeline position: its definition nodes join phase 1, its defined-term matches phase 2.

**Open**:
- **Equation minting against the drop rule**, AR's with C2. An equation node is minted because
  something references it. If that reference sits in text judged not a claim, the equation may be
  left with nothing pointing at it: minting follows the claimhood verdicts, or is re-checked against
  them.

**Open and unsettled**: whether a mention should be recorded as the seat's positive judgment rather
than implied by omission from `depends-on`. `references_beyond` already writes the unselected pair
as a `references` edge, so a mention *is* recorded; what is lost is the distinction between "judged
a mention" and "never considered", and with it any completeness check over the candidate set. It is
a JSON-shape change and two byte-exactness test files. Nobody has needed it yet, and C6 makes it
rarer: once every candidate is classified, "never considered" arises only in a `--no-inference`
build, whose ledger already names the steps it dropped.
