"""Geometry-level tests for ``kb_graph.layout`` and ``kb_graph.style``.

One section per clause of the row's done-condition: layering on the chain, fan
and diamond shapes; a cyclic graph laying out without recursion, without
raising and with no cycle member at layer 0, its residual pass reading a
pre-pass snapshot; a shuffle test at the geometry level; and four
hop-geometry fixtures, with a mechanical check that no epsilon and no true
division exist in either module's source.

**In-layer order is the crossing-reduction sweep's output, not a key lookup.**
The fixtures name their nodes so that the sweep's *starting* order is readable —
within one layer ``clm-l00001`` starts left of ``clm-l00002``, and a dummy,
keyed on its edge's ``(source, target)`` pair, starts against those ids as the
tuple it is — and a hand-computed coordinate stays checkable wherever the sweep
leaves that order where it found it, which is wherever the barycentres tie.
Where it does not, the shape is chosen so that the outcome is forced either
way: a crossing the sweep must remove, or a complete bipartite shape whose
crossings no ordering can remove at all.

**A column index is not an x coordinate either.** The coordinate phase pulls
each occupant toward its neighbours' barycentre, so a hand-computed coordinate
is checkable where the pull is forced — a vertex between two premises lands on
their midpoint — and where nothing pulls, which is a layer whose occupants all
want the same place and are held apart by the column pitch. The one comparison
against what the phase replaced runs it with its round cap set to zero, which is
the column grid exactly.

**A node with no edges is on neither of those two paths.** It takes no layer and
no place in the sweep at all; it is drawn in the grid block below the baseline,
where its coordinates are its row and column times the pitches and nothing
computes them. The fixtures for that are their own section, and the ones above
that used an unattached node as a ruler now attach it.

**Every fixture states the arrangement it is about.** The sheet ships
concentric (``layout.DEFAULT_PLACEMENT``); the sections up to the concentric one
are about the layered arrangement — the priority method's coordinates, the
box-edge anchors, the grid the ordering draws on — so a module-wide fixture
names ``linear`` for them rather than letting them read whatever the default
happens to be. The concentric section names its own, and what holds under every
arrangement is parametrised over all of them.
"""

import ast
import random
from collections import Counter
from collections.abc import Iterable
from fractions import Fraction
from itertools import combinations
from pathlib import Path

import pytest

from kb_tools.kb_cmd import index as kb_index
from kb_tools.kb_graph import layout, model, style

# ---------------------------------------------------------------------------
# Record builders and shape helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def layered(monkeypatch: pytest.MonkeyPatch) -> None:
    """The layered arrangement, which is what every section but the concentric one is about.

    A test about another one sets the variable again over this, which is what
    keeps any fixture here from reading whichever arrangement the sheet happens
    to ship with.
    """
    monkeypatch.setenv(layout.PLACEMENT_ENV, "linear")


def _claim(cid: str, *, canonical_path: str = "vol1/topic/leaf.md") -> kb_index.Claim:
    return kb_index.Claim(
        node_type="claim",
        id=cid,
        title=f"Claim {cid}",
        canonical_path=canonical_path,
        canonical_anchor=cid,
        confidence=0.8,
        solidity=0.8,
        build_status=None,
        build_band="ok-to-build",
        rationale="",
        depends_on_count=0,
        strengthen_by_count=0,
        citation_count=0,
    )


def _edge(source: str, target: str, relation: str = "depends", **overrides) -> kb_index.DependsOnEdge:
    fields = {
        "source": source,
        "target": target,
        "target_kind": "claim",
        "target_solidity_recorded": None,
        "context": None,
        "relation": relation,
        "strength": None,
        "fraction": None,
    }
    fields.update(overrides)
    return kb_index.DependsOnEdge(**fields)


def _graph(ids: Iterable[str], pairs: Iterable[tuple[str, str]], relation: str = "depends") -> model.ClaimGraph:
    """A graph of plain claims, ``pairs`` read as ``(source, target)`` records."""
    return model.build_graph(
        nodes=[_claim(node_id) for node_id in ids],
        edges=[_edge(source, target, relation) for source, target in pairs],
    )


def _layers(sheet: layout.Sheet) -> dict[str, int]:
    return {placed.id: placed.layer for placed in sheet.nodes}


def _columns(sheet: layout.Sheet) -> dict[str, int]:
    return {placed.id: placed.column for placed in sheet.nodes}


def _cid(letter: str, number: int) -> str:
    """A realistic six-character id body whose sort order is readable at a glance."""
    return f"clm-{letter}{number:05d}"


# ---------------------------------------------------------------------------
# Layering — the chain, fan and diamond shapes
# ---------------------------------------------------------------------------


def test_a_chain_layers_by_derivation_depth() -> None:
    """Layer 0 is the premise-less bedrock and the sheet grows upward."""
    a, b, c, d = (_cid("a", n) for n in range(4))
    sheet = layout.place(_graph([a, b, c, d], [(b, a), (c, b), (d, c)]))
    assert _layers(sheet) == {a: 0, b: 1, c: 2, d: 3}
    # One node per layer, so every column is 0 and the chain draws straight up.
    assert set(_columns(sheet).values()) == {0}


def test_a_fan_out_puts_every_dependent_one_layer_above_its_premise() -> None:
    premise = _cid("a", 0)
    dependents = [_cid("b", n) for n in range(3)]
    sheet = layout.place(_graph([premise, *dependents], [(dep, premise) for dep in dependents]))
    assert _layers(sheet) == {premise: 0, **{dep: 1 for dep in dependents}}
    # In-layer order is the node id ascending and nothing else.
    assert [dep for dep in dependents] == [placed.id for placed in sheet.nodes if placed.layer == 1]
    assert _columns(sheet) == {premise: 0, dependents[0]: 0, dependents[1]: 1, dependents[2]: 2}


def test_a_fan_in_layers_the_dependent_above_every_premise() -> None:
    dependent = _cid("z", 0)
    premises = [_cid("a", n) for n in range(3)]
    sheet = layout.place(_graph([dependent, *premises], [(dependent, premise) for premise in premises]))
    assert _layers(sheet) == {dependent: 1, **{premise: 0 for premise in premises}}


def test_a_diamond_layers_by_the_long_side_and_not_the_short_one() -> None:
    """A dependent stands above every premise, so the deepest one decides.

    Two routes run from ``a`` up to ``d`` — three steps one way and two the
    other — which is what a diamond has to be for the sheet to draw it whole:
    a route of one step beside a route of three is a premise the long way
    round already carries, and the model draws the route rather than the
    stroke.
    """
    a, b, c, d = (_cid("a", n) for n in range(4))
    short = _cid("s", 0)
    sheet = layout.place(_graph([a, b, c, d, short], [(b, a), (c, b), (d, c), (short, a), (d, short)]))
    # d leans on both c and short; the three-step side is what it has to clear.
    assert _layers(sheet)[d] == 3
    assert _layers(sheet)[a] == 0


def test_a_premise_rises_to_meet_the_one_dependent_it_has() -> None:
    """The layering's whole mechanism: total edge length, not depth from bedrock.

    ``lifted`` rests on nothing, so the longest path stands it on bedrock and
    its edge to the top of the chain is routed through two placeholders. Nothing
    holds it there — lifting it shortens that edge and lengthens none — so it
    comes to rest one layer below the claim that needs it, and the chain draws
    as one segment.
    """
    chain = [_cid("a", n) for n in range(4)]
    lifted = _cid("z", 0)
    sheet = layout.place(_graph([*chain, lifted], [*zip(chain[1:], chain[:-1], strict=True), (chain[-1], lifted)]))

    assert _layers(sheet) == {chain[0]: 0, chain[1]: 1, chain[2]: 2, chain[3]: 3, lifted: 2}
    assert {edge.key: len(edge.points) for edge in sheet.edges}[(chain[-1], lifted)] == 2


