"""Where an equation node is stated: its fence, and the claim whose own body holds that fence.

An equation node is its ``(document, label)`` (:attr:`graph.ClaimNode.equation`),
and its fence is the first in that document carrying the label, as the minting
stage reads it. A claim whose body (:func:`hand_named.bodies`) holds that fence
*states* the equation rather than pointing at it, so the pair is no dependency
in either direction and no reference: the unmarked shortlist leaves it out of
the claim's pool, and :func:`attribute.narrow` drops it as a candidate.
"""

from collections.abc import Mapping

from .graph import AuthoredGraph
from .hand_named import bodies
from .inventory import Inventory, MathFence
from .tree import Tree


def fences(graph: AuthoredGraph, inventory: Inventory) -> Mapping[str, MathFence]:
    """Each equation node's fence, by node id. A node whose label no fence carries is absent."""
    by_label: dict[tuple[str, str], MathFence] = {}
    for fence in inventory.fences:
        for label in fence.labels:
            by_label.setdefault((fence.document, label), fence)
    return {
        node.id: by_label[(node.document, node.equation)]
        for node in graph.nodes.values()
        if node.equation is not None and (node.document, node.equation) in by_label
    }


def own_equations(tree: Tree, graph: AuthoredGraph, inventory: Inventory) -> frozenset[tuple[str, str]]:
    """Every ``(claim, equation node)`` pair whose equation's fence lies inside that claim's own body."""
    extents: dict[str, list[tuple[str, int, int]]] = {}
    for node, document, first, text in bodies(tree, graph, inventory):
        extents.setdefault(document, []).append((node.id, first, first + len(text.split("\n"))))
    return frozenset(
        (claim_id, equation_id)
        for equation_id, fence in fences(graph, inventory).items()
        for claim_id, start, end in extents.get(fence.document, ())
        if start <= fence.start and fence.end <= end
    )
