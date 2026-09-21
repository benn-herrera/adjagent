"""Placed geometry for the claim-graph sheet: model in, coordinates out.

Layering, in-layer ordering and coordinates, edge routing through dummy nodes,
and hop detection with hop-side selection. It opens no file, and it knows no
colour, no font, no tag name and no URL. It reads
:mod:`kb_tools.kb_graph.style` for magnitudes and nothing else from it; if this
module ever imports ``xml``, the boundary has been crossed. The one thing it
reads from outside the graph is :data:`PLACEMENT_ENV`, a development control
with a shipped default, and the sheet is a pure function of the graph at any one
setting of it.

**An edge spanning more than one layer is a chain, not a segment.** Every layer
it crosses holds a **dummy** — a placeholder that takes a real column in that
layer, ordered among the real nodes by the sweep below — and the edge draws as
one stroke through them. How those points are joined is the emitter's and not
this module's (:func:`kb_tools.kb_graph.svg._control_points`). Two consequences, and the second is why the dummies
exist: a real node is no longer drawn under an edge path, and every segment is
layer-adjacent, so an ordering pass has something in the middle to reorder. A
dummy is never drawn and carries no label; it is mechanical, with no heuristic
and nothing to tune.

**A claim stands as far above bedrock as the argument needs and no further.**
Sugiyama's layer-assignment phase runs here, by the **network simplex** (Gansner,
Koutsofios, North & Vo 1993, *A Technique for Drawing Directed Graphs*, §2.3),
with every premise relation weighted alike and a minimum separation of one
layer. What it minimises is the **total number of layers the premise relations
span**, which is the dummy count plus the relation count — so it is the
placeholder columns of the paragraph above that it is spending, and the chain
that draws as one segment is the one it bought.

The longest-path ranking is where it starts: Kahn order out from the
premise-less nodes, every claim as high as its deepest premise pushes it
(:func:`_longest_path`). That ranking is feasible, and pointwise the lowest
feasible one there is — which is also what stands every premise-less claim on
bedrock whether the argument puts it there or not — a claim whose one dependent sits eight layers up
is drawn eight layers below it and routed through seven placeholders, and
nothing about the corpus asked for that.

The parameters, and what the phase is worth — measured over the committed
``mini-kb`` golden and every built KB in the tree, the count being the
placeholders the premise strokes are routed through:

* **One connected component at a time, each floored at layer 0.** A spanning
  tree spans one component, and two arguments with no premise path between them
  constrain each other not at all.
* **Convergence is the method's own: no tree edge left with a negative cut
  value**, at which point no exchange can shorten the sheet.
  :data:`LAYERING_PIVOTS` caps the exchanges; every intermediate ranking is
  feasible and the total never rises, so a run the cap cuts short returns a
  ranking no worse than the longest path's. The cap is headroom rather than a
  tuned number — the deepest corpus here converges in **two** pivots, most in
  none at all, the tight-tree construction having done the work.
* **Every tie is a stated key**: the component's lowest id roots the tree, the
  most negative cut value leaves and its own pair breaks that tie, and the
  tightest edge crossing the cut the other way enters, with the same tie-break.
* **The count of placeholders falls, and the sheet narrows with it**: on the
  corpus's largest sheet 58 placeholder hops become 39 and 31 routed strokes
  become 23, taking it from 7928px to 5576px and its crossings from 144 to 126;
  on the next, 9 hops become 5 and the sheet 1328px to 896px, crossings 4 to 2.
  ``mini-kb`` does not move at all — every one of its strokes is already
  layer-adjacent, so the longest-path ranking is the minimum and no pivot runs.
* **It is not free on a dense sheet, and the one regression measured is stated
  rather than averaged away.** On ``ModernCorpPristine`` — 71 strokes over 42
  claims — the placeholders fall 51 to 43 and the crossings *rise* 67 to 76,
  because the placeholders were what spread those strokes over bands the
  ordering sweep could unpick, and a shorter edge set piles into fewer of them.
  That sheet is 16% wider for it. The trade is taken because the rest of the
  corpus is where the width is.
* **The balance step is not adopted.** Gansner's own ``balance`` — moving a
  claim whose premises and dependents are equal in number to the least crowded
  rank its window admits — was measured here: it takes the regression above from
  76 crossings to 70, still above the 67 it started from, and widens that sheet
  further (2704px to 2848px). Pressing such a claim to the bottom of its window
  instead is what the simplex already returns, and to the top is the balance's
  own result. None of the three recovers the sheet, so the freedom is spent on
  the simplest rule.

**A node with no edges at all leaves the hierarchy.** Layering answers "what
does this rest on", and a node that rests on nothing and carries nothing has no
answer to give: put through the layering it lands on layer 0 beside the corpus's
real bedrock, where it says nothing and makes that layer as wide as the count of
unattached nodes. So an **orphan** — degree zero over the whole corpus
graph, which is :attr:`kb_tools.kb_graph.model.Node.isolated` — is taken out of
layer assignment entirely and drawn in a grid block below everything the
hierarchy occupies and flush with its left edge (:func:`_orphan_origin`),
:data:`style.ORPHAN_ROW` to a row, in the same stable key order every other
occupant starts from. Degree is the corpus's and never the drawn sheet's, for
the reason layers are (:func:`place`): otherwise a node would move between the
grid and the hierarchy depending on which domain was being rendered. Nothing an
orphan does can reach a crossing or a hop, there being no stroke to cross.

**In-layer order is computed, not looked up.** Sugiyama's crossing-reduction
phase runs here, as the pair of steps Gansner, Koutsofios, North & Vo (1993)
§3.1–3.2 run together. Each layer's occupants — real nodes and dummies alike —
start in the stable key order :func:`_occupants` states, and an iterated
**barycentre** sweep reorders them from there: one round is a pass up the
layers, each reordered against the one beneath it, then a pass back down, each
reordered against the one above, an occupant's rank being the mean position of
the occupants it is joined to across that band. Each round's order is then
refined by **transpose** (:func:`_transpose`), which exchanges *adjacent*
occupants of a layer wherever the exchange removes more crossings from the two
bands that layer touches than it plants, repeating until no exchange does.
Crossings that survive are still denoted by the hop glyph; the phase only makes
fewer of them.

The parameters, measured rather than assumed — over ``mini-kb`` plus 25
synthetic shapes, flat and wide two-layer graphs and multi-layer DAGs carrying
dummies, and over every built KB in the tree:

* **Barycentre, not median.** The barycentre sweep left 3251 crossings across
  that sample against the median sweep's 3706, and was best-or-equal on 18 of
  the 26 shapes against the median's 10. The median carries the better
  published approximation bound for one layer at a time; on these shapes it
  did not cash out.
* **At most :data:`SWEEP_ROUNDS` rounds, stopping on the first that does not
  improve**, and the best-scoring order any round reached is what is returned
  — so the phase never hands back a picture worse than the order it started
  from. Two rounds leaves about 15% of the crossings eight remove; thirty-two
  buys under 1% over eight.
* **Ties hold their ground**, in both steps. Occupants with equal barycentres,
  and an occupant with no neighbour across the band at all, keep the position
  they already had — which at the first pass is the start key's; and an
  exchange is made only where it *strictly* reduces, which is also what makes
  transpose's local minimum a fixed point rather than a cycle of equal-scoring
  exchanges. A transpose pass takes the layers ascending and each layer's pairs
  left to right, both stated orders rather than a container's.
* **The refinement runs on each round's candidate, not on the sweep's own
  state.** The next round's barycentre pass starts from the order the two
  passes left, never from the exchanged one — the departure from the published
  loop, and it is measured rather than preferred. A local minimum is the wrong
  place to restart a barycentre pass from: feeding the exchanged order back
  costs 22 glyphs on the corpus's largest sheet (116 against 94), while
  refining only once the sweep has converged costs 2 on its densest (66 against
  64). Refining each round's candidate takes the better of the two on every
  sheet in the tree — 162 glyphs against 184 fed back and 164 refined at the
  end. On the synthetic sample the three arrangements are within 1.5% of one
  another (1891, 1912, 1920 against the sweep's own 2177), so it is the corpus
  that decides.
* **What the refinement is worth**: across every built KB the drawn glyphs fall
  from 210 to 162, 23%; across the synthetic sample the crossings fall from
  2177 to 1920, 12%. It is the two dense sheets that carry the corpus figure —
  ``2609.09855v1``'s 131 become 94 and ``ModernCorpPristine``'s 75 become 64 —
  but the smallest sheet in the tree moves too: ``mini-kb``'s 2 crossings go to
  **0**, which no barycentre round reached, and the sheet narrows by one column
  with them. A crossing an exchange of two adjacent occupants removes is not a
  crossing a mean position finds.
* **Transpose is not free in width, and the trade is stated rather than
  averaged away.** Exchanging a pair to uncross it can leave the coordinate
  phase two occupants further apart: ``2609.09855v1``'s width-setting layer
  keeps its 36 occupants and gains two columns of slack, and the sheet grows
  5%. ``ModernCorpPristine`` goes the other way and loses 3%. The trade is
  taken because crossings are what makes a dense sheet unreadable and 5% of
  width is not — and the occupant count, which is what the width is really
  made of, does not move on either sheet.
* **Convergence is the refinement's own: the first pass that exchanges
  nothing.** :data:`TRANSPOSE_PASSES` caps the passes within one round. No pass
  can raise the crossing count, every exchange strictly lowering it, so a run
  the cap cuts short returns an order no worse than the one it was given. The
  cap is headroom rather than a tuned number — over the corpus and the
  synthetic sample the deepest refinement converged in **ten** passes and half
  of them in two or fewer.

That start key, those tie rules and that stated walk are the whole of what keeps
the result independent of the order the records were loaded in. **Locality is
not a constraint**: the phase may relocate any node it likes, and one added edge may
rearrange the sheet. Determinism is the constraint, and
``test_shuffling_the_loaded_records_changes_no_geometry`` is what holds it.

**The sheet is a set of concentric rings, one per layer.** Ring 0 is the
**deepest** layer, so the conclusions stand at the centre and the corpus's
bedrock is the outermost ring. The orientation is measured rather than assumed:
bedrock-centred leaves a 448×362 empty half-side on the arXiv corpus and costs
area on every corpus. Layering and in-layer order are untouched by this — the
two phases above run exactly as they are described, and a ring's occupants are
its layer's occupants in the order the sweep chose — so the arrangement changes
only where an occupant stands.

Two **forms** offer the rings their candidate positions and differ in nothing
else. ``rectangle`` offers an axis-aligned rectangle, its candidates one column
pitch apart along the horizontal sides and one layer pitch apart along the
vertical ones, which clears by construction and never grows. ``ellipse`` offers
a true ellipse walked in integers by :func:`math.isqrt`, whose diagonal sector
brings two consecutive rings closer than the pitch — caught by the placer's own
separation check rather than by a guessed multiplier, and paid for by the ring
growing. The separation rule is a property of two placed rectangles and never of
any ring, so it lives in :func:`_place_ring` and a form states positions alone.
One ring stands :data:`style.RING_STEP` pitches outside the ring within it; at
one pitch the rings tile a lattice and no boundary is visible, which is what
that constant exists to make a single edit.

A ring has no up, so its strokes run box centre to box centre rather than top
edge to bottom edge — the emitter draws the boxes opaque and last, so a stroke
still leaves from under its own box edge.

**The layered arrangement stays reachable and is the comparison baseline.**
:data:`PLACEMENT_ENV` selects between the three, :data:`DEFAULT_PLACEMENT` is
what ships, and neither is a consumer-facing control: nothing a user runs sets
the variable and no runner target passes it. What follows describes the layered
arrangement, which is the one those phases belong to.

**A column index is not an x coordinate.** Sugiyama's coordinate-assignment
phase runs here too, by the **priority method** (Sugiyama, Tagawa & Toda 1981).
The ordering above says who stands left of whom; this says where each of them
stands. Every occupant starts at its index times the column pitch — the grid the
ordering alone used to draw — and is then pulled toward the barycentre of the
occupants it joins across one band, layer by layer, in alternating passes up and
down. What it minimises is the **total horizontal edge length**, which is the
same thing as saying a chain through placeholders comes out near-vertical
instead of zigzagging through its own columns.

Two rules bound every move, and between them they are why the phase cannot undo
the phase above it: **an occupant never passes its neighbours in the order the
sweep chose**, and no two occupants of one layer ever come closer than
:data:`style.COLUMN_PITCH` — one box width plus the gutter, so the boxes keep
the blank space between them the grid always gave them.

The parameters, measured rather than assumed, over 25 synthetic layered DAGs —
three to six layers, two to seven nodes a layer, edges skipping up to three — in
which the phase cuts total horizontal edge length by 36%, from 359520 to 231380:

* **Priority is ``(is a dummy, degree across the band)``, descending, ties
  taking the occupants in their drawn order.** A dummy outranks every real node,
  which is what makes a long edge's chain straighten and the real nodes give way
  to it rather than the other way round; among real nodes the one with more
  neighbours to answer to moves first. An occupant moves only lower-priority
  occupants out of its way — it stops dead against an equal or higher one — so
  the vertex that most needs its position gets it. **That rank is a trade and it
  is paid on purpose**: against a degree-only rule giving a dummy no standing of
  its own, the chains come out 14% straighter (36898 against 42923 over the
  chained edges) and the sheet's total length 5% longer. A chain that runs
  straight reads as one edge; the length it costs is spread over edges that
  read as themselves either way.
* **An occupant with no neighbour across the band does not move**, exactly as in
  the ordering sweep: it has no barycentre, and inventing one for it would drag
  an isolated node around the sheet to no one's benefit. It can still be pushed.
* **At most :data:`COORDINATE_ROUNDS` rounds, stopping on the first that moves
  nothing, and the best-scoring round is what is returned.** The stop is a fixed
  point rather than the ordering sweep's stop-on-no-improvement, because total
  length is *flat* wherever a vertex sits anywhere between two neighbours: a
  round that centres such a vertex scores the same and draws better. So the
  score carries the sheet's width behind its length as a tie-break, ties go to
  the swept round, and only the starting grid is kept against a round scoring
  worse — which is what makes "no longer than the sheet it was given" hold.
  Four rounds already reach the thirty-two round total on every shape measured,
  and one round leaves about 10% of the length eight rounds remove; the cap is
  headroom rather than a tuned number.

The whole sheet is then shifted once so its leftmost occupant sits where column
zero always sat. A global shift, never a per-layer one — a per-layer shift is
alignment thrown away.

**Nothing raises on a defective graph.** A cycle, a ghost id, an isolated node
and a disconnected component are all placed, and the defects geometry decides —
cycle membership and its back edges — come out as fields for the drawing and the
report lines to read.

**The arithmetic is exact integer arithmetic and there is no epsilon anywhere.**
Every coordinate is an ``int`` because every magnitude in :mod:`style` is; the
crossing test's denominator is therefore exact, ``den == 0`` is the whole
parallel/colinear test, and nothing divides. The two non-integral quantities are
a crossing point and an ordering barycentre, and both are exact
:class:`fractions.Fraction`\\ s: the point so that its rounding happens once, at
emission, in the serializer's single number formatter rather than at an
intermediate step, and the rank so that a tie between two occupants is a tie
rather than a float comparison that rounded its way into one. The coordinate
phase's barycentre is the one quantity rounded here rather than at emission,
because what it produces *is* a coordinate: it rounds to the nearer integer by
exact integer arithmetic, so nothing about where a box lands depends on a
binary fraction.

Stdlib only.
"""

