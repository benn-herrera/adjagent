"""Reading order, where each claim sits in it, and the adjacency links it implies.

The one definition every stage that orders claims shares. A document's place is
its index in :func:`reading_order`; a claim's line is where its body begins
(:func:`hand_named.bodies`) or, for an equation node, where its fence opens
(:func:`equation_sites.fences`) — both 0-based lines of the written document.
"""

import sys
from collections.abc import Callable, Collection, Mapping
from typing import NamedTuple

from .. import kb_index_lib
from .equation_sites import fences
from .graph import AuthoredGraph
from .hand_named import bodies
from .inventory import Inventory
from .tree import Tree

#: The line of a claim neither a body nor a fence reaches: after every line of its document.
UNREACHED_LINE = sys.maxsize

#: An unordered pair of claims, held lower id first (:func:`link`).
Link = tuple[str, str]


class Position(NamedTuple):
    """Where a claim sits in reading order; tuples compare document first, then line."""

    document: int
    line: int


def link(x: str, y: str) -> Link:
    """The unordered pair of ``x`` and ``y``, lower id first."""
    return (x, y) if x <= y else (y, x)


def reading_key(positions: Mapping[str, Position]) -> Callable[[str], tuple[Position, str]]:
    """A claim's place in reading order, a tie by id."""
    return lambda node_id: (positions[node_id], node_id)


def shown_order(pair: Link, positions: Mapping[str, Position]) -> tuple[str, str]:
    """The link's two claims in reading order, a tie by id."""
    key = reading_key(positions)
    return (pair[1], pair[0]) if key(pair[1]) < key(pair[0]) else pair


def reading_order(tree: Tree) -> list[str]:
    """Every document reachable from the entry point, in preorder over each document's children as it lists them."""
    out: list[str] = []

    def walk(path: str) -> None:
        out.append(path)
        for child in tree.children.get(path, ()):
            walk(child)

    walk(kb_index_lib.ENTRY_POINT_FILENAME)
    return out


def claim_positions(tree: Tree, graph: AuthoredGraph, inventory: Inventory) -> dict[str, Position]:
    """Every claim's position: a block or prose claim at its body's first line, an equation node at its fence's
    first line, and a claim neither reaches last in its document."""
    documents = {path: index for index, path in enumerate(reading_order(tree))}
    lines: dict[str, int] = {}
    for node, _, first, _ in bodies(tree, graph, inventory):
        lines[node.id] = min(first, lines.get(node.id, first))
    for node_id, fence in fences(graph, inventory).items():
        lines[node_id] = fence.start
    return {
        node.id: Position(documents[node.document], lines.get(node.id, UNREACHED_LINE)) for node in graph.nodes.values()
    }


def adjacent_links(graph: AuthoredGraph, positions: Mapping[str, Position], marked: Collection[Link]) -> list[Link]:
    """Each document's consecutive claims linked, equation nodes left out, in (line, id) order, less the marked
    links; sorted."""
    out = []
    for document in graph.documents():
        hosted = sorted(graph.hosted_by(document), key=lambda node: (positions[node.id].line, node.id))
        for earlier, later in zip(hosted, hosted[1:]):
            pair = link(earlier.id, later.id)
            if pair not in marked:
                out.append(pair)
    return sorted(out)
