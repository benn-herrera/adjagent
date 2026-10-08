# Fixture: found-not-authored edge adjudication brief (instrument v1)

The standing instrument for judging dependency edges a KB build inferred that the
author's hand-curated KB does not carry. Every adjudication uses the prompt body
below unchanged, so verdict files compare row for row across runs; an edit to the
instrument is an edit to the baseline and gets owner sign-off.

Dispatch contract: `applied-mathematician`, `model: fable`, cold context, one
dispatch for one citing paper at a time, background; a further paper is a further
decision, taken on the first paper's result. Substitute exactly five parameters,
nothing else:

- `{kb-root-path}` — absolute path to the built KB's kb-root/
- `{reference-kb-path}` — absolute path to the author's hand-curated kb-root/
  (`ModernCorpPristine/kb-root`)
- `{edge-list-path}` — absolute path to the TSV of this paper's edges: the rows of
  `found-not-authored.tsv` (a `compare-to-pristine.py` output) whose `citing_paper`
  is this paper and whose `verdict` column is empty
- `{citing-paper}` — the top-level directory name the edges cite from
- `{output-path}` — absolute path for this dispatch's verdict TSV

Edges already ruled on are filtered out before dispatch; the seat never sees a prior
verdict. Verdict rows accumulate in `verdicts.tsv` beside this file.

---- PROMPT BODY BELOW — SUBSTITUTE PARAMETERS, CHANGE NOTHING ELSE ----

You are adjudicating dependency edges in a knowledge base built from a multi-volume
economics work. The author hand-curated a reference KB of the same corpus; the edges
you are handed are ones the build inferred and the author did not mark. For each one
the question is: **had the author been asked, would he have marked it?**

Take both claims as given. The build registers far more claims than the author did,
most finer than anything he recorded. The question is the edge, not whether he would
have recorded either end.

The built KB: {kb-root-path}. Start at `entry-point.md`; `CONVENTIONS.md` beside it
defines the relations. Its sections on agents, the gate and writing apply to editing
the KB, not to reading it: read the files directly and run nothing that writes. Read
as much of the KB as establishing a working comprehension of the volumes needs; the
whole thing is yours. Your output file is the only thing you write.

Every `depends-on`, `references` and `demoted` list in {kb-root-path} is the build's
own output, and the edges you are judging are among them. The author's KB is
{reference-kb-path}. Its `claim-quality.md` registers show the grain at which he
marks `depends`; calibrate there, before ruling, and nowhere else.

The edges: {edge-list-path}, every one citing from `{citing-paper}`. Columns:
`citing_leaf` and `cited_leaf` are the documents hosting each claim's text;
`citing_id` and `cited_id` find each claim's register entry by searching for
`<!-- id: <id> -->` in the `claim-quality.md` of `citing_paper` or `cited_paper`;
`locality` says whether the pair shares a document, a paper, or neither.

Each edge was produced by a 35-billion-parameter local model shown the two claims
alone and asked for a single letter. No reasoning was recorded. Treat the edge as a
hypothesis with that provenance: a reader who saw far less than you will.

**The author's standard, not a maximal one.** The reference KB marks `depends` where
a claim's derivation or argument uses the cited result, so that removing it breaks
the chain. A mention in passing, a shared symbol, a thematic kinship, or a
restatement of the same result in another volume is not a dependence. Mark `depends`
only where you can name the step in the citing claim that fails without the cited
result, and the reference KB shows he draws dependences at that grain. A dependence
a maximally careful author could defend, but this author's registers show he does
not draw, is `neither`.

**Method.** Read the citing leaf in full and the cited leaf in full. Read what else
the citing claim rests on and what else cites the cited claim, in both KBs: an edge
that duplicates a path the reference KB carries reads differently from one that opens
a route it never drew. Write rows as you rule. Before you finish, compare rulings on
similar pairs and make them agree. Claim classification is not asked for here.

**Verdict per edge**, exactly one of:

- `depends` — the author would have marked this as load-bearing.
- `references` — the citing claim names the cited result without resting on it. The
  author's KB has no citation relation, so this verdict says the build mislabelled a
  citation as a dependence.
- `neither` — the author was right to leave it unmarked.

With each verdict give your confidence: *verified* (you followed the citing claim's
argument in its leaf and found the use, or confirmed there is none),
*high-confidence*, *plausible*, *unverified* (the leaves did not let you follow it);
and a basis of one to three sentences naming the step in the citing leaf that uses,
names, or does not touch the cited result.

**Output**: write {output-path} as a tab-separated file with a header row and these
columns, one row per edge you rule on, in the order of the input list:

`citing_leaf	citing_register_anchor	cited_leaf	cited_register_anchor	verdict	confidence	basis	citing_paper`

`verdict` and `confidence` are bare lowercase tokens, no asterisks or backticks;
`citing_paper` is `{citing-paper}`; no quoting; tabs and newlines inside `basis`
become spaces; no other columns, no blank lines. After the file is written, reply
with the counts by verdict and the three edges you were least sure of, with why.
Nothing else.

---- PROMPT BODY ABOVE — MAINTAINER NOTES BELOW, NEVER EXTRACTED ----

## Verdict file

`verdicts.tsv` beside this brief holds every ruling to date: the per-dispatch output
files appended in dispatch order, header once. `compare-to-pristine.py --verdicts`
joins it onto `found-not-authored.tsv`, keyed on the four leaf and anchor columns,
so an edge with a verdict is never dispatched again. A rebuild that mints a claim
under a different title changes its register anchor and the edge re-enters the
queue; that is intended, since the claim text the ruling was made on has changed.

## Changelog

- **v1 — 2026-10-06.** Original. Drafted for the first full-corpus Qwen3.6-35B-A3B
  run after the oMLX turboquant-kv and lightning-mtp settings were turned off.
  Prompt-engineer review before first use moved calibration from the built KB's
  registers (which carry the edges under judgment) to the reference KB, dropped the
  prior-verdicts parameter in favour of filtering before dispatch, and reworded the
  `references` verdict to match an author's KB that has no citation relation.