def test_a_premise_rises_no_further_than_its_nearest_dependent() -> None:
    """The counter-case, and the bound on the lift above: ``bedrock`` carries two
    dependents, and the nearer one holds it down where it is, so its stroke to
    the far one keeps both placeholders.

    ``near`` stands one layer up because it rests on the corpus's own bedrock as
    well, and ``far`` stands three up because its own chain puts it there. No
    route runs from ``bedrock`` to ``far`` but the stroke itself — the two
    dependents are the only claims it reaches, and neither leads on — so the
    reduction leaves it, and what is measured here is the layering.
    """
    chain = [_cid("a", n) for n in range(3)]  # the corpus's bedrock and the two steps above it
    far, near, bedrock = _cid("f", 0), _cid("n", 0), _cid("z", 0)
    sheet = layout.place(
        _graph(
            [*chain, far, near, bedrock],
            [
                *zip(chain[1:], chain[:-1], strict=True),
                (far, chain[-1]),
                (near, chain[0]),
                (near, bedrock),
                (far, bedrock),
            ],
        )
    )

    assert _layers(sheet) == {chain[0]: 0, bedrock: 0, chain[1]: 1, near: 1, chain[2]: 2, far: 3}
    assert {edge.key: len(edge.points) for edge in sheet.edges}[(far, bedrock)] == 4


def test_a_dense_diamond_layers_every_rank_together() -> None:
    lower = [_cid("a", n) for n in range(2)]
    upper = [_cid("b", n) for n in range(2)]
    pairs = [(up, low) for up in upper for low in lower]
    sheet = layout.place(_graph([*lower, *upper], pairs))
    assert _layers(sheet) == {lower[0]: 0, lower[1]: 0, upper[0]: 1, upper[1]: 1}


def test_an_orphan_takes_no_layer_and_leaves_the_hierarchy_where_it_found_it() -> None:
    """Degree zero is no answer to "what does this rest on", so the node leaves
    the layering rather than standing on bedrock beside the corpus's real
    premises — and the hierarchy is byte-identical to the one drawn without it."""
    a, b, lonely = _cid("a", 0), _cid("a", 1), _cid("z", 0)
    sheet = layout.place(_graph([a, b, lonely], [(b, a)]))
    placed = {node.id: node for node in sheet.nodes}

    assert placed[lonely].layer < 0
    assert {node.id: node for node in layout.place(_graph([a, b], [(b, a)])).nodes} == {a: placed[a], b: placed[b]}


def test_an_empty_graph_places_nothing_and_still_has_a_view_box() -> None:
    sheet = layout.place(model.build_graph(nodes=[], edges=[]))
    assert (sheet.nodes, sheet.edges, sheet.hops) == ((), (), ())
    assert sheet.layer_count == 0
    assert sheet.view_box == layout.ViewBox(-style.MARGIN, -style.MARGIN, 2 * style.MARGIN, 2 * style.MARGIN)


@pytest.mark.parametrize("relation", ["supports", "strengthens", "conjectures"])
def test_only_depends_inverts_the_premise_direction(relation: str) -> None:
    """A ``depends`` record leans on its target; every other record's source
    is the premise, and an unknown relation is read the same way rather than
    dropped from the layering."""
    source, target = _cid("a", 0), _cid("b", 0)
    sheet = layout.place(_graph([source, target], [(source, target)], relation))
    assert _layers(sheet) == {source: 0, target: 1}
    assert layout.place(_graph([source, target], [(source, target)], "depends")) != sheet


def test_the_same_premise_recorded_twice_does_not_strand_a_node() -> None:
    """Two strokes can express one premise pair; counting it twice would leave
    the dependent's in-degree above zero forever and strand it in the residual
    set."""
    a, b = _cid("a", 0), _cid("b", 0)
    graph = model.build_graph(
        nodes=[_claim(a), _claim(b)],
        edges=[_edge(b, a, "depends"), _edge(a, b, "supports")],
    )
    sheet = layout.place(graph)
    assert _layers(sheet) == {a: 0, b: 1}
    assert [placed.cycle_member for placed in sheet.nodes] == [False, False]


# ---------------------------------------------------------------------------
# The cycle residual pass
# ---------------------------------------------------------------------------


def test_a_cycle_lays_out_with_marked_back_edges_and_no_member_at_layer_zero() -> None:
    a, b = _cid("a", 0), _cid("b", 0)
    sheet = layout.place(_graph([a, b], [(a, b), (b, a)]))
    assert _layers(sheet) == {a: 1, b: 1}
    assert all(placed.cycle_member for placed in sheet.nodes)
    assert all(placed.layer >= 1 for placed in sheet.nodes)
    assert [placed.back_edge for placed in sheet.edges] == [True, True]


def test_a_cycle_beside_a_resolved_graph_marks_only_its_own_edges() -> None:
    """The defective region is the picture's subject; the rest is unaffected."""
    a, b = _cid("a", 0), _cid("a", 1)  # a clean chain
    x, y = _cid("x", 0), _cid("x", 1)  # a two-cycle, disconnected from it
    sheet = layout.place(_graph([a, b, x, y], [(b, a), (x, y), (y, x)]))
    assert _layers(sheet) == {a: 0, b: 1, x: 1, y: 1}
    assert {placed.id for placed in sheet.nodes if placed.cycle_member} == {x, y}
    assert {edge.key for edge in sheet.edges if edge.back_edge} == {(x, y), (y, x)}


def test_the_residual_pass_reads_a_pre_pass_snapshot() -> None:
    """A layer assigned during the pass never feeds a later member's max().

    ``base`` resolves to layer 0 before the pass. ``first`` leans on it and on
    ``second``; ``second`` leans on ``first``, so the two are the residual set
    and ``first`` is visited first. Reading live layers would hand ``second``
    ``first``'s freshly assigned 1 and put it at 2; reading the snapshot leaves
    it at the floor of 1.
    """
    base, first, second = _cid("a", 0), _cid("b", 0), _cid("c", 0)
    sheet = layout.place(_graph([base, first, second], [(first, base), (first, second), (second, first)]))
    assert _layers(sheet) == {base: 0, first: 1, second: 1}


def test_a_self_loop_is_its_own_cycle() -> None:
    solo = _cid("a", 0)
    sheet = layout.place(_graph([solo], [(solo, solo)]))
    assert _layers(sheet) == {solo: 1}
    assert sheet.nodes[0].cycle_member
    assert sheet.edges[0].back_edge


def test_a_deep_chain_lays_out_without_recursion() -> None:
    """A recursive descent is a stack overflow on a deep or cyclic input;
    this chain is deeper than CPython's default recursion limit."""
    ids = [_cid("a", n) for n in range(1200)]
    sheet = layout.place(_graph(ids, list(zip(ids[1:], ids[:-1], strict=True))))
    assert sheet.layer_count == 1200
    assert _layers(sheet)[ids[-1]] == 1199
    # The pairwise hop scan ran over all of it: one node per layer, so every
    # segment is vertical on one column and every pair is parallel.
    assert len(sheet.edges) == 1199
    assert sheet.hops == ()


