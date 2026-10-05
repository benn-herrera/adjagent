# claim-graph-sheet — the claim-graph sheets' input and their DOT goldens

`kb_tools/claim_sheet.py` reads a KB root's `.index/`, the H1s of `entry-point.md` and each
volume's `index.md`, the leaves hosting its claims, and the two claim-graph build records beside
`kb-root/`. This directory is such a repository: `kb-root/` holds the index, the title documents and
two leaves and nothing else of a KB (no registers), and the build records sit beside it.
`test_claim_sheet.py` loads it, composes the sheets and byte-compares them with the three goldens
here. `kb_cmd.load` refusing the `.index/` records is the check that they stay well-formed.

These are inputs to tests only: `INSTALL_EXCLUDED_DIRS` carries `tests`, so nothing under
`kb_tools/tests/` reaches a consuming project.

| File | What it is |
|---|---|
| `claim-graph.dot` | `compose_sheet(load(kb-root))`, trailing newline included |
| `claim-graph-digest.dot` | `compose_digest(load(kb-root))`, trailing newline included |
| `alpha-claim-graph.dot` | `compose_volume_sheet(load(kb-root), "alpha")`, trailing newline included |
| `kb-build-unmarked.json`, `kb-build-classification.json` | the build records each edge's provenance is read from |
| `kb-root/entry-point.md`, `kb-root/alpha/index.md`, `kb-root/beta/index.md` | the KB title and the two volume titles, Beta's carrying `&`, `"` and `<` |
| `kb-root/alpha/results.md`, `kb-root/beta/governance.md` | the leaves whose Tier-2 markers place claim kinds |
| `kb-root/gamma/index.md` | a volume directory no node sits in, which gets no sheet and no digest box |
| `kb-root/.index/*.jsonl` | the records; `strengthen-by.jsonl` and `subtree-aggregates.jsonl` are empty |

## What the records cover

- **Nodes.** Claims in both volumes, a support and an experiment in `alpha`, and an invariant, an
  axiom and a work at the root. Bands on four ladder rungs and `unknown`. Two unattached claims in
  `alpha`, none in `beta`. One title carrying `` $`\nabla f`$ ``, `"`, `<` and `&`; one long enough
  to be cut, and one carrying a Markdown link and emphasis.
- **Kinds.** A marker in a labelled blockquote (`clm-aaa001`), the same on the content line of a block
  whose label carries a `<span id>`, under a title that reads as prose (`clm-bbb002`), a marker inside a math fence under a prose title
  (`clm-aaa003`), and a marker in a paragraph (`clm-aaa004`). An equation with no marker is read by
  its title, as every equation is; four more claims fall back to the title and are counted: claims
  no leaf cites, and one whose cited leaf does not exist.
- **Edges.** Every relation in `kb_schema.EDGE_RELATIONS`. A cross-volume `depends`. An inferred
  `depends` (the unmarked record's "points" letter) and a cited one the unmarked record answered
  "does not point". A `references` pair in both directions: one cut (the classification record's
  `depends` letter), the other not, and so not drawn. A triangle — `clm-aaa003` rests on
  `clm-aaa002` directly and through `clm-aaa001` — whose direct edge is not drawn. Two `depends`
  records differing only in `context`, which draw as one stroke. One `depends` naming an id no
  record carries, which draws as a ghost.

## Regenerating the goldens

The DOT text is ours and deterministic, so it needs no Graphviz and no version pin. No SVG is
committed and no test runs Graphviz: `dot`'s layout and bytes change between releases, so the DOT
text is the only pin on what is drawn.

There is no regeneration recipe. A failing compare prints the diff, and a deliberate change is
applied by editing the golden to the bytes the failure shows.

**A golden update is a decision, not a repair.** Its whole value is that a change nobody meant to
make shows up as a failing byte-compare; editing one to turn a red test green throws that away.
Read the diff, decide the change was intended, then apply it.
