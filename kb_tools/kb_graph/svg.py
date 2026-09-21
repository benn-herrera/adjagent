"""Markup for the claim-graph sheet: placed geometry in, one document out.

This is the **only** module in the package that composes markup, and it makes no
layout decision. It compares no two node positions — every position it emits is
one :mod:`kb_tools.kb_graph.layout` already decided or a stated function of those
alone (a run's control points, and the hop arc's two endpoints on the tangent of
the stroke they bridge), and every offset it adds to one is a label-local
constant from :mod:`kb_tools.kb_graph.style` — the text baselines inside a box,
and the hop radius.

**The document is built as an element tree and serialized by it.** No f-string
composes a tag or an attribute here, the pinned XML declaration included — that
declaration is emitted from a processing-instruction node rather than written as
a literal, so the rule has no exception to remember. The reason
is not tidiness: node titles in this corpus carry ``&``, ``$\\beta$``, quotes and
em-dashes, and a hand-rolled escaper is an exhaustiveness obligation with no
mechanical check, where the standard library's escaping is total by
construction. *The trap*: the tree is plain and non-namespaced with the SVG
namespace set as an ordinary attribute on the root — ``ET.QName`` and
``register_namespace`` prefix every tag with ``ns0:`` instead.

**One number formatter, and rounding happens once.** Every coordinate
:mod:`layout` hands over is an ``int`` and emits with no decimal point, and so
is every control point derived from one here (:func:`_control_points`). A hop is
the non-integral geometry — its arc, and the cut ends of the stroke that arc
lifts (:func:`_cubic_slice`) — and those path values carry exactly three
decimals applied at emission, after all the arithmetic — never at an
intermediate step.

**A stroke is a curve and the curve is a stated function of layout's own
points.** :mod:`layout` decides where a chain's vertices sit; this module
decides only how they are joined, and joins them with centripetal Catmull-Rom
(α = ½) written as one cubic Bezier per run. The parametrisation, what it was
measured against and what the alternatives cost are recorded on
:func:`_control_points`, which owns it.

The caller writes the returned text with ``encoding="utf-8", newline="\\n"``;
nothing here opens a file.

Stdlib only.
"""

import xml.etree.ElementTree as ET
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from fractions import Fraction
from math import isqrt, lcm
from pathlib import PurePosixPath

from kb_tools import kb_schema
from kb_tools.kb_graph import layout, style

#: Set as a literal attribute on a plain, non-namespaced root. Node
#: links are emitted as ``href`` alone; there is no ``xlink`` namespace.
SVG_NAMESPACE = "http://www.w3.org/2000/svg"

#: The XML declaration, composed by the serializer rather than written
#: out: this package composes no markup by hand, and the declaration is markup.
#: A processing-instruction node serializes to exactly the pinned bytes.
_DECLARATION = ET.tostring(ET.ProcessingInstruction("xml", 'version="1.0" encoding="utf-8"'), encoding="unicode")

#: The serializer call, pinned: two spaces of indentation, then a text
#: serialization, and exactly one trailing newline on the document.
_INDENT = "  "
_NEWLINE = "\n"

#: The kind whose tooltip carries a second value beside its id.
_EXPERIMENT = "experiment"

#: The two edge classes carrying a strength of their own. A ``depends``
#: edge carries neither and is drawn in the colour of the premise it leans on.
_SUPPORTS = "supports"
_STRENGTHENS = "strengthens"

#: An experiment's tooltip carries its ``status`` beside its id; a deduped
#: stroke's tooltip carries its merged contexts.
_ID_LINE_SEPARATOR = " · "
_CONTEXT_SEPARATOR = " · "
_TITLE_ARROW = " → "
_TITLE_DASH = " — "
_RELATIONS_LABEL = "relations: "
_RELATION_SEPARATOR = ", "

#: The one admitted fragment separator. An empty ``canonical_anchor`` yields
#: a path with no fragment rather than a trailing one.
_FRAGMENT = "#"

#: An edge's path data: ``x,y`` per vertex, tokens separated by a space.
_COORDINATE_SEPARATOR = ","
_POINT_SEPARATOR = " "

#: The three path commands a stroke is written with. ``L`` appears on a
#: two-point chain alone, where it is the curve rather than an exception to it
#: (:func:`_edge_path`).
_MOVE = "M"
_LINE = "L"
_CURVE = "C"

#: Bits of fixed-point precision the chord roots (:func:`_chord_root`) are taken
#: at. **Not a presentation magnitude** — :mod:`style` holds those, and nothing
#: about how the sheet looks is decided here; this is the precision of an exact
#: integer computation, and 20 bits puts its error some six orders of magnitude
#: below the one-pixel rounding every control point takes at the end of it.
_ROOT_SHIFT = 20

#: The hop arc, as SVG path data. Its bulge is ``n = (d.y, -d.x)`` for the
#: direction ``d`` of the chord its two feet span, **read left to right across
#: the sheet**, which is a fixed rotation of ``d`` — so the arc's handedness
#: never varies and the sweep flag is a constant, not a case analysis.
_ARC_SWEEP = "1"


# ---------------------------------------------------------------------------
# The single number formatter
# ---------------------------------------------------------------------------


def format_number(value: int | float | Fraction) -> str:
    """Format one emitted number: integers bare, everything else to three decimals.

    Every coordinate in the frame is an ``int`` because every magnitude in
    :mod:`style` is, so it emits with no decimal point and a golden diff cannot
    widen under floating-point noise. A hop's arc, and the cut ends of the
    stroke it lifts, are the non-integral geometry, and this is where their
    rounding happens — once, at emission.

    A value that rounds to zero from below emits as ``0.000``: the signed zero
    is the same point and reads as a defect.
    """
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    text = format(float(value), ".3f")
    return text[1:] if text.startswith("-") and float(text) == 0 else text


# ---------------------------------------------------------------------------
# Hyperlinks
# ---------------------------------------------------------------------------


def relative_link_base(*, kb_root: PurePosixPath | str, sheet_dir: PurePosixPath | str) -> PurePosixPath:
    """Where the KB root sits, relative to the directory the sheet is written into.

    ``PurePosixPath`` throughout and never ``os.path``, whose separators are
    platform-dependent and would make the emitted document host-dependent. The
    result is what :func:`node_href` joins a node's kb-root-relative
    ``canonical_path`` onto, so a link resolves from the sheet's own directory.

    Raises:
        ValueError: when one path is absolute and the other is not — there is no
            relative answer between them, and returning a plausible-looking one
            would emit links that resolve nowhere.
    """
    root, here = PurePosixPath(kb_root), PurePosixPath(sheet_dir)
    if root.is_absolute() != here.is_absolute():
        raise ValueError(f"kb_root {str(root)!r} and sheet_dir {str(here)!r} must both be absolute or both relative")

    shared = 0
    for mine, theirs in zip(root.parts, here.parts):
        if mine != theirs:
            break
        shared += 1
    return PurePosixPath(*([".."] * (len(here.parts) - shared)), *root.parts[shared:])


