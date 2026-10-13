# KB_TOOLS Catch-Up: kbase's New Write Ops, Stage, and Ask Kind

Summary of what the kbase Go sibling (read at `/Users/agent-user/projects/kbase`) now has that
kb_tools must mirror: four write ops (three public, one build-only), the build stage
`claims-vetted` with its record, and the ask kind `vetting`. Read against kbase's SPEC.md §4 (the
two divergence rows, each closed when kb_tools adopts), §5, §6, §8 and §10.

## 1. The four new write ops

Rows copied verbatim from kbase `internal/write/values.go` `opFields` map:

```go
"drop-claim-edges": {
    {"id", checkClaimID, true},
    {"edge-class", checkEdgeClass, false},
},
"drop-inbound-edges": {
    {"id", checkClaimID, true},
},
DemoteClaimEdge: {
    {"id", checkClaimID, true},
    {"target", checkClaimID, true},
    {"origin", checkOneOf(kb.Origins, "origin"), true},
    {"context", checkProse, false},
},
"drop-claim-node": {
    {"id", checkClaimID, true},
},
```

`DemoteClaimEdge` is the constant `"demote-claim-edge"` (`internal/write/ops.go`); `kb.Origins` is
`cited` and `inferred`.

Three ops are public subcommands (and MCP tools); `demote-claim-edge` is build-only, absent from the
public op list and from `kbase --help`, and reachable only by the build. SPEC.md §8 semantics:

- `drop-claim-edges` — removes a claim entry's outgoing `depends-on` or `references` bullets, the
  class named by `edge-class` or, where none is, both; each bullet goes with its continuation lines,
  and a list's header goes where neither bullet nor other text is left. An absent list stands.
  `edge-class: demoted` is refused: demoted rows are `resolve-demoted`'s to remove. A re-issue is
  `unchanged`. Mirror: remove the outgoing bullets, headers included; refuse the demoted class.
- `drop-inbound-edges` — removes, from every register entry holding one, each `depends-on` or
  `references` bullet naming `id`, with its continuation lines, and a list's header where neither
  bullet nor other text is left; an entry naming no such bullet stands. A re-issue is `unchanged`.
  Mirror: sweep every register entry for bullets pointing at the claim.
- `demote-claim-edge` (build-only) — turns `id`'s existing `depends` edge naming `target` into a
  `demoted` row of the same entry carrying `origin`, which the build computes: `inferred` where the
  pair, in its written direction, is a yes in the unmarked record, else `cited`. Where that row
  already stands with the same origin, it removes a `depends` bullet still standing beside it
  (`done`) and otherwise leaves the pair (`unchanged`); a row standing with the other origin is
  refused, naming both origins; a pair with neither a `depends` bullet nor a `demoted` row is
  refused. Mirror: the origin is a required value, not a constant `cited`; a kb_tools build-only
  registry row, as `add-build-edges`.
- `drop-claim-node` — deletes the claim node entirely: its register entry block, its claim-quality
  marker from every leaf carrying it (a leaf restated no-claim included), its id from every leaf
  claiming it, and every other entry's `demoted` row naming it. Refused, writing nothing, where any
  entry's `depends-on` or `references` still names the node; where the call would empty a leaf's
  `claims` list (the nodes one call drops from a leaf counted together), that being a no-claim
  decision `set-frontmatter` makes; and where, once those removals are composed, any line under
  `kb-root/` still names the node, each such line named as `path:line` (refresh's own roll-ups
  excepted). A re-issue removes whatever of the node still stands (`done`) and is `unchanged` where
  nothing does. Mirror: full node deletion with the three refusals; the issuer restates a leaf
  hosting only the culled claim no-claim through `set-frontmatter` before the drop.

## 2. The new stage `claims-vetted`

kbase `internal/build/build.go` `Stages` places `{"claims-vetted", "claims vetted"}` between
`{"depends-attributed", "dependency attribution"}` and `{"phase-3a", "validation gate"}`. Its row is
`{id: "vetting.build", stage: "claims-vetted", spendsInferenceInPart: true,
run: claimGraph(claimgraph.Vetting)}`: its asks spend inference, while the elision tail and the ring
row are mechanical. Under `--no-inference` the row is still walked on a reader-nil path: no ask, an
empty record, and the ring row.

The stage body (`claimgraph.Vetting`):

- A candidate is a claim node with exactly one claim-to-claim `depends` edge in and one out.
  Two passes of a vetting ask run over every candidate, each candidate asked once; the second pass
  reads the graph as the first left it, bridges included.
- An Accompany, answered or re-asked, culls the node through the elision tail: one bridge per
  maximal run of consecutive culls, created first (the claim that depended on the run depends on the
  claim the run depended on); then each cull's outgoing edge bullets, inbound bullets and the node.
  A leaf hosting the cull alone is first restated no-claim with a fixed reason. A defaulted ask
  keeps the node.
- Last, every `depends` edge still on a cycle is demoted through `demote-claim-edge`, its origin
  computed from the unmarked record.

The stage writes the fourth tracked build record `kb-build-vetting.yaml`
(`buildrecords.VettingFile`, repository root, joining `NodePassFile`, `ClassificationFile` and
`UnmarkedFile` in `RecordFiles`). Its shape: `about`; `entries`, sorted by `id`, each `id`,
`predecessor` (the claim the node depends on), `successor` (the claim that depends on the node),
`verdict` (`carry` or `accompany`) and `outcome` (`answered`, `re-asked` or `defaulted`); `bridges`,
sorted by `from` then `to`, each `from` depends on `to`. The sheet reads `bridges` to draw each as
an inferred `depends` edge.

## 3. The new ask kind `vetting`

Two files, both provenance class `kbase-origin` in the manifest `internal/asks/provenance.yaml`
(authored de novo, no origin file, no kb_tools ancestor):

- `internal/asks/prompt-templates/questions/vetting.question.yaml` — `type: noul`,
  `true-letter: "@!letter-carry!@"`, criteria keyed `"true"` and `"false"`, complements built on a
  removal test.
- `internal/asks/prompt-templates/vetting.tmpl.md` — shows, in argument order, the claim it builds
  on (the predecessor), the claim under vetting, and the claim that builds on it (the successor).

The letters are kbase `internal/asks/kinds.go` constants: `LetterCarry = "A"` and
`LetterAccompany = "B"`. A = Carry: without the claim under vetting, the reasoning from the claim it
builds on to the claim that builds on it has a gap — keep. B = Accompany: there is no gap; the claim
only restates, paraphrases, glosses, motivates or comments — elide.

## 4. kb_tools' mirror obligation

kb_tools' test `tests/test_kb_write_ops.py`
(`test_every_op_of_the_surface_has_a_closed_values_vocabulary`, ~lines 2822–2831) asserts
`set.union(*registries) == set(values.OP_FIELDS)` over
`(set(ops.OPS), set(ops.READ_OPS), set(ops.BUILD_OPS))` — this FAILS until the four ops' rows land
in kb_tools' `kb_write/values.py` `OP_FIELDS`. kb_tools' `OP_FIELDS` already carries the build-only
op `add-build-edges` (`kb_write/values.py:1122`; `ops.py` `BUILD_OPS`, ~line 3309), so build-only vs
public is not an exemption: all four rows go in, `demote-claim-edge` among `BUILD_OPS`.
