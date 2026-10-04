# {project-name} Knowledge Base

{overview-passage}

## What Is Here

A `leaf` is translated source — the corpus's own text carried across, not a summary of it. The rest
is navigation the build wrote: the `entry-point` at the root, and an `index` in each directory that
holds documents beneath it. An index carries no translated source of its own — a section's own prose
is a leaf beneath it. Those three kinds are the documents, and nothing else is one: no
`claim-quality.md` register, no `invariants.md`, not this file, `AGENTS.md` or `CONVENTIONS.md`, and
none of the images under `assets/` that leaves embed. Every document names its kind in the `kind`
field of its frontmatter. Reading order is what the indexes themselves carry.

## The Claim Graph Over It

This graph is over results rather than documents: what the corpus establishes, what each result
stands on, and which outside works it leans on.

Every node has an entry in a `claim-quality.md` register: its title, its quality values, and a
rationale for them. An entry for a result of this corpus links the document that states it. A
domain's register holds that domain's nodes; the register at this root holds the outside works the
corpus cites.

Each edge between the nodes is of one class. A `depends` edge runs from a result to what it was
derived from. `supports` and `strengthens` run the other way, from evidence to the result it lifts.
`rests-on` leaves the corpus: it points at a work this KB cites and does not contain. A
`references` edge records that one result's own text names another, and nothing rests on it.

The graph is drawn too: [`claim-graph.svg`](claim-graph.svg) beside this file draws every node
and not every edge. It draws no `references` edge. Of the other classes, edges sharing a source and
target share one stroke, and a stroke is left off wherever the drawn strokes already lead from its
premise to what rests on it. So everything a node rests on is reachable along the strokes, but a
missing stroke is not a missing edge — `.index/` carries every edge. A node only `references` edges
touch is drawn unattached, in the block below the rest. Nodes are coloured by standing and edges by
what they carry. It is rendered from `.index/` by the refresh target and authored by nobody — read
it, never edit it.

A claim carrying no confidence value reads {pending-literal} wherever it appears, and so does its
solidity: that says *unscored*, not *low* and not *doubted*.

## Current Figures

This file states no counts, because the KB changes after it is written. The current ones come from
the KB's runner targets, run from the project root that holds this KB: `just <target>`, or
`make <target>` where that root has a Makefile rather than a justfile.

`kb-stats` counts the claim graph. Its first lines count the nodes, one line per node kind.
`depends_on_edges` counts every edge, of every class. Under `solidity build-band distribution` it
counts the claims in each band: the {pending-literal} band holds the unscored claims, and every
other band holds scored ones.

It does not split the edges by class. Each edge is one line of `.index/depends-on.jsonl`, and the
line's `relation` field names its class.

`kb-verify` counts the documents. The files its `[claim-quality] Scanned` line counts are the
documents, and the same line says how many of them are leaves.

## Reading It

Don't walk the tree by hand — it is built to be navigated, and a breadth-first read spends context
the answer never needed. Run `/kb-start` for a new topic or `/kb-next` to switch, from this KB root
or from the project root that holds it.

[`AGENTS.md`](AGENTS.md) beside this file says how this KB expects to be read and changed.
[`CONVENTIONS.md`](CONVENTIONS.md) is the full operating contract: what is authored versus derived,
how the gate works, and how citations are formed.