def node_href(placed: layout.PlacedNode, *, link_base: PurePosixPath | str) -> str | None:
    """The link target for one node, or ``None`` when it has no definition to name.

    The index's ``canonical_path`` (kb-root-relative POSIX) under ``link_base``,
    plus the ``canonical_anchor`` as a fragment. An empty anchor — which the
    index emits in one branch — yields a path with **no** fragment rather than a
    trailing one. A stub stands for a ghost id and has no record, so it carries
    no link at all.
    """
    record = placed.node.record
    if record is None:
        return None
    target = str(PurePosixPath(link_base) / record.canonical_path)
    anchor = record.canonical_anchor
    return target + _FRAGMENT + anchor if anchor else target


# ---------------------------------------------------------------------------
# Colour — one entry per node kind
# ---------------------------------------------------------------------------


def _band_fill(placed: layout.PlacedNode) -> str:
    """The palette colour of a node's own stored band, or the pending neutral.

    A claim carries ``build_band`` and a support has one derived on the load
    side; an external work and a stub carry none, and are unscored rather than
    weak, so they take the off-ladder neutral. The absent-band reading is a
    ``getattr`` default because the field's presence is the record type's, and
    the record types are :mod:`kb_tools.kb_cmd.index`'s to define.
    """
    return style.BAND_PALETTE.get(getattr(placed.node.record, "build_band", ""), style.PENDING_FILL)


#: A fixed fill per node kind, or ``None`` where the kind's fill is the node's
#: own band. Total over :data:`kb_schema.NODE_KINDS` by construction: a kind
#: added to the vocabulary and not to this table fails here rather than
#: inheriting whichever branch came last. A framework node takes a fill that is
#: deliberately no rung of the ramp; an experiment and an external work carry no
#: band, and :func:`_band_fill` answers the neutral for them.
_FILL_BY_KIND: dict[str, str | None] = kb_schema.kind_table(
    {
        "claim": None,
        "support": None,
        "work": None,
        "experiment": style.EXPERIMENT_FILL,
        "invariant": style.FRAMEWORK_FILL,
        "axiom": style.FRAMEWORK_FILL,
    },
    what="kb_graph.svg node fills",
)


def _node_fill(placed: layout.PlacedNode, *, foreign: bool) -> str:
    """Fill for one box, across every node kind plus the stub and the foreign one."""
    if foreign:
        return style.FOREIGN_FILL
    node_type = placed.node.node_type
    if node_type is None:
        return style.STUB_FILL
    if node_type not in _FILL_BY_KIND:
        raise ValueError(f"node {placed.id!r} carries node_type {node_type!r}, which is no kind the sheet draws")
    fixed = _FILL_BY_KIND[node_type]
    return _band_fill(placed) if fixed is None else fixed


def _premise_colour(target: layout.PlacedNode) -> str:
    """The strength a ``depends`` edge inherits from the premise it leans on.

    A framework premise takes the ladder's top rung: framework dependencies
    contribute 1.0 to the solidity min and never pend, so the rung is read from
    that rule rather than invented. Every other premise shows its own band — so
    a weak premise's whole fan-out reads weak at every dependent, which is the
    instrument's second role exactly.
    """
    if target.node.node_type in kb_schema.FRAMEWORK_KINDS:
        return style.FRAMEWORK_EDGE_COLOUR
    return _band_fill(target)


@dataclass(frozen=True, slots=True)
class _Stroke:
    """How one edge is drawn: its colour, its dash, and its weight."""

    colour: str
    dash: str | None
    width: int


def _edge_presentation(placed: layout.PlacedEdge, nodes: Mapping[str, layout.PlacedNode]) -> _Stroke:
    """One stroke's presentation, with the precedence between defects stated once.

    A ghost endpoint wins outright — such an edge takes the defect stub style and
    no band, because there is no node whose strength it could be showing. A
    conflict mark then wins over the band, since the fact the colour would report
    is the one in dispute. Dashes are the defect channel and colour is the
    strength channel, so a back edge keeps its band and takes the dash.
    """
    edge = placed.edge
    if nodes[edge.source].node.is_stub or nodes[edge.target].node.is_stub:
        return _Stroke(style.STUB_STROKE, style.DASH_STUB, style.EDGE_STROKE_WIDTH)

    dash = style.DASH_BACK_EDGE if placed.back_edge else None
    if edge.conflict:
        return _Stroke(style.CONFLICT_STROKE, dash, style.EDGE_STROKE_WIDTH)
    if edge.relation == _SUPPORTS:
        return _Stroke(style.band_colour(edge.fraction), dash, style.EDGE_STROKE_WIDTH)
    if edge.relation == _STRENGTHENS:
        return _Stroke(style.band_colour(edge.strength), dash, style.EDGE_STROKE_WIDTH)
    return _Stroke(_premise_colour(nodes[edge.target]), dash, style.EDGE_STROKE_WIDTH)


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------


def _fitted(text: str) -> str:
    """One label line cut to the width of the box it is drawn in.

    :data:`style.LABEL_CHARS` with a single ellipsis character. This is the id
    line's own cut; :func:`_wrapped` holds the title's lines to the same cap, so
    **every** line is under it and the box is a width labels fit rather than one
    they usually fit. A ``work-`` id is a citation key, bounded by nothing, and
    the corpus carries them up to 37 characters, so a line left uncut would run
    across its neighbour.
    """
    return text if len(text) <= style.LABEL_CHARS else text[: style.LABEL_CHARS - 1] + style.TRUNCATION_ELLIPSIS


def _wrapped(title: str) -> tuple[str, ...]:
    """One title broken across at most :data:`style.TITLE_LINES` label lines.

    **The rule is total and deterministic, and it is stated here because the
    same title must always produce the same lines.** Whitespace runs collapse to
    one space and the ends are stripped, so no line is decided by how the title
    was spaced. Then, line by line:

    * a remainder that fits under :data:`style.LABEL_CHARS` is the last line;
    * otherwise the break is the **last space at or before the cap**, and the
      space itself is consumed rather than drawn;
    * a token with no such space — one word longer than the cap — is **cut at
      the cap** and its tail continues on the next line, because the alternative
      is a line wider than the box it sits in;
    * on the final line a remainder that does not fit is cut hard to
      ``LABEL_CHARS - 1`` characters and given :data:`style.TRUNCATION_ELLIPSIS`.
      The final line does not break at a space: there is no next line for the
      word to move to, so a whitespace break would spend the width on nothing.

    An empty title — a stub's, which shows none — wraps to no lines at all
    rather than to one blank one.
    """
    lines: list[str] = []
    rest = " ".join(title.split())
    while rest:
        if len(rest) <= style.LABEL_CHARS:
            lines.append(rest)
            break
        if len(lines) == style.TITLE_LINES - 1:
            lines.append(rest[: style.LABEL_CHARS - 1] + style.TRUNCATION_ELLIPSIS)
            break
        cut = rest.rfind(" ", 0, style.LABEL_CHARS + 1)
        lines.append(rest[: cut if cut > 0 else style.LABEL_CHARS])
        rest = rest[cut if cut > 0 else style.LABEL_CHARS :].lstrip()
    return tuple(lines)


