"""Which referenced equations are claim nodes, and which are not.

An equation is not a result, and this does not make one into one. What it mints
a node for is narrower and is the author's own doing: **a labelled equation that
a cross-reference names and that nothing else in the graph already holds.** The
node exists so that the reference resolves to something; it is not a judgement
that the equation states anything.

**Three cases, and only the third mints.**

* The equation is labelled inside a **claim-bearing block**. The block's claim
  already holds it — an equation labelled inside a theorem body *is* that
  theorem's assertion — and :func:`attribute._equation_claim` has landed such a
  reference on that claim since before this module existed.
* The equation is labelled inside a **proof**. :class:`inventory.Proof` already
  binds the proof to the blocks it establishes, so what holds the equation is
  the claim being proved and no node is needed. **The join that walks that
  binding is not built**, so such a reference reaches nothing today — 689
  anchors over the corpus. What it needs is a node it does not have; what it
  is a second reading of an existing artifact and not this module's subject.
* The equation is labelled anywhere else — free-standing, or inside a block
  nothing claims. Nothing holds it, the reference resolves to nothing at all,
  and that is what a node here ends.

**Bounded by the author's own cross-references.** A labelled equation nobody
cites is scaffolding: the author numbered it and then never pointed at it, and
minting for it would put a corpus's display maths into the graph rather than the
part of it the corpus reasons over. Measured over the 50-paper arXiv corpus:
2057 labelled equations, of which this yields 755.

**Identity is the label, and the title is the only field that can carry it.**
Point 9 leaves an equation's ``\\label`` inside the maths fence rather than as an
addressable id, so an equation has no fragment for a cross-reference to name and
no display line for :func:`graph.read` to join a block by. The label is
therefore the join key — what :func:`attribute._equation_claim` matches an
anchor's ``data-reference`` against — and it reaches that join through
:func:`kb_schema.equation_title`, which is where the round trip through the
authored bytes happens.

**A node minted here is terminal on the mechanical path.** The only thing inside
a maths fence that could source an edge is a cross-reference, and a reference
sealed inside a fence reaches the tree as no anchor at all (155 of them over the
corpus, the class the plan rules out of scope). So an equation node is named by
references and names none, which is why adding a corpus's worth of them leaves
:func:`attribute.check_acyclic` with nothing new to find.
"""

from dataclasses import dataclass

from .inventory import PROOF_ENVIRONMENT, Inventory, by_document, hosting_block


@dataclass(frozen=True)
class ReferencedEquation:
    """One labelled equation a cross-reference names and nothing else holds."""

    document: str
    #: The author's own ``\\label``, off the maths fence. The join key.
    label: str
    #: 0-based line the fence carrying it opens on. Carried so the mint order is
    #: the scan's order and two runs over one corpus mint in the same sequence.
    line: int


def unheld(inventory: Inventory) -> tuple[ReferencedEquation, ...]:
    """Every referenced equation no claim-bearing block and no proof holds, in scan order.

    Deterministic and total over stage B's readings: nothing is sampled, and an
    equation appearing twice under one label in one document is one node rather
    than two, the label being what a reference names.
    """
    blocks = by_document(inventory.blocks)
    named = {(anchor.target, anchor.label) for anchor in inventory.anchors if anchor.target is not None}

    found: list[ReferencedEquation] = []
    seen: set[tuple[str, str]] = set()
    for fence in inventory.fences:
        block = hosting_block(fence.start, blocks.get(fence.document, ()))
        if block is not None and (block.claim_bearing or block.environment.casefold() == PROOF_ENVIRONMENT):
            continue
        for label in fence.labels:
            key = (fence.document, label)
            if key not in named or key in seen:
                continue
            seen.add(key)
            found.append(ReferencedEquation(document=fence.document, label=label, line=fence.start))
    return tuple(found)