import os
from collections import defaultdict, deque
from collections.abc import Callable, Collection, Iterable
from dataclasses import dataclass
from fractions import Fraction
from functools import partial
from itertools import combinations
from math import isqrt

from kb_tools.kb_graph import style
from kb_tools.kb_graph.model import ClaimGraph, Edge, Node, premise_pair

#: One layer occupant's identity and its start-order key: a real node's id
#: alone, or the ``(source, target)`` pair of the edge a dummy stands in for.
_Key = tuple[str, ...]

#: The layering's pivot cap. One pivot swaps one tree edge for one non-tree
#: edge; the method stops earlier on its own convergence condition — no tree
#: edge left with a negative cut value — and a run cut short by this cap returns
#: a feasible ranking no longer than the one it started from. Measured, not
#: guessed — the module docstring carries the numbers.
LAYERING_PIVOTS = 512

#: The crossing-reduction sweep's round cap. A round is a pass up the layers, a
#: pass back down, and the transpose refinement; the sweep stops earlier on the
#: first round that fails to improve. Measured, not guessed — the module
#: docstring carries the numbers.
SWEEP_ROUNDS = 8

#: The transpose refinement's pass cap within one sweep round. A pass walks
#: every layer's adjacent pairs once; the refinement stops earlier at its own
#: local minimum — the first pass that exchanges nothing. Measured, not guessed
#: — the module docstring carries the numbers.
TRANSPOSE_PASSES = 16

#: The coordinate phase's round cap. A round is a pass up the layers and a pass
#: back down; the phase stops earlier at a fixed point — the first round that
#: moves nothing — and the best-scoring round is what is returned. Measured, not
#: guessed — the module docstring carries the numbers.
COORDINATE_ROUNDS = 8

#: How far one ring may grow past its own first size looking for room. A ring
#: grows because a form's candidates crowd, never because the graph is large:
#: the rectangle form's candidates are pairwise clear and clear of the ring
#: within it, so it seats at its first size always, and it is the ellipse's
#: diagonal sector that spends any of this. A ring that reaches the cap is drawn
#: on the largest ring it reached rather than refused (:func:`_rings`), so the
#: cap is headroom and never a gate.
RING_GROWTH = 64


@dataclass(frozen=True, slots=True)
class Point:
    """An exact integer point in the bottom-anchored frame."""

    x: int
    y: int