def _label_lines(placed: layout.PlacedNode) -> tuple[str, ...]:
    """The box's lines: the node's id, then its title wrapped beneath it.

    All cut to the box — the id by :func:`_fitted`, the title by
    :func:`_wrapped` — and none is where the whole of either is read:
    :func:`_node_title` carries both in full, at no layout cost, as a tooltip in
    every browser. The id line is what a reader carries off the sheet to a
    register, a query or a grep, so it is drawn ahead of the title rather than
    sized around it.

    A title shorter than its allowance yields fewer lines than
    :data:`style.TITLE_LINES`. That costs no geometry: :data:`style.BOX_HEIGHT`
    is a function of the cap and not of the lines a given node produced.
    """
    return (_fitted(placed.node.id), *_wrapped(placed.node.title))


def _node_title(placed: layout.PlacedNode) -> str:
    """The box's tooltip: the whole identity and the whole title, uncut.

    An experiment's ``status`` rides here rather than on the id line. It is
    still shown as its own word and never asserted as a score — which is the
    property the fill already carries — but the id line is the one thing on the
    box a reader acts on, and a status sharing it made the box wide enough to
    hold both on every sheet in the corpus, experiments or none.
    """
    node = placed.node
    identity = node.id
    if node.node_type == _EXPERIMENT:
        identity = identity + _ID_LINE_SEPARATOR + getattr(node.record, "status", "")
    return identity + _TITLE_DASH + node.title


def _edge_title(placed: layout.PlacedEdge) -> str:
    """The stroke's tooltip: the pair, its merged contexts, and any relation conflict.

    Contexts arrive already ascending and collapsed; the head stands alone when
    the group carried none, rather than trailing the separator that would
    introduce them. A stroke carrying two relations for one fact names every
    relation it found.
    """
    edge = placed.edge
    parts = [edge.source + _TITLE_ARROW + edge.target]
    if edge.contexts:
        parts.append(_CONTEXT_SEPARATOR.join(edge.contexts))
    if edge.conflict:
        parts.append(_RELATIONS_LABEL + _RELATION_SEPARATOR.join(edge.relations))
    return _TITLE_DASH.join(parts)


# ---------------------------------------------------------------------------
# Element emitters
# ---------------------------------------------------------------------------


def _root(view_box: layout.ViewBox) -> ET.Element:
    """The sheet root: the namespace as a plain attribute, and the pinned font.

    **The root carries the ``viewBox`` and no ``width`` or ``height``**, so the
    sheet scales to whatever it is placed in. Those two are the intrinsic size a
    viewer lays the document out at, and a real corpus's sheet is some fifteen
    thousand pixels wide: pinned, it opens at that size and can only be zoomed
    *in* from there. Absent, the SVG root takes its initial ``100%`` in both
    axes, so a standalone file fills the window and the default
    ``preserveAspectRatio`` fits the ``viewBox`` inside it at any window size.

    ``width="100%" height="100%"`` reaches the same standalone view and is not
    the same document: a percentage is no intrinsic size, so an ``img`` element
    or a CSS background with no sizing of its own falls back to the replaced
    element's 300×150 default, where the ``viewBox`` alone gives it the sheet's
    own aspect ratio to size by.

    The font sits here rather than on every text element: it is inherited, the
    document names the family and size it was sized against, and a per-node byte
    identity stays as small as it can be.
    """
    extent = (view_box.min_x, view_box.min_y, view_box.width, view_box.height)
    return ET.Element(
        "svg",
        {
            "xmlns": SVG_NAMESPACE,
            "viewBox": " ".join(format_number(value) for value in extent),
            "font-family": style.FONT_FAMILY,
            "font-size": format_number(style.FONT_SIZE),
        },
    )


def _background(view_box: layout.ViewBox) -> ET.Element:
    return ET.Element(
        "rect",
        {
            "class": "sheet",
            "x": format_number(view_box.min_x),
            "y": format_number(view_box.min_y),
            "width": format_number(view_box.width),
            "height": format_number(view_box.height),
            "fill": style.SHEET_BACKGROUND,
        },
    )


def _rounded(value: Fraction) -> int:
    """One exact rational to the nearer integer, half up, by integer arithmetic.

    A control point is a coordinate, so — as in :func:`layout._mean`, for the
    same reason — it rounds where it is computed rather than at emission, and
    nothing about where a curve bends depends on a binary fraction.
    """
    return (2 * value.numerator + value.denominator) // (2 * value.denominator)


def _reflected(anchor: layout.Point, neighbour: layout.Point) -> layout.Point:
    """``neighbour`` reflected through ``anchor`` — the phantom beyond a chain's end.

    The first and last runs have no outer neighbour to read a knot spacing from.
    Duplicating the endpoint instead is the other common choice and is not
    available: it gives that run a zero-length chord, which is a zero
    denominator in :func:`_control` rather than a degenerate curve. Reflecting
    makes the phantom chord equal the run's own, which collapses the formula to
    a control point one third along the run — so a chain's end leaves straight
    along its own first run, and a two-point chain is a straight line exactly.
    """
    return layout.Point(x=2 * anchor.x - neighbour.x, y=2 * anchor.y - neighbour.y)


def _fixed_length(x: int, y: int) -> int:
    """``|(x, y)|`` in ``2 ** -_ROOT_SHIFT`` fixed point, by integer square root alone.

    :func:`math.isqrt` is total over the integers and answers the same on every
    host and every build, where ``math.sqrt`` and ``math.hypot`` over the same
    value are libm calls and the sheet must be byte-identical for a given graph
    wherever it is rendered. Two callers need a length and neither may take one
    from libm: :func:`_chord_root` roots this again for the knot spacing, and
    :func:`draw_hop_over` divides by it to set the arc's endpoints one radius
    apart along a tangent.
    """
    return isqrt((x * x + y * y) << (2 * _ROOT_SHIFT))


def _chord_root(first: layout.Point, second: layout.Point) -> Fraction:
    """``|second − first| ** ½`` — the centripetal knot spacing — exactly and identically everywhere.

    Two nested integer square roots over the exact integer squared length, in
    ``2 ** -_ROOT_SHIFT`` fixed point: :func:`_fixed_length` takes the inner one
    and this takes the outer. :func:`math.isqrt` is total over the integers and
    its answer is the same on every host and every build, where ``math.sqrt`` of
    the same value is a libm call and the golden's byte identity is a gate
    (SPEC.md, The Claim-Graph Sheet).
    """
    return Fraction(isqrt(_fixed_length(second.x - first.x, second.y - first.y) << _ROOT_SHIFT), 1 << _ROOT_SHIFT)