def test_a_deep_cycle_lays_out_without_recursion_and_without_raising() -> None:
    ids = [_cid("a", n) for n in range(1200)]
    ring = list(zip(ids[1:], ids[:-1], strict=True)) + [(ids[0], ids[-1])]
    sheet = layout.place(_graph(ids, ring))
    assert {placed.layer for placed in sheet.nodes} == {1}
    assert all(placed.cycle_member for placed in sheet.nodes)
    assert all(edge.back_edge for edge in sheet.edges)


# ---------------------------------------------------------------------------
# Coordinates — the bottom-anchored integer frame
# ---------------------------------------------------------------------------


def test_coordinates_are_the_declared_frame_and_every_one_is_an_integer() -> None:
    a, b, c = _cid("a", 0), _cid("a", 1), _cid("b", 0)
    sheet = layout.place(_graph([a, b, c], [(c, a), (c, b)]))
    placed = {node.id: node for node in sheet.nodes}
    assert (placed[a].x, placed[a].y) == (0, 0)
    assert (placed[b].x, placed[b].y) == (style.COLUMN_PITCH, 0)
    # c leans on both, so the coordinate phase puts it on their barycentre —
    # half a pitch, which the column grid alone could never draw.
    assert (placed[c].x, placed[c].y) == (style.COLUMN_PITCH // 2, -style.LAYER_PITCH)
    # Box width is a constant, so a long title never moves a neighbour.
    assert placed[a].width == style.COLUMN_PITCH - style.COLUMN_GUTTER
    for node in sheet.nodes:
        for value in (node.x, node.y, node.width, node.height):
            assert type(value) is int
    for edge in sheet.edges:
        for point in edge.points:
            assert (type(point.x), type(point.y)) == (int, int)


def test_every_edge_uses_the_one_anchor_per_box_side() -> None:
    """All edges leave a node from its top-centre and arrive at its
    bottom-centre; distributing anchors by edge index would move every edge on a
    node when one edge is added."""
    premise = _cid("a", 0)
    dependents = [_cid("b", n) for n in range(3)]
    sheet = layout.place(_graph([premise, *dependents], [(dep, premise) for dep in dependents]))
    placed = {node.id: node for node in sheet.nodes}
    assert {edge.start for edge in sheet.edges} == {placed[premise].top_centre}
    assert {edge.end for edge in sheet.edges} == {placed[dep].bottom_centre for dep in dependents}


def test_the_view_box_is_the_box_union_plus_a_margin() -> None:
    a, b = _cid("a", 0), _cid("b", 0)
    sheet = layout.place(_graph([a, b], [(b, a)]))
    assert sheet.view_box == layout.ViewBox(
        min_x=-style.MARGIN,
        min_y=-style.LAYER_PITCH - style.MARGIN,
        width=style.BOX_WIDTH + 2 * style.MARGIN,
        height=style.LAYER_PITCH + style.BOX_HEIGHT + 2 * style.MARGIN,
    )


def test_adding_a_node_moves_nothing_whose_layer_and_column_are_unchanged() -> None:
    """The locality property, at the geometry level: the sheet grows upward and
    left-anchored, so a new deepest layer changes only the view box."""
    a, b = _cid("a", 0), _cid("b", 0)
    before = layout.place(_graph([a, b], [(b, a)]))
    after = layout.place(_graph([a, b, _cid("c", 0)], [(b, a), (_cid("c", 0), b)]))
    unchanged = {node.id: node for node in after.nodes if node.layer < 2}
    assert {node.id: node for node in before.nodes} == unchanged
    assert before.view_box != after.view_box


# ---------------------------------------------------------------------------
# Coordinates — the priority method
# ---------------------------------------------------------------------------


def _centres_by_layer(sheet: layout.Sheet) -> dict[int, list[int]]:
    """Every drawn box's centre x, per layer, in drawn order."""
    out: dict[int, list[int]] = {}
    for node in sheet.nodes:
        out.setdefault(node.layer, []).append(node.x + node.width // 2)
    return out


def test_a_vertex_is_pulled_onto_the_barycentre_of_its_neighbours() -> None:
    """The phase's whole claim, in its smallest form: three premises and one
    dependent leaning on all of them, which lands over the middle one instead of
    over its own index's multiple of the pitch — column 0, where the grid alone
    would have drawn it."""
    low = [_cid("l", n) for n in range(3)]
    top = _cid("u", 0)
    sheet = layout.place(_graph([*low, top], [(top, premise) for premise in low]))
    placed = {node.id: node for node in sheet.nodes}

    assert placed[top].column == 0  # the ordering did not move; the coordinate did
    assert placed[top].x == placed[low[1]].x
    assert placed[top].x == (placed[low[0]].x + placed[low[2]].x) // 2


def test_a_dummy_outranks_the_real_nodes_of_its_layer() -> None:
    """A dummy carries the highest priority, so where a chain and a real node
    want the same place the chain gets it and the node gives way — the rule
    stated from the side that costs something.

    ``middle`` and the placeholder of ``top → side`` are the only two occupants
    of their layer, and both are pulled toward ``top`` above them. The
    placeholder takes that position and pushes ``middle`` clear; ``middle`` ends
    on neither of the positions its own neighbours pull it toward.
    """
    top, middle, graph = _spanning_shape()
    sheet = layout.place(graph)
    centres = {node.id: node.x + node.width // 2 for node in sheet.nodes}
    bend = {edge.key: edge.points for edge in sheet.edges}[(top, _SIDE_LEFT)][1]

    assert bend.x == centres[top] == centres[_SIDE_LEFT]  # the chain got its own barycentre
    assert centres[middle] > bend.x
    # And the node did not get its own: it is pulled toward the mean of the two
    # occupants it joins across its bands, and the placeholder holds the column
    # it would have to cross to reach it.
    assert centres[middle] != (centres[_cid("m", 0)] + centres[top]) // 2


def test_no_two_occupants_of_a_layer_come_closer_than_the_column_pitch() -> None:
    """One box width plus the gutter, which is the blank space the grid always
    gave them — the bound that keeps the phase from drawing two boxes over each
    other, and with it the one that keeps it from reordering a layer."""
    nodes, edges = _rich_records()
    sheet = layout.place(model.build_graph(nodes=nodes, edges=edges))

    for centres in _centres_by_layer(sheet).values():
        gaps = [second - first for first, second in zip(centres, centres[1:])]
        assert all(gap >= style.COLUMN_PITCH for gap in gaps), centres


def test_the_coordinate_phase_leaves_the_order_the_sweep_chose() -> None:
    """``x`` ascends with ``column`` inside every layer. A phase that let a
    vertex pass its neighbour would be undoing the phase above it — and would
    do it invisibly, since the columns would still read as ordered."""
    nodes, edges = _rich_records()
    sheet = layout.place(model.build_graph(nodes=nodes, edges=edges))

    for layer in {node.layer for node in sheet.nodes}:
        placed = [node for node in sheet.nodes if node.layer == layer]
        assert [node.x for node in placed] == sorted(node.x for node in placed)
        assert [node.column for node in placed] == sorted(node.column for node in placed)


def test_the_leftmost_occupant_stands_where_column_zero_stood() -> None:
    """One global shift at the end, never a per-layer one — a per-layer shift is
    the alignment the phase just bought, thrown away."""
    low = [_cid("l", n) for n in range(3)]
    top = _cid("u", 0)
    sheet = layout.place(_graph([*low, top], [(top, premise) for premise in low]))

    assert min(node.x for node in sheet.nodes) == 0


def _long_chain_shape() -> tuple[tuple[str, str], model.ClaimGraph]:
    """Six layers, and one stroke from the second of them to the top.

    ``side`` rests on the corpus's bedrock and the top of a four-step chain
    rests on ``side``, so the stroke between them crosses three layers and draws
    through three placeholders. Those layers are already occupied — a dependent
    of each chain step stands beside it — which is what makes the column grid
    put the placeholders in different columns and bend the chain at each of
    them.

    Nothing from ``side`` leads anywhere but the top, so no route carries that
    premise and the reduction leaves the stroke: a chain to measure has to be a
    stroke the sheet still draws.
    """
    bedrock = _cid("b", 0)
    chain = [_cid("c", n) for n in range(4)]
    beside = [_cid("d", n) for n in range(3)]
    top, side = _cid("a", 0), _cid("s", 0)
    pairs = [
        (chain[0], bedrock),
        *zip(chain[1:], chain[:-1], strict=True),
        (top, chain[-1]),
        (side, bedrock),
        (top, side),
        *((beside[n], chain[n]) for n in range(3)),
    ]
    return (top, side), _graph([bedrock, *chain, *beside, top, side], pairs)


def _bends(chain: layout.PlacedEdge) -> int:
    return sum(1 for segment in chain.segments if segment.start.x != segment.end.x)


def _horizontal(chain: layout.PlacedEdge) -> int:
    return sum(abs(segment.end.x - segment.start.x) for segment in chain.segments)


def test_a_dummy_chain_comes_out_straighter_than_the_column_grid_draws_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The measurement the phase exists for, against the thing it replaced:
    :data:`layout.COORDINATE_ROUNDS` at zero *is* the column grid, every
    occupant at its own index's multiple of the pitch."""
    pair, graph = _long_chain_shape()
    swept = {edge.key: edge for edge in layout.place(graph).edges}[pair]

    monkeypatch.setattr(layout, "COORDINATE_ROUNDS", 0)
    gridded = {edge.key: edge for edge in layout.place(graph).edges}[pair]

    assert len(swept.points) == len(gridded.points) == 5  # three placeholders
    assert _bends(swept) < _bends(gridded)
    assert _horizontal(swept) < _horizontal(gridded)


# ---------------------------------------------------------------------------
# Dummy nodes — an edge across layers is a chain, and its placeholders take columns
# ---------------------------------------------------------------------------


#: The two ``side`` ids :func:`_spanning_shape` is built with. Both rest on the
#: same bedrock; what differs is where the sweep's start key puts the side node
#: among the occupants of its own layer, and with it where its chain starts.
_SIDE_LEFT, _SIDE_RIGHT = _cid("b", 1), _cid("s", 0)


def _spanning_shape(side: str = _SIDE_LEFT) -> tuple[str, str, model.ClaimGraph]:
    """A three-step chain, and a claim beside it that the chain's top rests on.

    ``side`` rests on the chain's own bedrock and ``top`` rests on ``side``, so
    ``side`` stands one layer up and its stroke to ``top`` skips the layer
    ``middle`` occupies. **The reduction leaves that stroke alone**: the only
    way from ``side`` to ``top`` is the stroke itself, ``side`` reaching no
    other claim — which is what a spanning stroke has to look like now that a
    premise a drawn route already carries is not drawn. The old shape here was
    the triangle ``top → middle → bottom`` plus ``top → bottom``, and that
    stroke is exactly the one the route replaces.

    ``top``'s id sorts **before** ``middle``'s, so the chain's dummy key
    ``(top, side)`` sorts before the middle node's own key and starts in the
    left column of the layer they share — which is what makes the "a dummy takes
    a real column" claim visible rather than assumed.
    """
    bedrock, first, middle, top = _cid("b", 0), _cid("m", 0), _cid("m", 1), _cid("a", 0)
    pairs = [(first, bedrock), (middle, first), (top, middle), (side, bedrock), (top, side)]
    return top, middle, _graph([bedrock, first, middle, top, side], pairs)


def test_an_edge_skipping_a_layer_draws_as_two_segments_through_one_dummy() -> None:
    top, middle, graph = _spanning_shape()
    sheet = layout.place(graph)
    assert _layers(sheet)[middle] + 1 == _layers(sheet)[top]

    chains = {edge.key: edge.points for edge in sheet.edges}
    # The layer-adjacent edges are two points each; the spanning one bends once.
    assert [len(points) for key, points in chains.items() if key != (top, _SIDE_LEFT)] == [2, 2, 2, 2]
    bends = chains[(top, _SIDE_LEFT)]
    assert len(bends) == 3
    # The bend sits on the middle node's own layer, at that layer's own height.
    assert bends[1].y == -_layers(sheet)[middle] * style.LAYER_PITCH + style.BOX_HEIGHT // 2


def test_a_dummy_takes_a_real_column_and_shifts_the_node_beside_it() -> None:
    """The claim the whole row turns on. Without the spanning stroke the middle
    node is the only occupant of its layer; with it the dummy sorts first, takes
    column 0 and the node is the second column — a placeholder interpolated
    along the old straight line would leave it where it was."""
    top, middle, graph = _spanning_shape()
    bedrock, first = _cid("b", 0), _cid("m", 0)
    without = _graph(
        [bedrock, first, middle, top, _SIDE_LEFT],
        [(first, bedrock), (middle, first), (top, middle), (_SIDE_LEFT, bedrock)],
    )

    assert _columns(layout.place(without))[middle] == 0
    sheet = layout.place(graph)
    placed = {node.id: node for node in sheet.nodes}
    bend = {edge.key: edge.points for edge in sheet.edges}[(top, _SIDE_LEFT)][1]

    assert placed[middle].column == 1
    # The column the node gave up is the one the placeholder is standing in.
    assert bend.x == style.BOX_WIDTH // 2 < placed[middle].x


def test_an_edge_spanning_three_layers_draws_as_three_segments_through_two_dummies() -> None:
    """One more layer in the chain beneath it, so the same stroke spans two."""
    bedrock, top, side = _cid("b", 0), _cid("a", 0), _cid("s", 0)
    chain = [_cid("m", n) for n in range(3)]
    sheet = layout.place(
        _graph(
            [bedrock, *chain, top, side],
            [
                (chain[0], bedrock),
                *zip(chain[1:], chain[:-1], strict=True),
                (top, chain[-1]),
                (side, bedrock),
                (top, side),
            ],
        )
    )
    points = {edge.key: edge.points for edge in sheet.edges}[(top, side)]

    assert len(points) == 4
    # The bends ascend one layer at a time, between the two anchors.
    assert [point.y for point in points] == sorted((point.y for point in points), reverse=True)
    assert [point.y for point in points[1:3]] == [
        -2 * style.LAYER_PITCH + style.BOX_HEIGHT // 2,
        -3 * style.LAYER_PITCH + style.BOX_HEIGHT // 2,
    ]


def test_a_dummy_is_placed_over_the_corpus_and_not_over_the_sheets_own_edges() -> None:
    """A domain sheet that draws neither end of the spanning edge still carries
    the column its dummy took, or a node would move between views."""
    _, middle, graph = _spanning_shape()
    full = {node.id: node for node in layout.place(graph).nodes}
    selected = layout.place(graph, include={middle})

    assert [edge.key for edge in selected.edges] == []
    assert {node.id: node for node in selected.nodes} == {middle: full[middle]}


def test_a_same_layer_edge_carries_no_dummy() -> None:
    """Nothing lies strictly between one layer and itself."""
    x, y = _cid("x", 0), _cid("x", 1)
    sheet = layout.place(_graph([x, y], [(x, y), (y, x)]))  # a two-cycle, both at layer 1
    assert {placed.layer for placed in sheet.nodes} == {1}
    assert all(len(edge.points) == 2 for edge in sheet.edges)


# ---------------------------------------------------------------------------
# The crossing-reduction sweep — in-layer order is computed, not looked up
# ---------------------------------------------------------------------------


def test_the_sweep_uncrosses_a_crossing_an_order_can_remove() -> None:
    """The row's own claim. Two premises and two dependents, wired so that the
    id-ascending start order draws the pair crossed; the sweep reorders the
    upper layer and the crossing is gone."""
    low = [_cid("l", n) for n in range(2)]
    high = [_cid("u", n) for n in range(2)]
    sheet = layout.place(_graph([*low, *high], [(high[0], low[1]), (high[1], low[0])]))

    assert sheet.hops == ()
    # Layer 0 is unconstrained and keeps its start order; layer 1 is the one
    # that moved, and it moved against its own ids.
    assert _columns(sheet) == {low[0]: 0, low[1]: 1, high[1]: 0, high[0]: 1}


def test_the_sweep_leaves_an_order_it_cannot_improve_where_it_found_it() -> None:
    """Every occupant of a complete bipartite shape has the same barycentre, so
    every rank ties and the start order is what draws — which is what makes a
    tie rule, rather than a sort's own stability, the thing to state."""
    sheet = layout.place(_complete_bipartite(3))
    ids_by_layer = {layer: [n.id for n in sheet.nodes if n.layer == layer] for layer in (0, 1)}
    assert ids_by_layer == {layer: sorted(ids) for layer, ids in ids_by_layer.items()}


def test_an_occupant_with_no_neighbour_across_a_band_holds_its_place() -> None:
    """Such an occupant scores its own index, so a layer reordering around it
    neither drags it along nor blocks the occupants that do move.

    A two-cycle is the case at hand: its edge lies **within** layer 1, so it
    contributes no segment to the band beneath and its two members have nothing
    across that band to be ranked against — while the two dependents sharing
    their layer are swapped by the sweep. (An orphan is no longer an instance of
    this: degree zero leaves the hierarchy altogether.)
    """
    low = [_cid("l", n) for n in range(2)]
    high = [_cid("u", n) for n in range(2)]
    ring = [_cid("x", n) for n in range(2)]
    sheet = layout.place(
        _graph([*low, *high, *ring], [(high[0], low[1]), (high[1], low[0]), (ring[0], ring[1]), (ring[1], ring[0])])
    )

    assert _layers(sheet) == {low[0]: 0, low[1]: 0, high[0]: 1, high[1]: 1, ring[0]: 1, ring[1]: 1}
    assert sheet.hops == ()
    assert _columns(sheet) == {low[0]: 0, low[1]: 1, high[1]: 0, high[0]: 1, ring[0]: 2, ring[1]: 3}


def test_a_dummy_is_swept_like_any_other_occupant_of_its_layer() -> None:
    """A dummy takes a column, so it takes a place in the ordering too: here the
    start key puts it left of the real node sharing its layer and the sweep
    moves it right, which is the crossing the routing would otherwise draw.

    The spanning shape is taken with the side node whose id sorts *after* the
    chain's, so the layer the placeholder lands in starts with the placeholder
    on the left and the sweep is what puts it on the right.
    """
    top, middle, graph = _spanning_shape(_SIDE_RIGHT)
    sheet = layout.place(graph)

    assert _layers(sheet)[middle] == 2
    # The dummy's key starts left of the middle node's; after the sweep the
    # middle node holds column 0 and the chain bends in column 1.
    assert _columns(sheet)[middle] == 0
    bend = {edge.key: edge.points for edge in sheet.edges}[(top, _SIDE_RIGHT)][1]
    assert bend == layout.Point(
        style.COLUMN_PITCH + style.BOX_WIDTH // 2,
        -2 * style.LAYER_PITCH + style.BOX_HEIGHT // 2,
    )
    assert sheet.hops == ()


# ---------------------------------------------------------------------------
# The orphan block — a node with no edges is not part of the hierarchy
# ---------------------------------------------------------------------------


def _block(sheet: layout.Sheet) -> list[layout.PlacedNode]:
    """Every orphan drawn, in emission order."""
    return [node for node in sheet.nodes if node.layer < 0]


def _orphan_graph(orphans: int) -> tuple[list[str], model.ClaimGraph]:
    """A two-node hierarchy plus ``orphans`` unattached nodes, ids sorting after it."""
    a, b = _cid("a", 0), _cid("a", 1)
    lonely = [_cid("z", n) for n in range(orphans)]
    return lonely, _graph([a, b, *lonely], [(b, a)])


def test_the_block_fills_rows_of_the_declared_width_below_the_baseline() -> None:
    """Four to a row, in the same ascending-id key every occupant starts from,
    and the fifth opens a second row one layer pitch further down."""
    lonely, graph = _orphan_graph(style.ORPHAN_ROW + 1)
    sheet = layout.place(graph)
    placed = {node.id: node for node in sheet.nodes}

    for index, node_id in enumerate(lonely):
        row, column = divmod(index, style.ORPHAN_ROW)
        assert (placed[node_id].column, placed[node_id].x) == (column, column * style.COLUMN_PITCH)
        assert placed[node_id].y == (row + 1) * style.LAYER_PITCH
    # Below the whole hierarchy, whose boxes all sit at y <= 0.
    assert min(node.y for node in _block(sheet)) > style.BOX_HEIGHT


def test_the_block_is_emitted_bottom_row_first_like_every_other_row_of_the_sheet() -> None:
    """``(layer, column)`` ascending runs from the bottom of the sheet upward,
    and the block's rows carry negative layers, so its lowest row is emitted
    first — one reading of the emission key rather than a second one for the
    block."""
    lonely, graph = _orphan_graph(style.ORPHAN_ROW + 2)
    block = _block(layout.place(graph))

    assert [node.id for node in block] == lonely[style.ORPHAN_ROW :] + lonely[: style.ORPHAN_ROW]
    assert not any(node.cycle_member for node in block)


def test_the_orphans_are_off_the_layer_census_and_out_of_layer_zero() -> None:
    """The defect the row exists to fix: unattached nodes inflating layer 0's
    width until the sheet is one unreadable row."""
    lonely, graph = _orphan_graph(20)
    sheet = layout.place(graph)

    assert sheet.layer_count == 2
    assert [node.id for node in sheet.nodes if node.layer == 0] == [_cid("a", 0)]
    assert len(_block(sheet)) == len(lonely)


def test_a_graph_of_nothing_but_orphans_occupies_no_layer_at_all() -> None:
    ids = [_cid("a", n) for n in range(3)]
    sheet = layout.place(_graph(ids, []))

    assert sheet.layer_count == 0
    assert [node.id for node in sheet.nodes] == ids
    assert sheet.edges == () and sheet.hops == ()


def test_the_view_box_unions_the_block() -> None:
    """One more extent, on the same rule as every box and every stroke vertex —
    a sheet whose frame stopped at the hierarchy would clip the block off."""
    _, graph = _orphan_graph(2)
    sheet = layout.place(graph)
    lowest = max(node.y + node.height for node in sheet.nodes)

    assert sheet.view_box.min_y + sheet.view_box.height == lowest + style.MARGIN
    assert sheet.view_box.width >= 2 * style.COLUMN_PITCH - style.COLUMN_GUTTER


def test_an_orphan_carries_no_stroke_and_so_moves_no_crossing() -> None:
    """Degree zero is the whole argument: the block cannot reach the hop scan."""
    low = [_cid("l", n) for n in range(2)]
    high = [_cid("u", n) for n in range(2)]
    pairs = [(up, down) for up in high for down in low]
    lonely = [_cid("z", n) for n in range(5)]
    bare = layout.place(_graph([*low, *high], pairs))
    blocked = layout.place(_graph([*low, *high, *lonely], pairs))

    assert len(bare.hops) == len(blocked.hops) == 1
    assert bare.hops == blocked.hops
    assert bare.edges == blocked.edges


def test_orphan_ness_is_the_corpus_graphs_and_never_the_selected_sheets() -> None:
    """A node whose only edge leaves the selection keeps its layer, and an orphan
    keeps its place in the block — or a node would move between the grid and the
    hierarchy depending on which domain was rendered."""
    a, b, lonely = _cid("a", 0), _cid("a", 1), _cid("z", 0)
    graph = _graph([a, b, lonely], [(b, a)])
    full = {node.id: node for node in layout.place(graph).nodes}
    selected = {node.id: node for node in layout.place(graph, include={b, lonely}).nodes}

    assert selected == {b: full[b], lonely: full[lonely]}
    assert selected[b].layer == 1


# ---------------------------------------------------------------------------
# Hop geometry — four fixtures and the crossing rules
# ---------------------------------------------------------------------------


def _complete_bipartite(size: int) -> model.ClaimGraph:
    """``size`` premises and ``size`` dependents, every pair joined.

    The shape the crossing-reduction sweep cannot improve: a complete bipartite
    graph draws the same number of crossings under **every** in-layer order, so
    the glyphs these fixtures are about are there whatever the sweep does with
    the columns. A hand-built reversal no longer serves — the sweep is what
    removes one of those, and :func:`test_the_sweep_uncrosses_a_crossing_an_order_can_remove`
    is where that belongs.
    """
    low = [_cid("l", n) for n in range(size)]
    high = [_cid("u", n) for n in range(size)]
    return _graph([*low, *high], [(up, down) for up in high for down in low])


def test_two_crossing_edges_yield_exactly_one_glyph_on_the_higher_key_edge() -> None:
    """Four edges between two premises and two dependents; exactly one of their
    pairs crosses, and no ordering of either layer changes that."""
    sheet = layout.place(_complete_bipartite(2))
    assert len(sheet.hops) == 1
    hop = sheet.hops[0]
    # Which edge hops is the stable key, never the scan order: of the two
    # crossing edges, the one whose pair sorts greater.
    assert (hop.hopping, hop.crossed) == ((_cid("u", 1), _cid("l", 0)), (_cid("u", 0), _cid("l", 1)))
    # The crossing point is exact, and it is interior to both segments.
    assert (hop.x, hop.y) == (
        Fraction(style.COLUMN_PITCH + style.BOX_WIDTH, 2),
        Fraction(style.BOX_HEIGHT - style.LAYER_PITCH, 2),
    )


@pytest.mark.parametrize("shape", ["fan-in", "fan-out"])
def test_edges_sharing_a_node_are_skipped_by_identity(shape: str) -> None:
    """Every fan-in and fan-out shares an endpoint; a naive test flags all of
    them and the sheet fills with glyphs at every junction."""
    hub = _cid("h", 0)
    others = [_cid("a", n) for n in range(3)]
    pairs = [(hub, other) for other in others] if shape == "fan-in" else [(other, hub) for other in others]
    sheet = layout.place(_graph([hub, *others], pairs))
    assert len(sheet.edges) == 3
    assert sheet.hops == ()


def test_edges_on_one_vertical_line_carry_no_glyph() -> None:
    """``den == 0`` is the whole parallel/colinear test, and nothing divides.

    A chain one node wide puts every segment on one vertical line. The two edges
    checked share no node, so the scan does reach them — and rejects them on the
    denominator alone.

    *Colinear **overlap** is unreachable through :func:`layout.place` once edges
    are chains*: every segment is layer-adjacent, and two segments in one layer
    band lie on the same line only if they join the same two columns, which
    makes them the same edge.
    """
    a, b, c, d = (_cid("a", n) for n in range(4))
    sheet = layout.place(_graph([a, b, c, d], [(b, a), (c, b), (d, c)]))
    placed = {edge.key: edge for edge in sheet.edges}
    lower, upper = placed[(b, a)], placed[(d, c)]
    assert {b, a}.isdisjoint({d, c})
    assert lower.start.x == lower.end.x == upper.start.x == upper.end.x
    assert sheet.hops == ()


def test_three_near_coincident_crossings_yield_three_overlapping_glyphs() -> None:
    """The accepted case, pinned by assertion rather than left to accident:
    glyphs closer than twice the hop radius abut or overlap and are **not**
    merged, because merging is order-dependent.

    Three premises and three dependents, every pair joined: nine crossings under
    any order, three of them concurrent at the sheet's centre because the three
    edges of the reversal run meet there.
    """
    sheet = layout.place(_complete_bipartite(3))
    assert len(sheet.hops) == 9

    points = Counter((hop.x, hop.y) for hop in sheet.hops)
    centre, count = points.most_common(1)[0]
    assert count == 3  # three crossings at one point, three glyphs
    coincident = [hop for hop in sheet.hops if (hop.x, hop.y) == centre]
    for first in coincident:
        for second in coincident:
            separation = (first.x - second.x) ** 2 + (first.y - second.y) ** 2
            assert separation < (2 * style.HOP_RADIUS) ** 2
    # Each glyph names its own pair, so nothing was collapsed on the way out.
    assert len({(hop.hopping, hop.crossed) for hop in coincident}) == 3


def _hop_key(hop: layout.Hop) -> tuple:
    return (hop.hopping, hop.hopping_segment, hop.crossed, hop.crossed_segment)


def test_hops_are_emitted_in_the_declared_order() -> None:
    """Hops sort by ``(hopping pair, hopping segment, crossed pair, crossed segment)``.

    The segment indices are what keeps the key total now that one edge is a
    chain and two chains can cross more than once.
    """
    sheet = layout.place(_complete_bipartite(3))
    assert len(sheet.hops) == 9  # the sort must have something to order
    assert list(sheet.hops) == sorted(sheet.hops, key=_hop_key)
    assert len({_hop_key(hop) for hop in sheet.hops}) == len(sheet.hops)


# ---------------------------------------------------------------------------
# Emission order and the sheet's own orderings
# ---------------------------------------------------------------------------


def test_nodes_are_emitted_by_layer_then_in_layer_index_and_edges_by_pair() -> None:
    ids = [_cid("a", n) for n in range(4)]
    sheet = layout.place(_graph(ids, [(ids[2], ids[0]), (ids[3], ids[1])]))
    assert list(sheet.nodes) == sorted(sheet.nodes, key=lambda node: (node.layer, node.column))
    assert list(sheet.edges) == sorted(sheet.edges, key=lambda edge: edge.key)


# ---------------------------------------------------------------------------
# The geometry is a function of the record set, not of its order
# ---------------------------------------------------------------------------


def _rich_records() -> tuple[list[kb_index.Claim], list[kb_index.DependsOnEdge]]:
    """A shape exercising every ordering key declared at this level: two
    layers of crossing edges, a fan, a residual cycle, a ghost id, an isolated
    node, a merged context pair and a two-relation conflict."""
    low = [_cid("l", n) for n in range(3)]
    high = [_cid("u", n) for n in range(3)]
    cycle = [_cid("x", n) for n in range(2)]
    nodes = [_claim(node_id) for node_id in (*low, *high, *cycle, _cid("z", 0))]
    edges = [
        _edge(high[2], low[0]),
        _edge(high[0], low[2]),
        _edge(high[1], low[1]),
        _edge(high[1], low[0], context="beta"),
        _edge(high[1], low[0], context="alpha"),
        _edge(high[0], low[0], "supports", fraction=0.5),
        _edge(high[0], low[0], "depends"),
        _edge(cycle[0], cycle[1]),
        _edge(cycle[1], cycle[0]),
        _edge(high[2], "clm-ghostx"),
    ]
    return nodes, edges


def test_shuffling_the_loaded_records_changes_no_geometry() -> None:
    """The shuffle test at the geometry level: a coder who sorts nowhere
    passes a golden and fails this, and so does a sweep that walks a dict built
    in record order."""
    nodes, edges = _rich_records()
    reference = layout.place(model.build_graph(nodes=nodes, edges=edges))
    assert reference.hops  # the fixture must actually exercise the hop scan
    assert any(node.cycle_member for node in reference.nodes)
    # And it must actually exercise the sweep: a layer whose drawn order is no
    # longer its ids ascending is the evidence that the ordering was computed.
    swept = [node.id for node in reference.nodes if node.layer == 1]
    assert swept != sorted(swept)

    rng = random.Random(20260904)
    for _ in range(20):
        rng.shuffle(nodes)
        rng.shuffle(edges)
        assert layout.place(model.build_graph(nodes=nodes, edges=edges)) == reference


def test_placing_the_same_graph_twice_is_identical() -> None:
    nodes, edges = _rich_records()
    graph = model.build_graph(nodes=nodes, edges=edges)
    assert layout.place(graph) == layout.place(graph)


# ---------------------------------------------------------------------------
# Sheet selection — layers stay the corpus's, on every sheet
# ---------------------------------------------------------------------------


def test_a_selected_sheet_keeps_every_coordinate_the_full_sheet_gave_it() -> None:
    """A node's layer is a property of the corpus, not of the sheet it
    appears on — recomputing per sheet would move a node between views."""
    a, b, c = _cid("a", 0), _cid("b", 0), _cid("c", 0)
    graph = _graph([a, b, c], [(b, a), (c, b)])
    full = {node.id: node for node in layout.place(graph).nodes}
    selected = layout.place(graph, include={b, c})
    assert [node.id for node in selected.nodes] == [b, c]
    assert {node.id: node for node in selected.nodes} == {b: full[b], c: full[c]}


def test_a_selected_sheet_draws_only_edges_whose_both_ends_it_draws() -> None:
    a, b, c = _cid("a", 0), _cid("b", 0), _cid("c", 0)
    sheet = layout.place(_graph([a, b, c], [(b, a), (c, b)]), include={b, c})
    assert [edge.key for edge in sheet.edges] == [(c, b)]
    assert sheet.hops == ()


# ---------------------------------------------------------------------------
# The concentric arrangement — one ring per layer
# ---------------------------------------------------------------------------

_RING_FORMS = ["ring-rectangle", "ring-ellipse"]
_PLACEMENTS = ["linear", *_RING_FORMS]


def _chain(length: int) -> tuple[list[str], model.ClaimGraph]:
    """A chain of ``length`` claims, bedrock first — one occupant per layer and no placeholder anywhere."""
    ids = [_cid("a", n) for n in range(length)]
    return ids, _graph(ids, [(ids[n + 1], ids[n]) for n in range(length - 1)])


def _overlaps(first: layout.PlacedNode, second: layout.PlacedNode) -> bool:
    return (
        first.x < second.x + second.width
        and second.x < first.x + first.width
        and first.y < second.y + second.height
        and second.y < first.y + first.height
    )


def test_the_ring_index_is_the_layer_counting_inward_from_bedrock(monkeypatch: pytest.MonkeyPatch) -> None:
    """The conclusions are the centre and the corpus's bedrock is the outermost ring.

    One occupant per layer, so each ring seats it at the 3 o'clock ray its
    candidates start from and the whole arrangement is one hand-computed row:
    the deepest claim at the origin, and every layer below it one
    :data:`style.RING_STEP` further out.
    """
    monkeypatch.setenv(layout.PLACEMENT_ENV, "ring-rectangle")
    ids, graph = _chain(4)
    placed = {node.id: node for node in layout.place(graph).nodes}

    for layer, node_id in enumerate(ids):
        ring = len(ids) - 1 - layer
        assert placed[node_id].centre == layout.Point(ring * style.RING_STEP * style.COLUMN_PITCH, 0)


def test_a_ring_steps_a_whole_ring_step_outside_the_one_within_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """What separates one ring from the next is :data:`style.RING_STEP` and
    nothing else — the constant that exists so that the spacing at which the
    nested rectangles stop tiling a lattice is one edit to find."""
    monkeypatch.setenv(layout.PLACEMENT_ENV, "ring-rectangle")
    ids, graph = _chain(3)
    placed = {node.id: node for node in layout.place(graph).nodes}
    radii = [placed[node_id].centre.x for node_id in reversed(ids)]

    gaps = [second - first for first, second in zip(radii, radii[1:])]
    assert gaps == [style.RING_STEP * style.COLUMN_PITCH] * len(gaps)


@pytest.mark.parametrize("placement", _PLACEMENTS)
def test_no_two_boxes_of_a_sheet_are_drawn_over_each_other(monkeypatch: pytest.MonkeyPatch, placement: str) -> None:
    """The separation rule, which is a property of two placed rectangles and of
    no arrangement: two occupants stand a column pitch apart horizontally or a
    layer pitch apart vertically, so no box is ever drawn over another, orphan
    block included."""
    monkeypatch.setenv(layout.PLACEMENT_ENV, placement)
    nodes, edges = _rich_records()
    sheet = layout.place(model.build_graph(nodes=nodes, edges=edges))

    assert len(sheet.nodes) > 1
    for first, second in combinations(sheet.nodes, 2):
        assert not _overlaps(first, second), (placement, first.id, second.id)


@pytest.mark.parametrize("placement", _PLACEMENTS)
def test_every_coordinate_is_an_integer_under_every_arrangement(
    monkeypatch: pytest.MonkeyPatch, placement: str
) -> None:
    """``layout``'s no-float rule is the arrangement's too: the concentric placer
    walks its ellipse by :func:`math.isqrt` rather than by ``libm``, which is not
    byte-reproducible across hosts."""
    monkeypatch.setenv(layout.PLACEMENT_ENV, placement)
    nodes, edges = _rich_records()
    sheet = layout.place(model.build_graph(nodes=nodes, edges=edges))

    for node in sheet.nodes:
        assert (type(node.x), type(node.y)) == (int, int)
    for edge in sheet.edges:
        for point in edge.points:
            assert (type(point.x), type(point.y)) == (int, int)


@pytest.mark.parametrize("placement", _RING_FORMS)
def test_a_ring_sheet_anchors_every_stroke_at_the_box_centres(monkeypatch: pytest.MonkeyPatch, placement: str) -> None:
    """A ring has no up, so the top-edge-to-bottom-edge anchors the layered sheet
    uses would put a stroke on the wrong side of half the boxes. The emitter
    draws the boxes opaque and last, so a centre-anchored stroke still leaves
    from under its own box edge."""
    monkeypatch.setenv(layout.PLACEMENT_ENV, placement)
    premise = _cid("a", 0)
    dependents = [_cid("b", n) for n in range(3)]
    sheet = layout.place(_graph([premise, *dependents], [(dep, premise) for dep in dependents]))
    placed = {node.id: node for node in sheet.nodes}

    assert sheet.edges
    for edge in sheet.edges:
        assert {edge.start, edge.end} == {placed[end].centre for end in edge.key}


@pytest.mark.parametrize("placement", _RING_FORMS)
def test_the_block_stands_below_a_ring_sheet_and_flush_with_its_left_edge(
    monkeypatch: pytest.MonkeyPatch, placement: str
) -> None:
    """The one thing a ring sheet changes about the block: the disc surrounds the
    origin, so ``below the baseline`` is no longer below anything — the floor is
    read off the occupants instead."""
    monkeypatch.setenv(layout.PLACEMENT_ENV, placement)
    _, graph = _orphan_graph(style.ORPHAN_ROW + 1)
    sheet = layout.place(graph)
    disc = [node for node in sheet.nodes if node.layer >= 0]
    block = _block(sheet)

    assert min(node.x for node in block) == min(node.x for node in disc)
    assert min(node.y for node in block) == max(node.y + node.height for node in disc) + style.LAYER_GAP
    assert [node.y for node in block] == sorted((node.y for node in block), reverse=True)


@pytest.mark.parametrize("placement", _RING_FORMS)
def test_a_ring_sheet_is_a_function_of_the_records_and_not_of_their_order(
    monkeypatch: pytest.MonkeyPatch, placement: str
) -> None:
    """The shuffle test again, against the arrangement rather than the phases
    above it: a placer that walked a set would pass every geometry fixture here
    and fail this."""
    monkeypatch.setenv(layout.PLACEMENT_ENV, placement)
    nodes, edges = _rich_records()
    reference = layout.place(model.build_graph(nodes=nodes, edges=edges))

    rng = random.Random(20260919)
    for _ in range(10):
        rng.shuffle(nodes)
        rng.shuffle(edges)
        assert layout.place(model.build_graph(nodes=nodes, edges=edges)) == reference


def test_an_unrecognised_arrangement_is_refused_rather_than_drawn(monkeypatch: pytest.MonkeyPatch) -> None:
    """The variable arrives from a developer's shell, and the vocabulary it is
    read against is closed. A sheet silently drawn by an arrangement nobody asked
    for is indistinguishable from one that was — and the freshness gate would
    report it as a change to the graph."""
    monkeypatch.setenv(layout.PLACEMENT_ENV, "concentric")
    _, graph = _chain(2)

    with pytest.raises(ValueError, match=layout.PLACEMENT_ENV):
        layout.place(graph)


def test_the_layered_arrangement_is_still_reachable(monkeypatch: pytest.MonkeyPatch) -> None:
    """It is the comparison baseline every ring form is judged against, so it is
    selectable rather than deleted — and it still draws the frame it always drew,
    layer 0 on the baseline and the sheet growing upward."""
    monkeypatch.setenv(layout.PLACEMENT_ENV, "linear")
    ids, graph = _chain(3)
    placed = {node.id: node for node in layout.place(graph).nodes}

    assert [placed[node_id].y for node_id in ids] == [-layer * style.LAYER_PITCH for layer in range(len(ids))]
    assert layout.DEFAULT_PLACEMENT != "linear"


# ---------------------------------------------------------------------------
# No epsilon, no float, no division — mechanically
# ---------------------------------------------------------------------------


def _module_tree(module) -> ast.Module:
    return ast.parse(Path(module.__file__).read_text(encoding="utf-8"))


@pytest.mark.parametrize("module", [layout, style], ids=["layout", "style"])
def test_the_geometry_modules_hold_no_float_and_no_true_division(module) -> None:
    """No epsilon exists anywhere in this design, and every ``style``
    magnitude is an ``int``. True division is the operator that would
    produce a float from exact inputs; integer floor division is not, and is
    what the box centres use."""
    tree = _module_tree(module)
    floats = [node for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, float)]
    divisions = [node for node in ast.walk(tree) if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)]
    assert floats == []
    assert divisions == []


def test_every_style_magnitude_is_an_integer() -> None:
    magnitudes = {
        name: value
        for name, value in vars(style).items()
        if not name.startswith("_") and isinstance(value, (int, float)) and not isinstance(value, bool)
    }
    assert magnitudes  # the sweep must actually reach the constants
    assert all(type(value) is int for value in magnitudes.values()), magnitudes


# ---------------------------------------------------------------------------
# style.py's declared constants
# ---------------------------------------------------------------------------


def test_the_census_relation_order_matches_the_dedupe_precedence() -> None:
    """``style`` is forbidden from importing ``model``, so the two constants
    are pinned equal by this test rather than by an import: ``model``'s is
    the dedupe semantics, ``style``'s is the report order."""
    assert style.CENSUS_RELATIONS == model.RELATION_PRECEDENCE


def test_the_band_palette_covers_the_ladder_and_the_pending_bucket() -> None:
    from kb_tools import kb_schema

    assert set(style.BAND_PALETTE) == {band.slug for band in kb_schema.BUILD_BAND_LADDER} | {
        kb_schema.UNKNOWN_BAND_SLUG
    }
    assert style.BAND_PALETTE[kb_schema.UNKNOWN_BAND_SLUG] == style.PENDING_FILL
    # One colour per band, all distinct — a rung that repeats another's hex
    # would make a rescore invisible.
    assert len(set(style.BAND_PALETTE.values())) == len(style.BAND_PALETTE)


def test_style_declares_no_node_type_order_of_its_own() -> None:
    """A node-type census iterates ``kb_schema.NODE_KINDS``. A tuple here would
    be a second spelling of that vocabulary, and the kind it omitted — ``work``
    was the one — is the kind the census would never report."""
    assert not [name for name in vars(style) if "NODE_TYPE" in name or "NODE_KIND" in name]


def test_the_declared_census_tuples_are_the_ones_the_plan_names() -> None:
    assert style.CENSUS_DEFECT_CLASSES == (
        "ghost-id",
        "back-edge",
        "isolated-node",
        "disconnected-component",
        "relation-conflict",
    )


def test_the_box_grid_is_metric_free_and_derived_from_the_label_cap() -> None:
    """Box width is a function of a character count and the pinned font;
    nothing measures text."""
    assert style.BOX_WIDTH == 2 * style.BOX_PADDING_X + style.LABEL_CHARS * style.CHAR_ADVANCE
    assert style.BOX_WIDTH == style.COLUMN_PITCH - style.COLUMN_GUTTER
    assert style.BOX_HEIGHT < style.LAYER_PITCH
    assert style.MARGIN > style.HOP_RADIUS
