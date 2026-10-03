# {project-name} Knowledge Base

{overview-passage}

## What Is Here

{document-count} documents in all, {leaf-count} of them at the leaves. A `leaf` is translated source
— the corpus's own text carried across, not a summary of it. The rest is navigation the build wrote:
the `entry-point` at the root, and an `index` in each directory that holds documents beneath it. An
index carries no translated source of its own — a section's own prose is a leaf beneath it. The
count and the listing below hold documents only: no `claim-quality.md` register, no `invariants.md`,
not this file, `AGENTS.md` or `CONVENTIONS.md`, and none of the images under `assets/` that leaves
embed. Every document in the listing carries its label.

The listing is by location, not by reading order — each directory's `index.md` first, then its other
documents by name, then its subdirectories. Reading order is what the indexes themselves carry.

```
{document-tree}
```

## The Claim Graph Over It

This graph is over results rather than documents: what the corpus establishes, what each result
stands on, and which outside works it leans on. By kind, it holds {node-kind-counts}.

Every node has an entry in a `claim-quality.md` register: its title, its quality values, and a
rationale for them. An entry for a result of this corpus links the document that states it. A
domain's register holds that domain's nodes; the register at this root holds the outside works the
corpus cites.

Edges between the nodes — {edge-count} in all, by class:

{edge-class-counts}

A `depends` edge runs from a result to what it was derived from. `supports` and `strengthens` run
the other way, from evidence to the result it lifts. `rests-on` leaves the corpus: it points at a
work this KB cites and does not contain.

The graph is drawn as well as counted: [`claim-graph.svg`](claim-graph.svg) beside this file draws
every node and not every edge. It draws no `references` edge. Of the other classes, edges sharing a
source and target share one stroke, and a stroke is left off wherever the drawn strokes already lead
from its premise to what rests on it. So everything a node rests on is reachable along the strokes,
but a missing stroke is not a missing edge — `.index/` carries every edge. A node only `references`
edges touch is drawn unattached, in the block below the rest. Nodes are coloured by standing and
edges by what they carry. It is rendered from `.index/` by the refresh target and authored by nobody
— read it, never edit it.

Claims carrying a confidence value: {scored-count} of {claim-count}. A claim without one reads
{pending-literal} wherever it appears, and so does its solidity: that says *unscored*, not *low* and
not *doubted*.

## Reading It

Don't walk the tree by hand — it is built to be navigated, and a breadth-first read spends context
the answer never needed. Run `/kb-start` for a new topic or `/kb-next` to switch, from this KB root
or from the project root that holds it.

[`AGENTS.md`](AGENTS.md) beside this file says how this KB expects to be read and changed.
[`CONVENTIONS.md`](CONVENTIONS.md) is the full operating contract: what is authored versus derived,
how the gate works, and how citations are formed.