def _control(
    near: layout.Point,
    mid: layout.Point,
    far: layout.Point,
    *,
    near_root: Fraction,
    mid_root: Fraction,
    low: layout.Point,
    high: layout.Point,
) -> layout.Point:
    """One run's control point, Barry–Goldman with α = ½, clamped to the chain's own extent.

    ``mid`` is the run end this control point belongs to, ``far`` the run's other
    end, and ``near`` the neighbour beyond ``mid`` on its own side; ``near_root``
    and ``mid_root`` are :func:`_chord_root` of those two chords. The same
    expression serves both control points of a run — the second is the first read
    from the other end — so the parametrisation is written once.

    **The clamp is what makes a curve leaving the sheet impossible rather than
    unobserved.** A cubic lies inside the convex hull of its own four points, so
    confining both control points to the bounding box of the chain's vertices
    confines the whole curve to it; :func:`layout._view_box` already unions every
    one of those vertices, so the drawn curve is inside the ``viewBox`` by
    construction. It is also the overshoot bound: no run can swing wider than the
    chain's own points, which is the defect an unclamped uniform parametrisation
    showed at 128px on ``ModernCorpPristine``.
    """
    square, other = near_root**2, mid_root**2
    weight = 2 * square + 3 * near_root * mid_root + other
    denominator = 3 * near_root * (near_root + mid_root)

    def axis(near_value: int, mid_value: int, far_value: int, *, floor: int, ceiling: int) -> int:
        offset = (square * far_value - other * near_value + weight * mid_value) / denominator
        return min(max(_rounded(offset), floor), ceiling)

    return layout.Point(
        x=axis(near.x, mid.x, far.x, floor=low.x, ceiling=high.x),
        y=axis(near.y, mid.y, far.y, floor=low.y, ceiling=high.y),
    )


def _control_points(points: tuple[layout.Point, ...]) -> tuple[tuple[layout.Point, layout.Point], ...]:
    """The two cubic control points of each run of one chain, in chain order.

    **The parametrisation is centripetal Catmull-Rom, α = ½, at full tension**,
    converted to cubic Beziers by Barry and Goldman's formula (Yuksel, Schaefer &
    Keyser 2011, *Parameterization and applications of Catmull-Rom curves*, §2).
    It is a stated function of ``points`` and adds no magnitude of its own: the
    knot spacing is the chord length raised to α and nothing else.

    **Measured over the drawn strokes of ``mini-kb``, ``ModernCorp``,
    ``ModernCorpPristine`` and ``2609.09855v1``**, against the polyline the sheet
    drew before it. Two numbers decide it. *Overshoot* is how far a curve swings
    outside the bounding box of its own chain's points — the corridor a polyline
    never leaves — and it is what escapes the ``viewBox``. *Box hits* count
    ``(stroke, box)`` pairs where the drawn stroke passes through a node box that
    is neither of its endpoints, which is the thing a curve can do that a
    rectilinear route could not:

    * **α = 0, uniform**: overshoot **128px** on Pristine and **126px** on the
      arXiv sheet, and it leaves that sheet — 24px outside the ``viewBox``, which
      is the whole of :data:`style.MARGIN`. This is the parametrisation the
      defect was first seen on.
    * **α = 1, chordal**: worse still, 172px and 163px, and the hop glyphs drift
      furthest of any variant.
    * **α = ½, centripetal**: 22px and 16px unclamped, **0px clamped** — and the
      clamp costs nothing, the box-hit counts being identical with it and without.
    * **Tension below 1** was measured and is not taken: it buys overshoot the
      clamp already gives for free, and it buys it by pulling the curve back
      toward the polyline, which is where the box hits were. Clamped and
      otherwise alike, τ = 0.8 and τ = 0.6 raise the arXiv sheet's hits by 3 and
      by 6. There is therefore no tension constant, here or in :mod:`style`.

    **Box hits fall rather than rise, which is the opposite of what a curve was
    expected to cost.** Pristine 26 → 21 and the arXiv sheet 45 → 23: a polyline
    bends *at* a dummy's own column, and a dummy's column is where a box in that
    layer stands, so the rectilinear route hugged exactly the boxes it did not
    connect to. Rounding the bend is what takes it off them.

    **The hop glyph is placed on this curve and not on the chain.**
    :func:`layout._hops` finds crossings between the straight chords joining a
    chain's vertices, which is which strokes cross and where — its question, and
    unchanged. Where the glyph is drawn is this module's: the crossing point lies
    on its own chord, so the parameter it sits at comes back exactly from a
    projection onto that chord (:func:`_chord_parameter`) and the run above is
    evaluated there for the glyph's centre and differentiated there for the
    tangent its two endpoints sit on (:func:`draw_hop_over`). Both are exact
    rational polynomial evaluations, so no curve-curve intersection is solved for
    and no tolerance is picked — which is what keeps root-finding out of the
    presentation module while the glyph still rides the stroke it marks.
    """
    low = layout.Point(x=min(point.x for point in points), y=min(point.y for point in points))
    high = layout.Point(x=max(point.x for point in points), y=max(point.y for point in points))
    chain = (_reflected(points[0], points[1]), *points, _reflected(points[-1], points[-2]))
    roots = tuple(_chord_root(first, second) for first, second in zip(chain, chain[1:]))

    controls = []
    for index in range(len(points) - 1):
        before, first, second, after = chain[index : index + 4]
        back, across, forward = roots[index], roots[index + 1], roots[index + 2]
        controls.append(
            (
                _control(before, first, second, near_root=back, mid_root=across, low=low, high=high),
                _control(after, second, first, near_root=forward, mid_root=across, low=low, high=high),
            )
        )
    return tuple(controls)


#: One axis of one drawn run, as its cubic's four Bernstein coefficients: the
#: run's two ends with its two control points between them.
_Cubic = tuple[Fraction, Fraction, Fraction, Fraction]

#: A closed parameter interval of one run, ``0 <= first <= last <= 1``. Read as
#: a *gap* it is what a hop lifts the stroke over (:func:`_hop_gap`); read as a
#: *span* it is a piece of stroke that survives one (:func:`_drawn_spans`).
_Interval = tuple[Fraction, Fraction]


def _chord(start: int, end: int) -> _Cubic:
    """One axis of a straight run: the control points on the chord at its own thirds.

    A cubic whose controls sit at the chord's thirds *is* that chord — the same
    points at the same parameter — so the ``L`` of :func:`_edge_path` needs no
    geometry of its own to be read at a parameter.
    """
    third = Fraction(end - start, 3)
    return (Fraction(start), start + third, start + 2 * third, Fraction(end))


def _drawn_run(points: tuple[layout.Point, ...], index: int) -> tuple[_Cubic, _Cubic]:
    """The run :func:`_edge_path` draws at ``index`` of one chain, per axis.

    **A two-point chain has no :func:`_control_points` entry**: it is emitted as
    a line, and :func:`_chord` is that line written as a cubic. So a glyph on a
    straight stroke is placed by the one evaluation a glyph on a curved one is,
    rather than by a second geometry that could disagree with it.
    """
    start, end = points[index], points[index + 1]
    if len(points) == 2:
        return (_chord(start.x, end.x), _chord(start.y, end.y))
    first, second = _control_points(points)[index]
    return (
        (Fraction(start.x), Fraction(first.x), Fraction(second.x), Fraction(end.x)),
        (Fraction(start.y), Fraction(first.y), Fraction(second.y), Fraction(end.y)),
    )