@dataclass(frozen=True, slots=True)
class PlacedNode:
    """One node's box, placed by the sheet's arrangement.

    ``x``/``y`` are the box's left and **top** edges, and the box's own centre
    is what the arrangement placed (:func:`place`): the sheet's frame is
    y-down, and where the origin sits inside it is the arrangement's to say.

    ``column`` is the box's place in its layer's left-to-right order, and it is
    no longer a coordinate under any arrangement: the layered one pulls a box
    toward its neighbours and away from its index's own multiple of the pitch,
    and the concentric one seats it on a ring where left-to-right is not a
    direction at all. What ``column`` still is, everywhere, is the sweep's
    stated order and half of the emission key.

    **A negative ``layer`` is a row of the orphan block**, not a layer: an
    orphan is outside the hierarchy (this module's docstring), and row ``r`` of
    the block takes ``layer = -(r + 1)``, which is what emits the block's lowest
    row first. Its ``column`` is its place in its own row, and the two together
    index it off the block's origin — one row pitch and one column pitch apiece,
    below everything the hierarchy occupies (:func:`_orphan_origin`). The block
    is a grid, with no coordinate phase over it and nothing to pull it toward.

    ``cycle_member`` is the residual set: a node the Kahn order never resolved.
    Cycle membership is defined as exactly that, which also sweeps in the nodes
    standing downstream of a cycle — their premises are never all resolved
    either. Both populations are unlayerable for the same reason and the picture
    says so in the same way.
    """

    node: Node
    layer: int
    column: int
    x: int
    y: int
    width: int
    height: int
    cycle_member: bool

    @property
    def id(self) -> str:
        return self.node.id

    @property
    def centre(self) -> Point:
        """The box's middle — where the arrangement placed it, and the anchor a sheet with no up uses."""
        return Point(self.x + self.width // 2, self.y + self.height // 2)

    @property
    def top_centre(self) -> Point:
        """The single anchor every edge leaving this box uses, on a sheet that has an up."""
        return Point(self.x + self.width // 2, self.y)

    @property
    def bottom_centre(self) -> Point:
        """The single anchor every edge arriving at this box uses, on a sheet that has an up."""
        return Point(self.x + self.width // 2, self.y + self.height)


@dataclass(frozen=True, slots=True)
class Segment:
    """One straight run of a chain, from its lower-layer end to its upper one."""

    start: Point
    end: Point


@dataclass(frozen=True, slots=True)
class PlacedEdge:
    """One stroke: the chain joining an edge's two box anchors.

    ``points`` runs from the lower node's top-centre, through one dummy per
    layer the edge crosses in ascending layer order, to the upper node's
    bottom-centre — "lower" being the smaller ``(layer, column)``. That reading
    coincides with premise-to-dependent whenever the premise really is lower,
    and stays deterministic when it is not — an intra-cycle edge whose endpoints
    the layering could not order, which is drawn and marked rather than hidden.

    An edge between adjacent layers, or within one, crosses nothing and carries
    the two anchors alone; an edge spanning N layers carries N−1 dummies and
    draws as N segments.
    """

    edge: Edge
    points: tuple[Point, ...]
    back_edge: bool

    @property
    def key(self) -> tuple[str, str]:
        """The ordered pair that is this edge's identity and its sort key."""
        return (self.edge.source, self.edge.target)

    @property
    def start(self) -> Point:
        """The lower node's anchor, where the chain begins."""
        return self.points[0]

    @property
    def end(self) -> Point:
        """The upper node's anchor, where the chain ends."""
        return self.points[-1]

    @property
    def segments(self) -> tuple[Segment, ...]:
        """The chain's runs, each between consecutive points."""
        return tuple(Segment(first, second) for first, second in zip(self.points, self.points[1:]))


@dataclass(frozen=True, slots=True)
class Hop:
    """One bridge glyph: where one edge's segment hops over another's.

    ``hopping`` is the edge the arc is drawn on and ``crossed`` the one it goes
    over — of the two, the pair sorting **greater** hops, a stable key rather
    than an iteration order. ``hopping_segment`` and ``crossed_segment`` index
    each edge's own :attr:`PlacedEdge.segments`, which is what keeps the
    emission key total now that two chains can cross more than once.

    ``x``/``y`` are the exact crossing point, on the straight chord between that
    run's two ends. **No line through it is stated here.** The stroke is a curve
    through the chain's vertices, so where the glyph's centre lands on it, which
    line its two endpoints sit on and which side the arc bulges toward are all
    read off the drawn stroke by the emitter
    (:func:`kb_tools.kb_graph.svg.draw_hop_over`); this module answers which
    strokes cross and where, and stating any of the rest twice is how the two
    would come to disagree.
    """

    hopping: tuple[str, str]
    hopping_segment: int
    crossed: tuple[str, str]
    crossed_segment: int
    x: Fraction
    y: Fraction


@dataclass(frozen=True, slots=True)
class ViewBox:
    """The sheet's extent: the union of every drawn box and every drawn point, plus a margin.

    The strokes enter it because a chain bends at a dummy's column, which can
    sit outside the widest box in its own layer — a `viewBox` taken from the
    boxes alone would clip the very routing the dummies exist to draw.

    The only global quantity in the document.
    """

    min_x: int
    min_y: int
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class Sheet:
    """Everything drawn, in the declared emission orders.

    ``nodes`` ascends by ``(layer, in-layer index)``, ``edges`` by
    ``(source, target)`` — one entry per edge however many segments it draws as
    — and ``hops`` by ``(hopping pair, hopping segment, crossed pair, crossed
    segment)``. No set or dict iteration order reaches any of them.

    Ascending layer runs from the bottom of the sheet upward, and the orphan
    block's rows carry negative layers (:class:`PlacedNode`), so the block's
    lowest row is emitted first and the deepest layer last — one reading of the
    key, not two.
    """

    nodes: tuple[PlacedNode, ...]
    edges: tuple[PlacedEdge, ...]
    hops: tuple[Hop, ...]
    view_box: ViewBox

    @property
    def layer_count(self) -> int:
        """How many layers the drawn hierarchy occupies — a ``FACT`` census line.

        The orphan block's rows are not layers and are not counted: a sheet of
        nothing but orphans occupies no layer, which is what its zero says.
        """
        layers = [n.layer for n in self.nodes if n.layer >= 0]
        return 0 if not layers else max(layers) + 1


def place(graph: ClaimGraph, *, include: Collection[str] | None = None) -> Sheet:
    """Place ``graph`` on the column grid and find its crossings.

    ``include``, when given, is the set of node ids this sheet draws — the domain
    selection, which is the caller's policy and not this module's.
    **Layering, orphan-ness, in-layer indices, coordinates and the dummy chains
    are computed over the whole of ``graph`` either way**, so a node occupies the
    same coordinates on a domain sheet as on the full one and never moves between
    views — and a chain bends where it bends on the full sheet, because an edge
    the domain sheet does not draw still took its columns and still pulled on
    the coordinates. Orphan-ness is in that list for the same reason and one
    more: a node whose only edge leaves the selected domain would otherwise be
    an orphan on that domain's sheet and a layered node on the full one, which
    is the same node drawn as two different facts. An edge is drawn when both its
    endpoints are; crossings are found over the edges actually drawn, since a
    glyph marks what a reader can see.

    The result is a function of ``graph`` alone: shuffling the records it was
    assembled from cannot change a byte of it — and of the arrangement, which is
    a development control with a shipped default (:data:`DEFAULT_PLACEMENT`).
    """
    hierarchy, orphans = _partition(graph)
    layers, cycle_members = _assign_layers(hierarchy, graph.edges)
    bands = _bands(graph.edges, layers)
    order = _sweep(_occupants(hierarchy, graph.edges, layers), bands)
    columns = {layer: _positions(keys) for layer, keys in order.items()}
    placement = _selected_placement()
    centres = placement.centres(order, bands)
    origin = _orphan_origin(centres)

    placed: dict[str, PlacedNode] = {}
    for node in hierarchy:
        if include is not None and node.id not in include:
            continue
        layer = layers[node.id]
        centre = centres[layer][(node.id,)]
        placed[node.id] = PlacedNode(
            node=node,
            layer=layer,
            column=columns[layer][(node.id,)],
            x=centre.x - style.BOX_WIDTH // 2,
            y=centre.y - style.BOX_HEIGHT // 2,
            width=style.BOX_WIDTH,
            height=style.BOX_HEIGHT,
            cycle_member=node.id in cycle_members,
        )
    for index, node in enumerate(orphans):
        if include is not None and node.id not in include:
            continue
        placed[node.id] = _place_orphan(node, index, origin)

    nodes = tuple(sorted(placed.values(), key=lambda p: (p.layer, p.column)))
    edges = tuple(
        _place_edge(
            edge,
            placed[edge.source],
            placed[edge.target],
            centres=centres,
            cycle_members=cycle_members,
            centre_anchored=placement.centre_anchored,
        )
        for edge in graph.edges
        if edge.source in placed and edge.target in placed
    )
    return Sheet(nodes=nodes, edges=edges, hops=_hops(edges), view_box=_view_box(nodes, edges))


# ---------------------------------------------------------------------------
# The hierarchy and the orphan block
# ---------------------------------------------------------------------------


def _partition(graph: ClaimGraph) -> tuple[tuple[Node, ...], tuple[Node, ...]]:
    """The nodes the hierarchy places, and the orphans it does not.

    An orphan is a node of degree zero over the whole corpus graph, which is
    what ``Node.isolated`` already says — read from there rather than recounted
    here, so the sheet and the defect census cannot come to disagree about which
    nodes they are. Both halves stay ascending by id, ``graph.nodes`` being so.
    """
    return (
        tuple(node for node in graph.nodes if not node.isolated),
        tuple(node for node in graph.nodes if node.isolated),
    )


def _place_orphan(node: Node, index: int, origin: Point) -> PlacedNode:
    """One orphan's box in the grid block, at its own place in the corpus's orphan order.

    ``index`` is that order — the same ascending-id key every other occupant
    starts from — so the block is a function of the graph and of nothing a
    particular sheet selected. The row and the column are the grid's own, off
    ``origin``, with no coordinate phase over either: an orphan has no
    neighbours to be pulled toward.
    """
    row, column = divmod(index, style.ORPHAN_ROW)
    return PlacedNode(
        node=node,
        layer=-(row + 1),
        column=column,
        x=origin.x + column * style.COLUMN_PITCH,
        y=origin.y + row * style.LAYER_PITCH,
        width=style.BOX_WIDTH,
        height=style.BOX_HEIGHT,
        cycle_member=False,
    )


def _orphan_origin(centres: dict[int, dict[_Key, Point]]) -> Point:
    """The block's first box: below everything the hierarchy occupies, flush with its left edge.

    Read off the placed occupants rather than off layer 0, because no
    arrangement owes the sheet a lowest layer at the bottom of it — a concentric
    sheet's bedrock is its outermost ring and surrounds everything else. On the
    layered arrangement this resolves to one layer pitch below the baseline,
    which is where the block has always stood.

    Taken over the whole hierarchy and never over the part of it a sheet
    selected, for the reason every other coordinate is (:func:`place`).
    """
    points = [point for row in centres.values() for point in row.values()]
    left = min((point.x for point in points), default=style.BOX_WIDTH // 2) - style.BOX_WIDTH // 2
    bottom = max((point.y for point in points), default=style.BOX_HEIGHT // 2) + style.BOX_HEIGHT // 2
    return Point(left, bottom + style.LAYER_GAP)


# ---------------------------------------------------------------------------
# Layering
# ---------------------------------------------------------------------------


def _premise_pairs(edges: Iterable[Edge]) -> set[tuple[str, str]]:
    """The premise relation over the deduped edge set, as ``(premise, dependent)``.

    Deduplicated: two distinct strokes can express the same premise pair — a
    ``depends`` edge ``(A, B)`` and a ``supports`` edge ``(B, A)`` both say B is
    an input to A — and counting that premise twice would leave A's in-degree
    permanently above zero and strand it in the residual set.

    Every stroke contributes one: the drawn set is the premise set, narrowed to
    it and reduced within it before geometry by
    :mod:`kb_tools.kb_graph.model`, so there is no class here to exempt and no
    pair here that a route through the others already carries.
    """
    return {premise_pair(edge) for edge in edges}


def _assign_layers(nodes: tuple[Node, ...], edges: Iterable[Edge]) -> tuple[dict[str, int], frozenset[str]]:
    """The shortest total layering the premises admit, plus the residual pass.

    Two stages over the acyclic core: the longest-path ranking, which is the
    feasible starting point, and then the network simplex that minimises total
    edge length from there (:func:`_network_simplex`). Cycle members are what
    the first stage could not resolve, and the residual pass places them.

    Iterative throughout: a recursive descent is a stack overflow on the first
    cyclic input, and this renderer's whole value on a defective graph is that it
    draws one.

    ``nodes`` is the hierarchy alone: every endpoint of every edge is in it by
    construction, an orphan being a node no edge names.

    Returns the layer of every node it was given and the residual set — the
    nodes the Kahn order never resolved, which are the cycle members.
    """
    ids = [node.id for node in nodes]  # model orders these ascending
    pairs = sorted(_premise_pairs(edges))
    premises: dict[str, list[str]] = {node_id: [] for node_id in ids}
    dependents: dict[str, list[str]] = {node_id: [] for node_id in ids}
    for premise, dependent in pairs:
        premises[dependent].append(premise)
        dependents[premise].append(dependent)

    resolved = _longest_path(ids, premises, dependents)
    cycle_members = frozenset(node_id for node_id in ids if node_id not in resolved)
    # The simplex runs over the acyclic core alone: a pair with an end in the
    # residual set has no feasible rank difference to minimise, that end's own
    # layer being the residual pass's rather than a constraint's.
    core = tuple(pair for pair in pairs if pair[0] in resolved and pair[1] in resolved)
    layers = _network_simplex(resolved, core)

    # The residual pass reads this snapshot, so a layer assigned during the pass
    # never feeds a later member's max() and the residual set is
    # order-independent — a coder who walks it as a set gets the same picture.
    snapshot = dict(layers)
    for node_id in sorted(cycle_members):
        placed = [snapshot[premise] for premise in premises[node_id] if premise in snapshot]
        # Never layer 0: bedrock is where the reader looks for the corpus's most
        # basic premises, and a broken cycle drawn there misreads the instrument
        # at exactly the moment the instrument matters.
        layers[node_id] = max(1, 1 + max(placed, default=-1))
    return layers, cycle_members


def _longest_path(
    ids: list[str],
    premises: dict[str, list[str]],
    dependents: dict[str, list[str]],
) -> dict[str, int]:
    """Longest path from the premise-less nodes, in Kahn order.

    Every node it returns is one the Kahn order resolved; the rest are the
    residual set, and the layering that consumes this says what becomes of them.
    The ranking is *feasible* — every premise sits at least one layer below its
    dependent — which is what :func:`_network_simplex` needs to start from, and
    it is the pointwise lowest such ranking.
    """
    unresolved = {node_id: len(premises[node_id]) for node_id in ids}
    layers: dict[str, int] = {node_id: 0 for node_id in ids if not premises[node_id]}
    longest: dict[str, int] = {}
    queue = deque(sorted(layers))
    while queue:
        current = queue.popleft()
        for dependent in dependents[current]:
            longest[dependent] = max(longest.get(dependent, 0), layers[current] + 1)
            unresolved[dependent] -= 1
            if unresolved[dependent] == 0:
                layers[dependent] = longest[dependent]
                queue.append(dependent)
    return layers


def _slack(pair: tuple[str, str], ranks: dict[str, int]) -> int:
    """How many layers above its floor this pair's dependent sits — never negative on a feasible ranking."""
    premise, dependent = pair
    return ranks[dependent] - ranks[premise] - 1


def _network_simplex(ranks: dict[str, int], pairs: tuple[tuple[str, str], ...]) -> dict[str, int]:
    """The feasible ranking of least total length, one connected component at a time.

    ``ranks`` is a feasible ranking to start from and ``pairs`` the premise
    relation over the same nodes; the result ranks every node ``ranks`` did.
    Each component is minimised on its own and then floored at layer 0, exactly
    as the longest-path ranking left it: a component's ranks say how its own
    claims stand relative to one another, and the sheet has nothing to say about
    how two unconnected arguments line up.
    """
    incident: dict[str, list[tuple[str, str]]] = {}
    for pair in pairs:
        incident.setdefault(pair[0], []).append(pair)
        incident.setdefault(pair[1], []).append(pair)

    out = dict(ranks)
    for members in _components(sorted(ranks), incident):
        _pivot(members, sorted({pair for node_id in members for pair in incident.get(node_id, ())}), out)
        # The component's own bedrock, wherever the pivots left it.
        floor = min(out[node_id] for node_id in members)
        for node_id in members:
            out[node_id] -= floor
    return out


def _components(ids: list[str], incident: dict[str, list[tuple[str, str]]]) -> list[list[str]]:
    """The connected components of the premise relation read undirected, each ascending by id.

    Two claims with no premise path between them constrain each other not at
    all, and a spanning tree spans one component — so the simplex runs once per
    component rather than over a graph it would have to join artificially.
    """
    seen: set[str] = set()
    out: list[list[str]] = []
    for start in ids:
        if start in seen:
            continue
        seen.add(start)
        members, queue = [start], deque([start])
        while queue:
            for node_id in (end for pair in incident.get(queue.popleft(), ()) for end in pair):
                if node_id not in seen:
                    seen.add(node_id)
                    members.append(node_id)
                    queue.append(node_id)
        out.append(sorted(members))
    return out


def _pivot(members: list[str], edges: list[tuple[str, str]], ranks: dict[str, int]) -> None:
    """Exchange tree edges until no cut value is negative, moving ``ranks`` in place.

    The loop is Gansner, Koutsofios, North & Vo (1993) §2.3 with unit weights and
    a minimum separation of one layer. Each pivot drops a tree edge whose cut
    value is negative — the cut value being what the sheet's total length would
    change by if the two sides of that edge were pulled one layer apart — and
    replaces it with the tightest edge crossing the same cut the other way,
    which is the largest move the remaining premises leave room for. Every
    intermediate ranking is feasible, and the total length falls or holds at
    every pivot, so a run cut short by the cap returns a ranking no worse than
    the one it was given.
    """
    if not edges:
        return
    tree = _tight_tree(members, edges, ranks)
    # A node's own contribution to any cut it sits behind: every premise
    # relation leaving it counts up, every one arriving counts down, so one
    # subtree sum is the whole cut value (:func:`_cut_values`).
    net = {node_id: 0 for node_id in members}
    for premise, dependent in edges:
        net[premise] += 1
        net[dependent] -= 1

    for _ in range(LAYERING_PIVOTS):
        order, parent = _rooted(tree, members[0])
        negative = [(value, pair) for pair, value in _cut_values(tree, order, parent, net).items() if value < 0]
        if not negative:
            return
        # The most negative cut leaves — the move that buys the most — and its
        # own pair breaks a tie, which is a stated key rather than the order a
        # dict happened to hand its items over in.
        leaving = min(negative)[1]
        premise_side = _premise_side(leaving, order, parent, members)
        # A negative cut value *is* one or more premise relations crossing back
        # into the premise side, and no tree edge but the leaving one crosses
        # the cut at all — so this minimum is over a non-empty set.
        distance, entering = min(
            (_slack(pair, ranks), pair)
            for pair in edges
            if pair not in tree and pair[0] not in premise_side and pair[1] in premise_side
        )
        for node_id in premise_side:
            ranks[node_id] -= distance
        tree.discard(leaving)
        tree.add(entering)


def _tight_tree(members: list[str], edges: list[tuple[str, str]], ranks: dict[str, int]) -> set[tuple[str, str]]:
    """A spanning tree of tight edges over one component, shifting ``ranks`` until one exists.

    Grown from the component's lowest id outward: a tight edge joins the tree
    for free, and where none reaches the tree the whole of what has been grown
    so far slides by the least slack any edge leaving it carries — which makes
    that edge tight and leaves every ranking along the way feasible, a uniform
    shift changing no distance inside the tree.
    """
    incident: dict[str, list[tuple[str, str]]] = {}
    for pair in edges:
        incident.setdefault(pair[0], []).append(pair)
        incident.setdefault(pair[1], []).append(pair)

    inside = {members[0]}
    tree: set[tuple[str, str]] = set()
    frontier = set(incident.get(members[0], ()))
    while len(inside) < len(members):
        frontier = {pair for pair in frontier if (pair[0] in inside) != (pair[1] in inside)}
        crossing = sorted(frontier)
        tight = [pair for pair in crossing if _slack(pair, ranks) == 0]
        if not tight:
            distance, pair = min((_slack(pair, ranks), pair) for pair in crossing)
            # Sliding the tree up closes the slack of an edge it holds the
            # premise end of; sliding it down closes the slack of one it holds
            # the dependent end of.
            step = -distance if pair[1] in inside else distance
            for node_id in inside:
                ranks[node_id] += step
            continue
        joined = tight[0]
        tree.add(joined)
        arrival = joined[1] if joined[0] in inside else joined[0]
        inside.add(arrival)
        frontier.update(incident.get(arrival, ()))
    return tree


def _rooted(tree: set[tuple[str, str]], root: str) -> tuple[list[str], dict[str, str]]:
    """The spanning tree read from ``root``: every node before its children, and each node's parent."""
    adjacency: dict[str, list[str]] = {}
    for premise, dependent in tree:
        adjacency.setdefault(premise, []).append(dependent)
        adjacency.setdefault(dependent, []).append(premise)

    order, queue, seen = [root], deque([root]), {root}
    parent: dict[str, str] = {}
    while queue:
        current = queue.popleft()
        for neighbour in sorted(adjacency.get(current, ())):
            if neighbour not in seen:
                seen.add(neighbour)
                parent[neighbour] = current
                order.append(neighbour)
                queue.append(neighbour)
    return order, parent


def _cut_values(
    tree: set[tuple[str, str]],
    order: list[str],
    parent: dict[str, str],
    net: dict[str, int],
) -> dict[tuple[str, str], int]:
    """Each tree edge's cut value: the premise relations crossing it one way, less those crossing the other.

    Cutting a tree edge splits the component in two, and an edge's cut value is
    the number of premise relations running from its premise side to its
    dependent side less the number running back. Summing ``net`` over one side
    is the whole of that count — every relation with both ends on one side
    contributes ``+1`` and ``−1`` and cancels — so one post-order pass prices
    every tree edge at once, rather than a traversal apiece.
    """
    sums = {node_id: net[node_id] for node_id in order}
    for node_id in reversed(order[1:]):
        sums[parent[node_id]] += sums[node_id]
    below = {pair: pair[0] if parent.get(pair[0]) == pair[1] else pair[1] for pair in tree}
    return {pair: sums[child] if child == pair[0] else -sums[child] for pair, child in below.items()}


def _premise_side(
    leaving: tuple[str, str],
    order: list[str],
    parent: dict[str, str],
    members: list[str],
) -> set[str]:
    """The half of the component standing on ``leaving``'s premise end, once that edge is cut."""
    child = leaving[0] if parent.get(leaving[0]) == leaving[1] else leaving[1]
    subtree = {child}
    for node_id in order:  # a parent precedes its children, so one pass closes the set
        if parent.get(node_id) in subtree:
            subtree.add(node_id)
    return subtree if child == leaving[0] else {node_id for node_id in members if node_id not in subtree}


def _intervening_layers(first: int, second: int) -> range:
    """The layers strictly between two endpoint layers — one dummy apiece."""
    lower, upper = sorted((first, second))
    return range(lower + 1, upper)


# ---------------------------------------------------------------------------
# In-layer ordering — the crossing-reduction sweep
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Band:
    """The segments between one layer and the next one up, as the sweep reads them.

    ``pairs`` is what the crossing count runs over; ``below`` and ``above`` are
    the same segments indexed from each end, which is what a pass needs and
    what would otherwise be rebuilt on every round.
    """

    pairs: tuple[tuple[_Key, _Key], ...]
    below: dict[_Key, list[_Key]]
    above: dict[_Key, list[_Key]]


def _occupants(nodes: tuple[Node, ...], edges: Iterable[Edge], layers: dict[str, int]) -> dict[int, list[_Key]]:
    """Every layer's occupants in the stable start order: key ascending.

    **A real node's key is its id alone and a dummy's is its edge's
    ``(source, target)`` pair**, and the two are ordered against each other as
    the tuples they are — so the order is total because ids are unique among
    nodes and pairs among edges, and it is a function of the graph rather than
    of the order its records arrived in. Nothing else enters either key: not
    domain, not degree, not component membership.

    This is a *starting* order, not the drawn one — and it is what the sweep's
    determinism rests on, a sweep started from a dict built in record order
    being reproducible only by accident.

    **Dummies are placed over the whole corpus graph**, never over the edge set
    a particular sheet draws, or a node would take one column on the full sheet
    and another on a domain sheet.

    ``nodes`` is the hierarchy alone: an orphan occupies no layer, and leaving
    it in one would put the whole unattached half of a mechanically-built corpus
    into layer 0 — which is the width this block exists to take out of it.
    """
    by_layer: dict[int, list[_Key]] = defaultdict(list)
    for node in nodes:
        by_layer[layers[node.id]].append((node.id,))
    for edge in edges:
        for layer in _intervening_layers(layers[edge.source], layers[edge.target]):
            by_layer[layer].append((edge.source, edge.target))
    return {layer: sorted(keys) for layer, keys in by_layer.items()}


def _chain(edge: Edge, layers: dict[str, int]) -> tuple[int, list[_Key]] | None:
    """The occupant key this edge holds in each layer, lower end upward.

    Its own two ends, and between them the dummy key :func:`_occupants` placed
    in each layer it crosses — the same keys, read as a chain.

    ``None`` for an edge within one layer, which crosses no band and so has no
    say in any layer's order — an intra-cycle edge, drawn and marked but not
    swept on.
    """
    lower_layer, upper_layer = sorted((layers[edge.source], layers[edge.target]))
    if lower_layer == upper_layer:
        return None
    lower_end = (edge.source,) if layers[edge.source] == lower_layer else (edge.target,)
    upper_end = (edge.target,) if layers[edge.target] == upper_layer else (edge.source,)
    dummies = [(edge.source, edge.target)] * (upper_layer - lower_layer - 1)
    return lower_layer, [lower_end, *dummies, upper_end]


def _bands(edges: Iterable[Edge], layers: dict[str, int]) -> dict[int, _Band]:
    """The segments running between each layer and the next one up, keyed by the lower layer."""
    pairs: dict[int, list[tuple[_Key, _Key]]] = defaultdict(list)
    for edge in edges:  # ascending by (source, target) — no incidental order enters
        chained = _chain(edge, layers)
        if chained is None:
            continue
        lower_layer, keys = chained
        for offset, pair in enumerate(zip(keys, keys[1:])):
            pairs[lower_layer + offset].append(pair)

    bands: dict[int, _Band] = {}
    for layer, group in sorted(pairs.items()):
        below: dict[_Key, list[_Key]] = defaultdict(list)
        above: dict[_Key, list[_Key]] = defaultdict(list)
        for lower, upper in group:
            below[upper].append(lower)
            above[lower].append(upper)
        bands[layer] = _Band(pairs=tuple(group), below=dict(below), above=dict(above))
    return bands


def _positions(keys: list[_Key]) -> dict[_Key, int]:
    """Each occupant's index in its layer."""
    return {key: index for index, key in enumerate(keys)}


def _band_crossings(band: _Band, below: dict[_Key, int], above: dict[_Key, int]) -> int:
    """How many pairs of this band's segments cross.

    Two segments cross when one starts left of the other and ends right of it.
    Segments meeting at an occupant never cross — they share that position, so
    neither comparison is strict — which is the same exclusion the hop scan
    makes on node identity.
    """
    placed = [(below[lower], above[upper]) for lower, upper in band.pairs]
    return sum(
        1
        for (first_low, first_high), (second_low, second_high) in combinations(placed, 2)
        if (first_low - second_low) * (first_high - second_high) < 0
    )


def _crossings(order: dict[int, list[_Key]], bands: dict[int, _Band]) -> int:
    """The whole sheet's crossing count under one ordering — the sweep's score."""
    positions = {layer: _positions(keys) for layer, keys in order.items()}
    return sum(_band_crossings(band, positions[layer], positions[layer + 1]) for layer, band in bands.items())


def _reordered(keys: list[_Key], neighbours: dict[_Key, list[_Key]], positions: dict[_Key, int]) -> list[_Key]:
    """One layer re-sorted on each occupant's barycentre across one band.

    An occupant with no neighbour in that band scores its own current index, so
    it neither drifts nor blocks: it holds its place among the occupants that
    did move. Ties sort by current index, which keeps the pass stable and is
    what carries the start order through a layer nothing constrains.
    """
    scored = []
    for index, key in enumerate(keys):
        adjacent = neighbours.get(key, ())
        rank = Fraction(sum(positions[other] for other in adjacent), len(adjacent)) if adjacent else Fraction(index)
        scored.append((rank, index))
    return [keys[index] for _, index in sorted(scored)]


def _pass(order: dict[int, list[_Key]], bands: dict[int, _Band], *, upward: bool) -> None:
    """One sweep in one direction, in place: each layer reordered against its already-placed neighbour."""
    for layer in sorted(bands, reverse=not upward):
        band = bands[layer]
        moving, fixed = (layer + 1, layer) if upward else (layer, layer + 1)
        neighbours = band.below if upward else band.above
        order[moving] = _reordered(order[moving], neighbours, _positions(order[fixed]))


def _pair_crossings(neighbours: dict[_Key, list[_Key]], positions: dict[_Key, int], *, left: _Key, right: _Key) -> int:
    """How many of two occupants' segments cross across one band, with ``left`` standing left of ``right``.

    One term per pair of their segments: the left occupant's crosses the right
    occupant's exactly when the right one's far end stands left of the left
    one's. Two segments reaching the same occupant tie and cross under neither
    reading, which is the exclusion :func:`_band_crossings` makes from the other
    side. Only these two occupants' own segments are counted, because no other
    segment's crossing status can change when the two of them exchange.
    """
    ends = [positions[other] for other in neighbours.get(left, ())]
    return sum(1 for other in neighbours.get(right, ()) for end in ends if positions[other] < end)


def _side_gain(neighbours: dict[_Key, list[_Key]], positions: dict[_Key, int], *, left: _Key, right: _Key) -> int:
    """What exchanging two adjacent occupants would cost across one band alone — negative is a gain."""
    return _pair_crossings(neighbours, positions, left=right, right=left) - _pair_crossings(
        neighbours, positions, left=left, right=right
    )


def _exchange_gain(
    bands: dict[int, _Band],
    positions: dict[int, dict[_Key, int]],
    *,
    layer: int,
    left: _Key,
    right: _Key,
) -> int:
    """What exchanging two adjacent occupants of ``layer`` would cost — negative is a gain.

    Both of the layer's bands are priced, the one beneath it and the one above:
    an exchange that unpicks a crossing below can plant one above, and the pair
    only moves when the two together come out ahead.
    """
    gain = 0
    beneath, above = bands.get(layer - 1), bands.get(layer)
    if beneath is not None:  # this layer is that band's upper side
        gain += _side_gain(beneath.below, positions[layer - 1], left=left, right=right)
    if above is not None:  # and this band's lower one
        gain += _side_gain(above.above, positions[layer + 1], left=left, right=right)
    return gain


def _transpose_pass(order: dict[int, list[_Key]], bands: dict[int, _Band]) -> bool:
    """One walk over every layer's adjacent pairs, exchanging in place; ``True`` when any pair moved.

    Layers ascend and each layer's pairs run left to right, so the walk is a
    stated order rather than a container's. **A pair that gains nothing holds
    its ground** — the exchange is made only on a strict reduction, the same tie
    rule the barycentre pass keeps — which is also what makes the local minimum
    a fixed point rather than a cycle of equal-scoring exchanges.

    Each layer is priced against its neighbours' positions as they stand, so a
    layer the walk has already been through is read in the order it left it.
    """
    moved = False
    positions = {layer: _positions(keys) for layer, keys in order.items()}
    for layer in sorted(order):
        keys, row = order[layer], positions[layer]
        for index in range(len(keys) - 1):
            left, right = keys[index], keys[index + 1]
            if _exchange_gain(bands, positions, layer=layer, left=left, right=right) < 0:
                keys[index], keys[index + 1] = right, left
                row[left], row[right] = row[right], row[left]
                moved = True
    return moved


def _transpose(order: dict[int, list[_Key]], bands: dict[int, _Band]) -> None:
    """The transpose refinement, in place: exchange adjacent occupants to a local minimum.

    Gansner, Koutsofios, North & Vo (1993) §3.2 — the barycentre pass's
    companion. It runs to its own convergence, the first pass that exchanges
    nothing, and :data:`TRANSPOSE_PASSES` caps it. No pass can raise the
    crossing count, every exchange strictly lowering it, so a run the cap cuts
    short returns an order no worse than the one it was given.
    """
    for _ in range(TRANSPOSE_PASSES):
        if not _transpose_pass(order, bands):
            return


def _snapshot(order: dict[int, list[_Key]]) -> dict[int, list[_Key]]:
    """A copy the passes cannot reach into — each layer's list is rewritten in place."""
    return {layer: list(keys) for layer, keys in order.items()}


def _sweep(occupants: dict[int, list[_Key]], bands: dict[int, _Band]) -> dict[int, list[_Key]]:
    """The iterated barycentre sweep with the transpose refinement, returning the best order it reached.

    Best-scoring rather than last-reached: a round can trade one band's
    crossings for another's, and the start order is in the running, so the sweep
    cannot return a worse picture than the one it was handed.

    **The refinement runs on each round's candidate and never on the sweep's own
    state**: the next round's barycentre pass starts from the order the two
    passes left, not from the exchanged one. Transpose descends to a local
    minimum, and an order sitting in one is the wrong place to restart a
    barycentre pass from — measured, and the module docstring carries the
    numbers.
    """
    order = _snapshot(occupants)
    best, best_score = _snapshot(order), _crossings(order, bands)
    for _ in range(SWEEP_ROUNDS):
        _pass(order, bands, upward=True)
        _pass(order, bands, upward=False)
        candidate = _snapshot(order)
        _transpose(candidate, bands)
        score = _crossings(candidate, bands)
        if score >= best_score:
            break
        best, best_score = candidate, score
    return best


# ---------------------------------------------------------------------------
# Coordinates — the priority method
# ---------------------------------------------------------------------------


def _priority(key: _Key, neighbours: dict[_Key, list[_Key]]) -> tuple[int, int]:
    """One occupant's claim on its own position: a dummy first, then degree.

    Read as a tuple so the two rank against each other without a sentinel
    number: **a dummy outranks every real node**, which is what straightens a
    long edge's chain and makes the real nodes give way to it, and among real
    nodes the one with more neighbours to answer to moves first.
    """
    return (1 if len(key) > 1 else 0, len(neighbours.get(key, ())))


def _mean(values: Iterable[int]) -> int:
    """The barycentre of some positions, rounded to the nearer integer, exactly.

    Integer arithmetic throughout — this quantity *is* a coordinate, so it
    rounds here rather than at emission, and nothing about where a box lands may
    depend on a binary fraction.
    """
    positions = list(values)
    total, count = sum(positions), len(positions)
    return (2 * total + count) // (2 * count)


def _blocker(keys: list[_Key], priorities: dict[_Key, tuple[int, int]], *, index: int, step: int) -> int:
    """The first occupant in ``step``'s direction that will not give way.

    Everything between here and it has strictly lower priority and can be
    pushed. The returned position may be one past the layer's own end, which is
    the unbounded case and needs no second spelling.
    """
    position = index + step
    while 0 <= position < len(keys) and priorities[keys[position]] < priorities[keys[index]]:
        position += step
    return position


def _shift(
    keys: list[_Key],
    xs: dict[_Key, int],
    priorities: dict[_Key, tuple[int, int]],
    *,
    index: int,
    target: int,
) -> None:
    """Move one occupant toward ``target``, pushing only occupants it outranks.

    The two bounds are the whole of what keeps this phase from undoing the
    ordering phase: the mover stops dead against the first occupant of equal or
    higher priority, and every occupant it does push keeps at least
    :data:`style.COLUMN_PITCH` of separation — so no occupant ever passes
    another and the boxes keep the gutter between them.
    """
    key = keys[index]
    step = 1 if target > xs[key] else -1
    blocker = _blocker(keys, priorities, index=index, step=step)
    if 0 <= blocker < len(keys):
        # Everything between here and the blocker must still fit at that
        # separation, so the blocker's own position is what caps this move.
        limit = xs[keys[blocker]] - (blocker - index) * style.COLUMN_PITCH
        if step * (target - limit) > 0:
            target = limit
    if step * (target - xs[key]) <= 0:
        return

    xs[key] = target
    for position in range(index + step, blocker, step):
        # The pushed follow only as far as the separation demands, never the
        # whole distance the mover travelled.
        pushed = xs[keys[position - step]] + step * style.COLUMN_PITCH
        if step * (pushed - xs[keys[position]]) > 0:
            xs[keys[position]] = pushed


def _align(
    keys: list[_Key],
    xs: dict[_Key, int],
    neighbours: dict[_Key, list[_Key]],
    fixed: dict[_Key, int],
) -> None:
    """One layer pulled toward the layer across one band, in priority order.

    ``reverse=True`` leaves equal priorities in the layer's own drawn order,
    which is the stated tie rule and the reason nothing here reads an index
    twice.
    """
    priorities = {key: _priority(key, neighbours) for key in keys}
    for index, key in sorted(enumerate(keys), key=lambda item: priorities[item[1]], reverse=True):
        adjacent = neighbours.get(key, ())
        if not adjacent:
            # No barycentre to be pulled toward. It holds its place and is
            # pushed like any other occupant.
            continue
        _shift(keys, xs, priorities, index=index, target=_mean(fixed[other] for other in adjacent))


def _coordinate_pass(
    order: dict[int, list[_Key]],
    xs: dict[int, dict[_Key, int]],
    bands: dict[int, _Band],
    *,
    upward: bool,
) -> None:
    """One coordinate sweep in one direction, in place — the ordering pass's shape, over positions."""
    for layer in sorted(bands, reverse=not upward):
        band = bands[layer]
        moving, fixed = (layer + 1, layer) if upward else (layer, layer + 1)
        _align(order[moving], xs[moving], band.below if upward else band.above, xs[fixed])


def _edge_length(xs: dict[int, dict[_Key, int]], bands: dict[int, _Band]) -> int:
    """The total horizontal edge length — what this phase minimises, and its score.

    One term per drawn segment, because every segment is layer-adjacent: a chain
    that runs straight up through its placeholders contributes nothing, and one
    that zigzags through them pays for every bend.
    """
    return sum(
        abs(xs[layer + 1][upper] - xs[layer][lower]) for layer, band in bands.items() for lower, upper in band.pairs
    )


def _score(xs: dict[int, dict[_Key, int]], bands: dict[int, _Band]) -> tuple[int, int]:
    """What one round is judged on: total edge length first, then the sheet's width.

    The width is a tie-break and never an objective. Total length is *flat*
    wherever a vertex sits anywhere between two neighbours, so on its own it
    cannot tell a round that centred such a vertex from one that also prised the
    sheet open around it; between two pictures whose edges are equally long, the
    narrower one is the one a reader can take in.
    """
    positions = [position for row in xs.values() for position in row.values()]
    return (_edge_length(xs, bands), max(positions, default=0) - min(positions, default=0))


def _anchored(xs: dict[int, dict[_Key, int]]) -> dict[int, dict[_Key, int]]:
    """Shift the whole sheet so its leftmost occupant stands where column zero stood.

    One global shift and never a per-layer one: a per-layer shift is the
    alignment this phase just bought, thrown away. Applied after every round and
    not only at the end, because a configuration nothing pins can translate
    sideways for ever without changing — and a round that moved nothing but the
    frame must read as the fixed point it is.
    """
    offset = style.BOX_WIDTH // 2 - min((position for row in xs.values() for position in row.values()), default=0)
    return {layer: {key: position + offset for key, position in row.items()} for layer, row in xs.items()}


def _priority_xs(order: dict[int, list[_Key]], bands: dict[int, _Band]) -> dict[int, dict[_Key, int]]:
    """Each occupant's centre **x**, by the priority method — the module docstring's phase 5.

    Starts from the column grid the ordering alone used to draw and returns the
    best-scoring round it reached: that grid is in the running, so the phase
    cannot hand back a sheet whose edges are longer than the one it was given.
    """
    grid = {layer: {key: index * style.COLUMN_PITCH for index, key in enumerate(keys)} for layer, keys in order.items()}
    xs = _anchored(grid)
    best, best_score = xs, _score(xs, bands)
    for _ in range(COORDINATE_ROUNDS):
        previous = xs
        xs = {layer: dict(row) for layer, row in xs.items()}
        _coordinate_pass(order, xs, bands, upward=True)
        _coordinate_pass(order, xs, bands, upward=False)
        xs = _anchored(xs)
        score = _score(xs, bands)
        if score <= best_score:
            # Ties go to the swept round rather than to the grid: where both
            # halves of the score are flat it is the barycentre that decides,
            # and putting a vertex on it is what this phase is.
            best, best_score = xs, score
        if xs == previous:
            break
    return best


# ---------------------------------------------------------------------------
# Concentric placement — one ring per layer
# ---------------------------------------------------------------------------


def _clears(first: tuple[int, int], second: tuple[int, int]) -> bool:
    """Do two occupant centres leave their boxes the blank space the grid always gave them?

    The whole separation rule, and a property of the two placed rectangles
    rather than of any ring: one column pitch apart horizontally **or** one
    layer pitch apart vertically — the box plus its gutter one way, the box plus
    the layer gap the other, which are the two magnitudes the layered
    arrangement holds its occupants apart by.
    """
    return abs(first[0] - second[0]) >= style.COLUMN_PITCH or abs(first[1] - second[1]) >= style.LAYER_PITCH


def _rectangle(ring: int) -> list[tuple[int, int]]:
    """Ring ``ring``'s candidate centres on an axis-aligned rectangle, counter-clockwise from the 3 o'clock ray.

    Candidates sit one column pitch apart along the horizontal sides and one
    layer pitch apart along the vertical ones, so every pair of them clears by
    construction, and so does every pair across two consecutive rings — a ring's
    vertical side stands a whole :data:`style.RING_STEP` of column pitch outside
    the ring within it and its horizontal side a whole one of layer pitch. So
    this form grows only where a layer has more occupants than the ring has
    seats, and never because two of them crowd.
    """
    seats = ring * style.RING_STEP
    if seats <= 0:
        return [(0, 0)]
    pitch_x, pitch_y = style.COLUMN_PITCH, style.LAYER_PITCH
    right, top = seats * pitch_x, seats * pitch_y
    return (
        [(right, y * pitch_y) for y in range(0, seats + 1)]
        + [(x * pitch_x, top) for x in range(seats - 1, -seats - 1, -1)]
        + [(-right, y * pitch_y) for y in range(seats - 1, -seats - 1, -1)]
        + [(x * pitch_x, -top) for x in range(-seats + 1, seats)]
        + [(right, y * pitch_y) for y in range(-seats, 0)]
    )


def _ellipse(ring: int) -> list[tuple[int, int]]:
    """Ring ``ring``'s candidate centres on a true ellipse, walked in integers.

    ``y = isqrt(b²(a² − x²)) // a``, the precedent being
    :func:`kb_tools.kb_graph.svg._fixed_length`'s use of :func:`math.isqrt` for
    the same reason: libm is not byte-reproducible across hosts and this must
    be.

    Both axes are walked and the results unioned, because stepping x alone
    leaves the curve coarse where it is steep and stepping y alone leaves it
    coarse where it is flat. Within the first quadrant the walk runs from
    ``(a, 0)`` to ``(0, b)``, along which x descends and y ascends
    monotonically, so ordering by ``(y, -x)`` *is* the counter-clockwise order
    and no angle is taken. The other three quadrants are that one mirrored, with
    the shared axis points dropped.

    Two similar ellipses come closer than the pitch in a diagonal sector, which
    :func:`_place_ring` catches rather than a guessed pitch multiplier: a ring
    that cannot seat its occupants grows, which is this form paying for itself
    deterministically.
    """
    seats = ring * style.RING_STEP
    if seats <= 0:
        return [(0, 0)]
    a, b = seats * style.COLUMN_PITCH, seats * style.LAYER_PITCH
    quarter = {(a, 0), (0, b)}
    for x in range(0, a + 1):
        quarter.add((x, isqrt(b * b * (a * a - x * x)) // a))
    for y in range(0, b + 1):
        quarter.add((isqrt(a * a * (b * b - y * y)) // b, y))
    first = sorted(quarter, key=lambda point: (point[1], -point[0]))
    second = [(-x, y) for x, y in reversed(first)][1:]
    third = [(-x, -y) for x, y in first][1:]
    fourth = [(x, -y) for x, y in reversed(first)][1:-1]
    return first + second + third + fourth


#: The ring forms, by the name the placement is selected under. A form states
#: the candidate positions it offers and nothing else — the separation rule is
#: :func:`_clears`' and the seating is :func:`_place_ring`'s — so a form is one
#: entry here and one function, and switching between them is one edit to
#: :data:`DEFAULT_PLACEMENT`.
RING_FORMS: dict[str, Callable[[int], list[tuple[int, int]]]] = {
    "rectangle": _rectangle,
    "ellipse": _ellipse,
}


def _place_ring(
    candidates: list[tuple[int, int]],
    count: int,
    inner: list[tuple[int, int]],
) -> tuple[list[tuple[int, int]], bool]:
    """Seat ``count`` occupants on one ring, and say whether every one of them cleared.

    Occupant ``i`` is aimed at its own fraction of the ring — an even spread,
    and that is measured rather than preferred: packing them consecutively from
    the cut puts *more* strokes through boxes, not fewer, because it bunches the
    occupants where two rings are already closest together. From its aim each is
    advanced along the candidates to the first position whose box clears
    everything already placed on this ring and everything on the ring within it.

    An occupant the advance cannot clear takes its aimed position, and the ring
    reports itself crowded — which is what :func:`_rings` grows on. It reports a
    seating either way, so no ring refuses to draw.
    """
    total = len(candidates)
    chosen: list[tuple[int, int]] = []
    cleared = count <= total
    pointer = 0
    for index in range(count):
        aim = (index * total) // count
        position = max(pointer, aim)
        while position < total and not all(_clears(candidates[position], other) for other in (*chosen, *inner)):
            position += 1
        if position >= total:
            position, cleared = aim, False
        chosen.append(candidates[position])
        pointer = position + 1
    if len(chosen) > 1 and not _clears(chosen[0], chosen[-1]):
        cleared = False
    return chosen, cleared


def _rings(counts: list[int], form: str) -> list[list[tuple[int, int]]]:
    """Every ring's seated centres, innermost first, in the ring frame.

    A ring starts one :data:`style.RING_STEP` outside the one within it — which
    is why the radii add rather than max — and grows until the placer seats its
    occupants clear of each other. Growth is the only way a form pays for
    needing more room, and it is what the ellipse's diagonal sector spends;
    :data:`RING_GROWTH` caps it, and a ring that reaches the cap draws on the
    largest ring it reached, a crowded picture being a true one where a refused
    picture is not.
    """
    shape = RING_FORMS[form]
    seated: list[list[tuple[int, int]]] = []
    ring = 0
    for index, count in enumerate(counts):
        ring = ring + 1 if index else 0
        inner = seated[-1] if seated else []
        limit = ring + RING_GROWTH
        placed, cleared = _place_ring(shape(ring), count, inner)
        while not cleared and ring < limit:
            ring += 1
            placed, cleared = _place_ring(shape(ring), count, inner)
        seated.append(placed)
    return seated


# ---------------------------------------------------------------------------
# Arrangements — how the swept order is stood up on the page
# ---------------------------------------------------------------------------


def _linear_centres(order: dict[int, list[_Key]], bands: dict[int, _Band]) -> dict[int, dict[_Key, Point]]:
    """Every occupant's centre on the layered grid: the priority method's x, at its layer's own height.

    Layer 0 sits on the baseline and the sheet grows upward into negative ``y``,
    so a new deepest layer changes the ``viewBox`` and moves nothing already
    placed.
    """
    middle = style.BOX_HEIGHT // 2
    return {
        layer: {key: Point(x, middle - layer * style.LAYER_PITCH) for key, x in row.items()}
        for layer, row in _priority_xs(order, bands).items()
    }


def _ring_centres(
    order: dict[int, list[_Key]],
    bands: dict[int, _Band],
    *,
    form: str,
) -> dict[int, dict[_Key, Point]]:
    """Every occupant's centre on concentric rings — one ring per layer, in the sheet's y-down frame.

    **The ring index is the layer, counting inward from bedrock**, so the
    deepest layer — the conclusions — is the centre. That orientation is
    measured rather than assumed: bedrock-centred leaves a 448×362 empty
    half-side on the arXiv corpus and costs area on every corpus.

    ``bands`` goes unread. Nothing pulls an occupant along a ring: the even
    spread :func:`_place_ring` aims at is what stands in this arrangement for
    the priority method's barycentre, and a ring has no room to give an occupant
    that another occupant is not standing in.
    """
    inward = sorted(order, reverse=True)
    seated = _rings([len(order[layer]) for layer in inward], form)
    return {
        # The ring frame is y-up; the sheet's is y-down.
        layer: {key: Point(x, -y) for key, (x, y) in zip(order[layer], seated[ring], strict=True)}
        for ring, layer in enumerate(inward)
    }


@dataclass(frozen=True, slots=True)
class _Placement:
    """One arrangement: where its occupants stand, and where a stroke meets a box.

    A layered sheet has an up, so its strokes leave a box's top edge and arrive
    at its bottom one. A ring has none, so its strokes run centre to centre —
    and the emitter draws the boxes opaque and last, so a stroke still leaves
    from under its own box edge.
    """

    centres: Callable[[dict[int, list[_Key]], dict[int, _Band]], dict[int, dict[_Key, Point]]]
    centre_anchored: bool


#: Every arrangement :data:`PLACEMENT_ENV` will select, by name.
PLACEMENTS: dict[str, _Placement] = {
    "linear": _Placement(centres=_linear_centres, centre_anchored=False),
    **{
        f"ring-{form}": _Placement(centres=partial(_ring_centres, form=form), centre_anchored=True)
        for form in RING_FORMS
    },
}

#: The arrangement the sheet ships with. Changing it is this one edit, which is
#: what keeps a form switch from being a patch.
DEFAULT_PLACEMENT = "ring-rectangle"

#: The environment variable that overrides it. **A development control**: no
#: consumer sets it, no runner target passes it, and nothing in the toolchain
#: reads the sheet differently for it — it exists so that two arrangements can
#: be drawn from one build and looked at side by side.
PLACEMENT_ENV = "KB_GRAPH_PLACEMENT"


def _selected_placement() -> _Placement:
    """The arrangement this render draws with: the environment's, or the shipped default.

    An unrecognised name raises rather than falling back. The value arrived from
    outside this toolchain — a developer's shell — and the vocabulary it is
    checked against is closed and stated here; a sheet silently drawn by an
    arrangement nobody asked for is indistinguishable from one that was, and the
    freshness gate would report it as a graph change.
    """
    name = os.environ.get(PLACEMENT_ENV) or DEFAULT_PLACEMENT
    if name not in PLACEMENTS:
        raise ValueError(f"{PLACEMENT_ENV}={name!r} is not one of {sorted(PLACEMENTS)}")
    return PLACEMENTS[name]


# ---------------------------------------------------------------------------
# Edges and the sheet extent
# ---------------------------------------------------------------------------


def _place_edge(
    edge: Edge,
    source: PlacedNode,
    target: PlacedNode,
    *,
    centres: dict[int, dict[_Key, Point]],
    cycle_members: frozenset[str],
    centre_anchored: bool,
) -> PlacedEdge:
    """The edge's chain: the lower anchor, a bend at each occupant crossed, the upper anchor.

    A bend is the dummy's own centre, which is the point a real box placed there
    would stand on — so the bend sits between the anchors it joins and a chain
    reads as one line rather than as a stack of hinges.
    """
    lower, upper = sorted((source, target), key=lambda p: (p.layer, p.column))
    pair = (edge.source, edge.target)
    bends = tuple(centres[layer][pair] for layer in _intervening_layers(lower.layer, upper.layer))
    return PlacedEdge(
        edge=edge,
        points=(
            lower.centre if centre_anchored else lower.top_centre,
            *bends,
            upper.centre if centre_anchored else upper.bottom_centre,
        ),
        # Every intra-cycle edge is a back-edge defect.
        back_edge=edge.source in cycle_members and edge.target in cycle_members,
    )


def _view_box(nodes: tuple[PlacedNode, ...], edges: tuple[PlacedEdge, ...]) -> ViewBox:
    """The union of every drawn box and every drawn point, plus :data:`style.MARGIN`.

    The stroke points are in it because a chain bends at a dummy's column, which
    may sit right of the widest box on the sheet.
    """
    if not nodes:
        return ViewBox(-style.MARGIN, -style.MARGIN, 2 * style.MARGIN, 2 * style.MARGIN)
    points = [point for edge in edges for point in edge.points]
    xs = [node.x for node in nodes] + [node.x + node.width for node in nodes] + [point.x for point in points]
    ys = [node.y for node in nodes] + [node.y + node.height for node in nodes] + [point.y for point in points]
    min_x, min_y = min(xs) - style.MARGIN, min(ys) - style.MARGIN
    max_x, max_y = max(xs) + style.MARGIN, max(ys) + style.MARGIN
    return ViewBox(min_x, min_y, max_x - min_x, max_y - min_y)


# ---------------------------------------------------------------------------
# Hop detection and hop side
# ---------------------------------------------------------------------------


def _hops(edges: tuple[PlacedEdge, ...]) -> tuple[Hop, ...]:
    """Every crossing in the drawn edge set, one glyph each.

    The test is per **segment**: an edge is a chain, so two edges may cross more
    than once and each crossing is its own glyph on its own run. O(E^2) in the
    edges and quadratic in their segments, and deliberately the naive
    implementation: at corpus scale it is free, and determinism by stable keys
    is worth more than asymptotics. An accelerated replacement would have to
    produce the identical glyph set, proven by an equivalence test — an
    acceleration that changes the picture has changed the contract.

    Multiple hops on one edge are independent: each crossing yields its own
    glyph at its own point, and two glyphs closer than twice the hop radius abut
    or overlap rather than being merged. Merging is order-dependent, and a
    congested region reading as congested is information.
    """
    # Each chain's runs, built once: the scan visits every pair of edges, and
    # rebuilding a tuple of segments inside that loop is the whole cost of it.
    segments = {edge.key: edge.segments for edge in edges}
    out: list[Hop] = []
    for position, first in enumerate(edges):
        for second in edges[position + 1 :]:
            if _share_a_node(first.edge, second.edge):
                # Every fan-in and fan-out shares an endpoint; a naive test
                # flags all of them and the sheet fills with glyphs at every
                # junction. The test is on node identity, never on coincident
                # coordinates.
                continue
            out.extend(_segment_hops(*_hop_side(first, second), segments=segments))
    return tuple(sorted(out, key=lambda hop: (hop.hopping, hop.hopping_segment, hop.crossed, hop.crossed_segment)))


def _segment_hops(
    hopping: PlacedEdge,
    crossed: PlacedEdge,
    *,
    segments: dict[tuple[str, str], tuple[Segment, ...]],
) -> Iterable[Hop]:
    """Every crossing between two chains, one per crossing pair of their runs."""
    for hopping_index, hopping_segment in enumerate(segments[hopping.key]):
        for crossed_index, crossed_segment in enumerate(segments[crossed.key]):
            crossing = _crossing(hopping_segment, crossed_segment)
            if crossing is None:
                continue
            yield Hop(
                hopping=hopping.key,
                hopping_segment=hopping_index,
                crossed=crossed.key,
                crossed_segment=crossed_index,
                x=crossing[0],
                y=crossing[1],
            )


def _share_a_node(first: Edge, second: Edge) -> bool:
    """True when the two strokes meet at a node, by id and never by coordinate."""
    return bool({first.source, first.target} & {second.source, second.target})


def _hop_side(first: PlacedEdge, second: PlacedEdge) -> tuple[PlacedEdge, PlacedEdge]:
    """Which of the two hops: the one whose ``(source, target)`` sorts greater.

    A stable key, stated as one so that it cannot quietly become the order the
    scan happened to visit the pair in. The pair is the whole key — ``relation``
    is redundant after the dedupe and is undefined for a two-relation conflict
    edge.
    """
    if first.key > second.key:
        return (first, second)
    return (second, first)


def _crossing(first: Segment, second: Segment) -> tuple[Fraction, Fraction] | None:
    """The point strictly interior to both segments, or ``None``.

    Exact integer arithmetic with no epsilon. With integer endpoints the
    cross-product denominator is exact, so ``den == 0`` is the whole
    parallel/colinear test — a colinear overlap draws as one line and carries no
    glyph — and each parameter is compared as a numerator against that
    denominator, sign-aware, rather than divided out. Only the returned point
    divides, exactly, into a :class:`~fractions.Fraction`.
    """
    origin, run = first.start, _delta(first)
    other_origin, other_run = second.start, _delta(second)
    den = run[0] * other_run[1] - run[1] * other_run[0]
    if den == 0:
        return None

    offset = (other_origin.x - origin.x, other_origin.y - origin.y)
    first_num = offset[0] * other_run[1] - offset[1] * other_run[0]
    second_num = offset[0] * run[1] - offset[1] * run[0]
    if den < 0:
        den, first_num, second_num = -den, -first_num, -second_num
    if not (0 < first_num < den and 0 < second_num < den):
        return None

    along = Fraction(first_num, den)
    return (origin.x + along * run[0], origin.y + along * run[1])


def _delta(segment: Segment) -> tuple[int, int]:
    """The segment's vector, lower end to upper end."""
    return (segment.end.x - segment.start.x, segment.end.y - segment.start.y)


__all__ = [
    "Hop",
    "PlacedEdge",
    "PlacedNode",
    "Point",
    "Segment",
    "Sheet",
    "ViewBox",
    "place",
]
