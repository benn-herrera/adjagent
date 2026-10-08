# Build-process changes since the last hand-offs — hand-off to kb_tools

For the kb_tools session. Two changes to the claim-graph build landed in kbase this week, each a
named divergence in kbase `SPEC.md` §4 until kb_tools adopts it, and one measurement finding that
decides what not to build. Sources: kbase `SPEC.md` §4 and §5, `ARCHITECTURE.md` §4 and §12, and
the measurement verdicts under kbase's `.claude-temp/n4/build-verdict.md` (not tracked; the
numbers are repeated here). Earlier hand-offs still open on this side: the build inputs on the
commit trail (`KB_BUILD_INPUTS_HANDOFF.md`).

## 1. The unmarked shortlist is a split budget

`references-found` plans, per source claim, its best four prose or equation candidates by the
existing TF-IDF cosine ranking over statement text, after dropping the source's own equations;
and, where the source is itself a block claim (a theorem-like environment, kb_tools'
`hand_named._block_claims`), its best four block candidates besides, recorded before the rest.
Two constants, `shortlistRestK = 4` and `shortlistBlockK = 4`, replace the single K = 5. The
ranking function is unchanged; only the selection after ranking changes. The pool was already
every node, cross-paper included.

Why: on the fixture the author's true premises are block claims ranked 14–233 in their source's
cosine list, out of reach at K = 5. Measured offline over kb_tools' own `shortlist.rank` (kbase
`tools/measure/sweep_shortlist.py`): of 25 author edges the build missed, today's top five reach
4 at 1,485 asks; blocks-first at five reaches 11 but loses half the edges the build recovers
through prose targets; the split offered only to block sources reaches 8, loses none, at 1,292
asks. A Flash-Next build with it recovered the same 16 author edges as the K = 5 build at 15 %
fewer asks, with four misses moved from nothing to a path or a references-only edge.

kbase's live compat check (`kbtools-shortlist` in its justfile) applies the same split to
kb_tools' `shortlist.rank` output before comparing planned pairs; when kb_tools' `unmarked.plan`
does it natively, that reordering comes out and the SPEC §4 row closes.

## 2. An unmarked yes lands as a depends edge with no attribution ask

A candidate born of an unmarked-reference `A` — "the source claim leans on the candidate" — is
not put to the attribution (`depends-attributed`) ask. It lands as a `depends` edge from source to
target, exactly as an answered *supported by* does: same edge, same `inferred` origin on a cut,
same cycle demotion. The classification record holds it as `offered: [A]`, `letter: A`,
`outcome: answered`, `confidence: null` — a shape kb_tools' reader already accepts as a settled
answer mapping to supported-by (`kb_pipeline.ClassifyOutcome`, `classify._held`, `_relation`),
so no reader change is needed to consume kbase's records. Proof-directed, equation-target and
claim-to-claim candidates keep their offers.

Why: the yes already carries the direction, and re-deciding it three ways is a second chance to
be wrong. Flash-Next's re-ask agreed with its own yes 78 % of the time (244 of 311 yeses;
41 in-support-of, 26 mention); the smaller models answered the re-ask a third each and reversed
author edges the yes had got right. Measured on Flash-Next builds of the same fixture: 19 of the
author's 71 edges recovered against 16 with the re-ask, the three edges attribution had been
demoting to `references` now `depends`, and the attribution stage spending 81 asks instead of
347.

kbase's compat harness needed no tolerance: every compat recipe builds `--no-inference`, where no
unmarked yes exists. Adopting the rule in `classify.py` closes the SPEC §4 row.

## 3. What was measured and not built: the hit list

The uncertainty-pool design (kbase `ROADMAP_PLANS/UNCERTAINTY_POOL_AND_HIT_LIST.md`) was measured
before building (kbase `tools/measure/measure_pool_yield.py`). On the fixture, the categories the
build declares — `demoted` rows, `references` rows, defaulted pairs — contain none of the author's
47 missed edges; the claim categories (pending score with nothing supporting it; depending on
nothing) catch half of them but are each half the KB, since no scoring pass has run. A near-miss
pool from the cosine ranking catches 4 of 18 reachable misses at ten pairs per source and 17 at
forty, which is 11,179 pairs over 316 claims. The hit-list query is therefore not built; it waits
on a scoring pass and on a ranking signal that puts the author's premises near the top, which is
what the planned classifier asks are for. Nothing in this section asks anything of kb_tools; it
is here so the two toolchains hold the same reading of where the floor is.

## The rows this closes

kbase SPEC §4: "Unmarked-reference shortlist" (section 1) and "Attribution of an unmarked yes"
(section 2). "Build inputs on the trail" stays open from the earlier hand-off.