def _cubic_point(axis: _Cubic, at: Fraction) -> Fraction:
    """One axis of a drawn run at parameter ``at`` — the Bernstein form, exactly."""
    start, first, second, end = axis
    rest = 1 - at
    return rest**3 * start + 3 * rest**2 * at * first + 3 * rest * at**2 * second + at**3 * end


def _cubic_slope(axis: _Cubic, at: Fraction) -> Fraction:
    """One axis of a drawn run's derivative at ``at`` — the tangent, exactly."""
    start, first, second, end = axis
    rest = 1 - at
    return 3 * (rest**2 * (first - start) + 2 * rest * at * (second - first) + at**2 * (end - second))


def _de_casteljau(axis: _Cubic, at: Fraction) -> tuple[_Cubic, _Cubic]:
    """One axis of a drawn run cut at ``at``: the same curve, as the cubic before and the cubic after.

    De Casteljau's construction is linear interpolation and nothing else, so on
    exact rationals the two pieces *are* the original curve rather than an
    approximation of it — which is what keeps a cut stroke inside this module's
    discipline: nothing is root-found and there is no tolerance to pick.
    """

    def between(first: Fraction, second: Fraction) -> Fraction:
        return first + (second - first) * at

    start, one, two, end = axis
    near, middle, far = between(start, one), between(one, two), between(two, end)
    inner, outer = between(near, middle), between(middle, far)
    cut = between(inner, outer)
    return (start, near, inner, cut), (cut, outer, far, end)


def _cubic_slice(axis: _Cubic, span: _Interval) -> _Cubic:
    """One axis of a drawn run over ``span`` alone, reparametrised onto 0-to-1.

    Two cuts: the piece after the span's start, then the piece of *that* before
    the span's end — whose parameter is rescaled onto the tail the first cut
    left. The start is strictly below 1 (:func:`_drawn_spans` emits no empty
    span), so the rescaling has no zero denominator.
    """
    first, last = span
    _, tail = _de_casteljau(axis, first)
    head, _ = _de_casteljau(tail, (last - first) / (1 - first))
    return head


def _drawn_spans(run_count: int, gaps: Mapping[int, tuple[_Interval, ...]]) -> tuple[tuple[int, _Interval], ...]:
    """Each run's drawn pieces, in chain order: 0-to-1 less whatever its hops lift it over.

    One pass per run, because :func:`_edge_gaps` hands the gaps over ascending
    and non-overlapping. A gap touching a run's own end leaves no span there
    rather than an empty one, so every span returned has positive extent.
    """
    spans: list[tuple[int, _Interval]] = []
    for index in range(run_count):
        at = Fraction(0)
        for first, last in gaps.get(index, ()):
            if first > at:
                spans.append((index, (at, first)))
            at = last
        if at < 1:
            spans.append((index, (at, Fraction(1))))
    return tuple(spans)


def _coordinate(x: int | Fraction, y: int | Fraction) -> str:
    return format_number(x) + _COORDINATE_SEPARATOR + format_number(y)


def _vertex(point: layout.Point) -> str:
    return _coordinate(point.x, point.y)


def _span_tokens(
    points: tuple[layout.Point, ...],
    *,
    index: int,
    span: _Interval,
    controls: tuple[tuple[layout.Point, layout.Point], ...],
) -> tuple[str, list[str]]:
    """One drawn span of one run: where the pen starts, and the command that draws it.

    A whole run is emitted from the control points :func:`_control_points`
    already rounded to integers — or, on a two-point chain that has none, as the
    ``L`` of :func:`_edge_path` — so a stroke no hop cuts is the same bytes it
    was before hops cut any. A part of a run is the cubic restricted to the span
    (:func:`_cubic_slice`), and where such a span still ends on one of the run's
    own vertices that vertex is emitted as the integer :mod:`layout` decided
    rather than as the identical rational the restriction returns.
    """
    first, last = span
    if (first, last) == (0, 1):
        if not controls:
            return _vertex(points[0]), [_LINE, _vertex(points[1])]
        one, two = controls[index]
        return _vertex(points[index]), [_CURVE, _vertex(one), _vertex(two), _vertex(points[index + 1])]

    horizontal, vertical = _drawn_run(points, index)
    across, down = _cubic_slice(horizontal, span), _cubic_slice(vertical, span)
    start = _vertex(points[index]) if first == 0 else _coordinate(across[0], down[0])
    end = _vertex(points[index + 1]) if last == 1 else _coordinate(across[3], down[3])
    return start, [_CURVE, _coordinate(across[1], down[1]), _coordinate(across[2], down[2]), end]


def _edge_path(points: tuple[layout.Point, ...], *, gaps: Mapping[int, tuple[_Interval, ...]]) -> str:
    """One chain as path data: a move, then one cubic per run, less what its own hops lift over.

    **A two-point chain is written as a line and that is not a second rule.**
    With the phantom of :func:`_reflected` at both ends the parametrisation
    returns a cubic whose control points lie on the chord at its thirds — the
    straight line, exactly — so ``L`` is the same geometry in a quarter of the
    bytes. An adjacent-layer stroke stays straight because the curve it would be
    given is straight, not because it was excused.

    **A hop is a hole in this path and not a mark on top of it.** The glyph
    belongs to the hopping stroke, so the stroke is emitted as subpaths with the
    span under each of its own arcs left out — a fresh ``M`` wherever the pen
    lifted, and none where the previous span ran to a vertex the next one starts
    from. Without that hole the arc closes against the stroke beneath it and the
    pair reads as a lens rather than as a line stepping over another.
    """
    controls = () if len(points) == 2 else _control_points(points)
    tokens: list[str] = []
    drawn_to, drawn_at = -1, Fraction(0)
    for index, span in _drawn_spans(len(points) - 1, gaps):
        start, drawn = _span_tokens(points, index=index, span=span, controls=controls)
        if not (index == drawn_to + 1 and drawn_at == 1 and span[0] == 0):
            tokens += [_MOVE, start]
        tokens += drawn
        drawn_to, drawn_at = index, span[1]
    return _POINT_SEPARATOR.join(tokens)


def _edge_element(
    placed: layout.PlacedEdge, *, stroke: "_Stroke", gaps: Mapping[int, tuple[_Interval, ...]]
) -> ET.Element:
    """One stroke: the whole chain as a single path, however many runs and however many hops.

    ``fill`` is explicitly none because a path's default fill closes it — a
    chain would otherwise paint the region under itself, and a gapped one would
    paint a chord across each of its own hops.
    """
    attrib = {
        "class": "edge",
        "d": _edge_path(placed.points, gaps=gaps),
        "fill": "none",
        "stroke": stroke.colour,
        "stroke-width": format_number(stroke.width),
    }
    if stroke.dash is not None:
        attrib["stroke-dasharray"] = stroke.dash
    element = ET.Element("path", attrib)
    ET.SubElement(element, "title").text = _edge_title(placed)
    return element


def _chord_parameter(x: Fraction, y: Fraction, *, start: layout.Point, end: layout.Point) -> Fraction:
    """Where along a chord a point sits: ``((p − p₀) · (p₃ − p₀)) / |p₃ − p₀|²``.

    Two questions are asked through this one projection, and neither solves
    anything. The crossing :func:`layout._hops` reports lies on that chord by
    construction, so its projection **recovers** the parameter the crossing was
    built from rather than approximating one. The opening's two ends
    (:func:`_hop_feet`) are stepped along the drawn stroke's *tangent* and so lie
    slightly off the chord, and their projection turns that into a fraction of a
    pixel of opening width — never into a glyph off its stroke, because the arc
    is drawn between the stroke's own points at the parameters this returns
    (:func:`_hop_ends`).

    The drawn run covers the same two vertices over the same 0-to-1 parameter,
    which is what makes either answer usable on it: the glyph sits at the
    fraction of the run the crossing sat at, and the gap under it at the fraction
    its feet reached, on the stroke that is actually drawn.
    """
    run = (end.x - start.x, end.y - start.y)
    offset = (x - start.x, y - start.y)
    return (offset[0] * run[0] + offset[1] * run[1]) / (run[0] ** 2 + run[1] ** 2)


def _integral(vector: tuple[Fraction, Fraction]) -> tuple[int, int]:
    """One exact rational direction as an integer vector pointing the same way.

    Scaling both axes by their common denominator names the same line, and it is
    what lets the length of that line be an integer square root
    (:func:`_fixed_length`) rather than a libm call.
    """
    scale = lcm(vector[0].denominator, vector[1].denominator)
    return (int(vector[0] * scale), int(vector[1] * scale))


def _rightward(direction: tuple[int, int]) -> tuple[int, int]:
    """The direction the glyph's chord runs, read left to right across the sheet.

    The arc's two endpoints ordered by screen x, tie-broken by y where the
    chord is vertical — which is the whole of the rule. ``d.x >= 0``
    afterwards, always.
    """
    x, y = direction
    return direction if (x, y) > (0, 0) else (-x, -y)


def _hop_feet(hop: layout.Hop, *, points: tuple[layout.Point, ...]) -> tuple[_Interval, _Interval]:
    """How wide the opening is: :data:`style.HOP_RADIUS` either side of the crossing, along the tangent.

    Ordered by screen x, which is what :func:`_rightward` decides. **This states
    the opening's width and nothing else.** :func:`_hop_gap` projects these two
    points back onto the run to get the parameters the stroke is cut at, and the
    arc is then drawn between the stroke's *own* points at those same two
    parameters (:func:`_hop_ends`) — so a foot sitting off the curve here costs
    the opening a fraction of a pixel of width and cannot move the glyph off the
    stroke.
    """
    horizontal, vertical = _drawn_run(points, hop.hopping_segment)
    at = _chord_parameter(hop.x, hop.y, start=points[hop.hopping_segment], end=points[hop.hopping_segment + 1])
    centre_x, centre_y = _cubic_point(horizontal, at), _cubic_point(vertical, at)
    direction = _rightward(_integral((_cubic_slope(horizontal, at), _cubic_slope(vertical, at))))
    length = Fraction(_fixed_length(*direction), 1 << _ROOT_SHIFT)
    along_x = style.HOP_RADIUS * direction[0] / length
    along_y = style.HOP_RADIUS * direction[1] / length
    return ((centre_x - along_x, centre_y - along_y), (centre_x + along_x, centre_y + along_y))


def _hop_gap(hop: layout.Hop, *, points: tuple[layout.Point, ...]) -> _Interval:
    """The run parameters between which the hopping stroke is not drawn.

    The arc's own two feet, projected back onto the run's chord by the same
    :func:`_chord_parameter` the crossing came through — the one rational
    operation, asked a second question. Each parameter is held inside the run's
    own 0-to-1 because a run is all there is to cut: a foot beyond a vertex
    reaches no stroke, and clamping it says so without inventing a magnitude.
    """
    start, end = points[hop.hopping_segment], points[hop.hopping_segment + 1]
    reached = [_chord_parameter(x, y, start=start, end=end) for x, y in _hop_feet(hop, points=points)]
    first, last = sorted(min(max(at, Fraction(0)), Fraction(1)) for at in reached)
    return (first, last)


def _hop_ends(hop: layout.Hop, *, points: tuple[layout.Point, ...]) -> tuple[_Interval, _Interval]:
    """The arc's two endpoints: the drawn stroke's own points where the stroke is cut.

    **This is what makes the arc and the stroke meet by construction.** The two
    parameters are :func:`_hop_gap`'s, which is what :func:`_edge_path` opens the
    stroke over, and the points are :func:`_cubic_point` at them — so an arc foot
    is a point of the drawn curve rather than a point near it, and the
    discontinuity a tangent step leaves on a curved stroke is unrepresentable.
    The two ends are also the bytes :func:`_span_tokens` emits for the cut, both
    sides evaluating one polynomial at one rational.

    Ordered by screen x and tie-broken by y — :func:`_rightward`'s rule, applied
    to the chord these two points span instead of to the tangent, so the glyph's
    handedness stays the screen fact :func:`draw_hop_over` describes.
    """
    horizontal, vertical = _drawn_run(points, hop.hopping_segment)
    first, last = _hop_gap(hop, points=points)
    ends = (
        (_cubic_point(horizontal, first), _cubic_point(vertical, first)),
        (_cubic_point(horizontal, last), _cubic_point(vertical, last)),
    )
    return ends if (ends[1][0] - ends[0][0], ends[1][1] - ends[0][1]) > (0, 0) else (ends[1], ends[0])


def _half_chord(across: Fraction, down: Fraction) -> Fraction:
    """Half the distance between the arc's two feet, exactly, by integer square root alone.

    The radius a semicircular arc must carry to span a chord is half that chord,
    so this is the arc's radius and it is a magnitude of the picture rather than
    one of :mod:`style`: the opening's width is :data:`style.HOP_RADIUS`'
    to state, and what a circle through the resulting two points measures is
    arithmetic. Scaling both axes by their common denominator is
    :func:`_integral`'s move, and :func:`_fixed_length` then takes the one root
    the same way every other length in this module does — no libm, so the same
    bytes on every host.
    """
    scale = lcm(across.denominator, down.denominator)
    return Fraction(_fixed_length(int(across * scale), int(down * scale)), 2 * scale << _ROOT_SHIFT)


def _merged(gaps: list[_Interval]) -> tuple[_Interval, ...]:
    """Ascending gaps with every pair that touches or overlaps joined into one."""
    joined: list[_Interval] = []
    for first, last in gaps:
        if joined and first <= joined[-1][1]:
            joined[-1] = (joined[-1][0], max(joined[-1][1], last))
        else:
            joined.append((first, last))
    return tuple(joined)


def _leaves_stroke_either_side(hole: _Interval) -> bool:
    """Whether punching ``hole`` leaves drawn stroke on both sides of it, within its own run.

    **This is the whole condition on a gap.** A hole reaching either end of its
    run leaves the stroke stopping in mid-air there: the arc's own feet are the
    only thing the reader would see resume it, and the arc is not the stroke.
    A hole starting above 0 leaves the span :func:`_drawn_spans` emits before
    it, and one ending below 1 the span after it; between two merged holes there
    is always a span, :func:`_merged` having joined every pair that touches.

    The comparison is on the exact parameters :func:`_hop_gap` already computed,
    so nothing is measured in pixels and no clearance is assumed from a grid
    constant — a run can be shorter than a hop's diameter wherever a crossing
    falls within a radius of a box or a bend, and that is the case this decides.
    """
    first, last = hole
    return first > 0 and last < 1


def _punched(gap: _Interval, holes: tuple[_Interval, ...]) -> bool:
    """Whether one hop's own gap sits inside a hole that survived.

    The holes are disjoint and every gap lies within exactly one of them, so at
    most one containment can hold and this is that hole's answer read back.
    """
    return any(first <= gap[0] and gap[1] <= last for first, last in holes)


def _edge_gaps(
    points: tuple[layout.Point, ...], hops: Collection[layout.Hop]
) -> tuple[dict[int, tuple[_Interval, ...]], frozenset[layout.Hop]]:
    """Where one chain is left undrawn for its own hop glyphs, keyed by run — and which hops earned one.

    A run carrying several hops gets several gaps: sorted by parameter, then
    merged where two touch, so a congested stretch comes out as one opening
    rather than as slivers of stroke drawn inside its own arcs. The sort is over
    the exact rationals and the merge is a single pass, so the answer is a
    function of the sheet and of nothing about iteration order.

    **A hole that would not leave drawn stroke on both sides of it is not
    punched, and no hop that formed it is denoted**
    (:func:`_leaves_stroke_either_side`) — the crossing goes unmarked and the
    stroke runs through it whole. The unit is the *merged* hole and not any one
    hop's gap, because the opening a reader sees is the merged one; so several
    hops sharing a hole that reaches a run's end all lose their glyphs together.
    An undenoted crossing costs the reader which of two strokes passes over;
    a stub left by a gap with nothing resuming after it costs them the stroke.
    """
    per_run: dict[int, list[tuple[_Interval, layout.Hop]]] = {}
    for hop in hops:
        per_run.setdefault(hop.hopping_segment, []).append((_hop_gap(hop, points=points), hop))

    gaps: dict[int, tuple[_Interval, ...]] = {}
    denoted: set[layout.Hop] = set()
    for index, found in per_run.items():
        holes = tuple(hole for hole in _merged(sorted(gap for gap, _ in found)) if _leaves_stroke_either_side(hole))
        if holes:
            gaps[index] = holes
        denoted |= {hop for gap, hop in found if _punched(gap, holes)}
    return gaps, frozenset(denoted)


@dataclass(frozen=True, slots=True)
class _Denotation:
    """One sheet's hops resolved: where each stroke opens, and which crossings are marked.

    ``gaps`` is keyed by :attr:`layout.PlacedEdge.key` and then by run. ``hops``
    is the subset of ``sheet.hops`` that carries a glyph, in the sheet's own
    emission order — the membership test runs against a set, so no set iteration
    reaches an output position.
    """

    gaps: Mapping[tuple[str, str], Mapping[int, tuple[_Interval, ...]]]
    hops: tuple[layout.Hop, ...]


def _denote(sheet: layout.Sheet) -> _Denotation:
    """Resolve every hop on the sheet at once: one pass, read by the strokes and by the glyphs alike.

    The gap and the arc are two halves of one decision, so they are decided
    together rather than asked twice and risked disagreeing.
    """
    per_edge: dict[tuple[str, str], list[layout.Hop]] = {}
    for hop in sheet.hops:
        per_edge.setdefault(hop.hopping, []).append(hop)

    gaps: dict[tuple[str, str], Mapping[int, tuple[_Interval, ...]]] = {}
    denoted: set[layout.Hop] = set()
    for edge in sheet.edges:
        found, marked = _edge_gaps(edge.points, per_edge.get(edge.key, ()))
        gaps[edge.key] = found
        denoted |= marked
    return _Denotation(gaps, tuple(hop for hop in sheet.hops if hop in denoted))


def denoted_hops(sheet: layout.Sheet) -> tuple[layout.Hop, ...]:
    """Which of ``sheet.hops`` the sheet actually marks, in the sheet's own order.

    ``sheet.hops`` is the geometric crossing count and stays whole; this is how
    many of those crossings carry a bridge glyph. The two differ wherever a hop's
    gap could not be punched (:func:`_edge_gaps`), and a census reporting the
    first without the second would say every crossing is denoted when some are
    not.
    """
    return _denote(sheet).hops


def draw_hop_over(hop: layout.Hop, *, points: tuple[layout.Point, ...], colour: str) -> ET.Element:
    """The bridge glyph: a semicircular arc standing on the two points the stroke is cut at.

    ``points`` is the hopping chain's own vertices — :attr:`layout.PlacedEdge.points`
    of the edge ``hop.hopping`` names — because what the glyph must sit on is the
    stroke drawn through them, not the chords between them.

    **The endpoints are the drawn stroke's own points** (:func:`_hop_ends`), at
    the two parameters :func:`_edge_path` opens it over, **ordered by screen x**
    — and the arc bulges toward ``n = (d.y, -d.x)`` for that chord's direction
    ``d``, which is screen up for every edge that is not vertical and screen
    right for one that is. One rule, no cases: ``n`` is a fixed rotation of
    ``d``, so the arc's handedness is constant and the sweep flag is a constant
    with it. The ordering is what makes that constant handedness a *screen* fact
    rather than an edge-local one — an edge whose graph direction runs right to
    left is drawn right to left, and a rotation of its own vector would dip the
    bridge downward on exactly those edges.

    **The radius is half the chord those two points span and not
    :data:`style.HOP_RADIUS`.** That constant states how wide an opening the
    stroke takes, measured along the tangent; on a curved run the stroke's own
    points at the resulting parameters stand a little nearer together than the
    tangent's do, and a circle of the fixed radius would not pass through both.
    Deriving the radius from the chord is what lets the feet be the stroke's
    points and the arc still close on them. On a straight run the two
    constructions are the same points and the radius comes back to the constant.

    **The stroke is open between the arc's feet, and the gap is the hopping
    stroke's own.** :func:`_hop_gap` projects those feet back onto the run and
    :func:`_edge_path` omits the span between them, so the hopping stroke comes
    in, arcs over and continues with nothing closing the bottom of the arc —
    which is the difference between a line stepping over another and a lens.
    **Whether a hop gets a glyph at all is decided before this is called**
    (:func:`_leaves_stroke_either_side`), the arc and the hole being two halves
    of one mark. The
    **crossed** stroke is not touched and runs through the crossing unbroken:
    which of the two is lifted is ``hop.hopping``'s answer, and taking a bite out
    of the other one would say the opposite of what the glyph says.

    **The crossing is the chain's and the stroke is the curve's, and the glyph
    goes on the curve.** ``hop`` is :func:`layout._hops`' answer over the straight
    chords between a chain's vertices — which strokes cross and where, its
    question and untouched here. The stroke drawn through those same vertices is
    a cubic (:func:`_control_points`), so the crossing's own chord parameter
    (:func:`_chord_parameter`) is what the cubic is evaluated at for the centre
    and differentiated at for the tangent. Every step is an exact rational
    polynomial evaluation: no curve-curve intersection is solved, nothing is
    root-found, and there is no tolerance to choose. The two lengths this needs —
    normalising that tangent to the opening's width, and halving the chord the
    arc then spans — are integer square roots (:func:`_fixed_length`) for the
    same reason every other length here is.
    """
    (first_x, first_y), (second_x, second_y) = _hop_ends(hop, points=points)
    radius = _half_chord(second_x - first_x, second_y - first_y)
    data = (
        "M",
        format_number(first_x),
        format_number(first_y),
        "A",
        format_number(radius),
        format_number(radius),
        "0",
        "0",
        _ARC_SWEEP,
        format_number(second_x),
        format_number(second_y),
    )
    return ET.Element(
        "path",
        {
            "class": "hop",
            "d": " ".join(data),
            "fill": "none",
            "stroke": colour,
            "stroke-width": format_number(style.HOP_STROKE_WIDTH),
        },
    )


def _box(placed: layout.PlacedNode, *, foreign: bool) -> ET.Element:
    stub = placed.node.is_stub
    attrib = {
        "x": format_number(placed.x),
        "y": format_number(placed.y),
        "width": format_number(placed.width),
        "height": format_number(placed.height),
        "fill": _node_fill(placed, foreign=foreign),
        "stroke": style.STUB_STROKE if stub else style.NODE_STROKE,
        "stroke-width": format_number(style.NODE_STROKE_WIDTH),
    }
    # Dashes are the defect channel: a ghost id's stub and a cycle member's box,
    # the two defects a box itself can carry.
    dash = style.DASH_STUB if stub else style.DASH_BACK_EDGE if placed.cycle_member else None
    if dash is not None:
        attrib["stroke-dasharray"] = dash
    return ET.Element("rect", attrib)


def _label(placed: layout.PlacedNode, *, line: int, text: str) -> ET.Element:
    """One label line, offset inside its own box by :mod:`style` constants alone.

    The baseline of line ``n`` is the box top plus the vertical padding, one
    font size for the first baseline, and one line height per line after it. No
    other box enters the calculation.
    """
    element = ET.Element(
        "text",
        {
            "x": format_number(placed.x + style.BOX_PADDING_X),
            "y": format_number(placed.y + style.BOX_PADDING_Y + style.FONT_SIZE + line * style.LINE_HEIGHT),
            "fill": style.LABEL_FILL,
        },
    )
    element.text = text
    return element


def _node_element(placed: layout.PlacedNode, *, link_base: PurePosixPath | str, foreign: bool) -> ET.Element:
    """One node's group, wrapped in a link when the index names a definition for it."""
    group = ET.Element("g", {"class": "node"})
    if not placed.node.is_stub:
        # First child of the group, which is the condition SVG puts on a
        # `title` being its parent's: the group is the innermost element under
        # the link, so this is the title a viewer resolves from anywhere inside
        # the box. A stub gets none — there is no record to take one from, and
        # an empty tooltip would assert the node has no name.
        ET.SubElement(group, "title").text = _node_title(placed)
    group.append(_box(placed, foreign=foreign))
    for line, text in enumerate(_label_lines(placed)):
        group.append(_label(placed, line=line, text=text))

    href = node_href(placed, link_base=link_base)
    if href is None:
        return group
    anchor = ET.Element("a", {"href": href})
    anchor.append(group)
    return anchor


# ---------------------------------------------------------------------------
# The document
# ---------------------------------------------------------------------------


def build(
    sheet: layout.Sheet,
    *,
    link_base: PurePosixPath | str,
    foreign: Collection[str] = (),
) -> ET.Element:
    """The sheet as an element tree, in the declared draw and emission orders.

    Edges first, then the hop glyphs, then the node boxes with an opaque fill.
    Each stroke is emitted already open under its own glyphs — a hop belongs to
    the hopping edge, so the gap goes in that edge's path (:func:`_edge_gaps`)
    and the crossed edge is drawn whole. **A crossing whose gap cannot be
    punched is drawn as no crossing at all**: no gap and no arc, the stroke
    running through it whole (:func:`_leaves_stroke_either_side`), which is what
    :func:`denoted_hops` counts and a census reports.
    An edge spanning several layers is routed through a dummy column in each
    (:mod:`kb_tools.kb_graph.layout`) rather than sliced across the boxes
    between its ends, so the draw order is what settles the remaining overlaps
    — a stroke meeting a box still passes under it, which is the schematic
    reading and costs nothing.

    ``link_base`` is the KB root relative to the sheet's own directory
    (:func:`relative_link_base`). ``foreign`` is the one-hop neighbour set on a
    domain sheet — the ids drawn in the outline-only foreign style — which is the
    caller's selection policy and not this module's.

    Every order here is the one :class:`layout.Sheet` already fixed, so no set
    or dict iteration reaches an output position.
    """
    root = _root(sheet.view_box)
    root.append(_background(sheet.view_box))

    placed_nodes = {placed.id: placed for placed in sheet.nodes}
    denotation = _denote(sheet)

    edges = ET.SubElement(root, "g", {"class": "edges"})
    colours: dict[tuple[str, str], str] = {}
    for edge in sheet.edges:
        stroke = _edge_presentation(edge, placed_nodes)
        colours[edge.key] = stroke.colour
        edges.append(_edge_element(edge, stroke=stroke, gaps=denotation.gaps[edge.key]))

    hops = ET.SubElement(root, "g", {"class": "hops"})
    chains = {edge.key: edge.points for edge in sheet.edges}
    for hop in denotation.hops:
        hops.append(draw_hop_over(hop, points=chains[hop.hopping], colour=colours[hop.hopping]))

    nodes = ET.SubElement(root, "g", {"class": "nodes"})
    for placed in sheet.nodes:
        nodes.append(_node_element(placed, link_base=link_base, foreign=placed.id in foreign))
    return root


def serialize(root: ET.Element) -> str:
    """The pinned serializer call, plus the declaration and one trailing newline.

    Attribute order is insertion order, which the toolchain's 3.11+ floor
    guarantees. The caller writes the result with ``encoding="utf-8",
    newline="\\n"``.
    """
    ET.indent(root, space=_INDENT)
    return _DECLARATION + _NEWLINE + ET.tostring(root, encoding="unicode") + _NEWLINE


def render(
    sheet: layout.Sheet,
    *,
    link_base: PurePosixPath | str,
    foreign: Collection[str] = (),
) -> str:
    """The whole document as text: :func:`build` then :func:`serialize`."""
    return serialize(build(sheet, link_base=link_base, foreign=foreign))


__all__ = [
    "SVG_NAMESPACE",
    "build",
    "denoted_hops",
    "draw_hop_over",
    "format_number",
    "node_href",
    "relative_link_base",
    "render",
    "serialize",
]
