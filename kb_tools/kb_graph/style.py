"""Every presentation constant the claim-graph sheet is drawn with.

The pitches, the box padding, the character advance and the pinned font, the
label cap, the band palette, the dash patterns, the hop radius, and the declared
order tuples. This module imports :mod:`kb_tools.kb_schema` for the band ladder
and nothing else.

**Every magnitude here is an ``int``.** That is what makes every coordinate
:mod:`kb_tools.kb_graph.layout` computes exact, what makes the crossing test
divide nothing, and what keeps a golden diff from widening under floating-point
noise. A float in this module would undo all three.

**Geometry is metric-free.** Box width is a function of a character count and
the font pinned here; nothing measures text, and the emitted document names the
same font it was sized against, so the boxes fit in a renderer nobody ran.

**Nothing here gates.** No refusal, no exit code and no check derives from any
constant in this module. They decide how the sheet looks and nothing else.

Stdlib only.
"""

from kb_tools import kb_schema

# ---------------------------------------------------------------------------
# Type metrics — the pinned font, and the advance the boxes are sized by
# ---------------------------------------------------------------------------

#: The font the sheet is sized against and the font it asks for. A family list
#: rather than one name because no single monospace family is present on every
#: host; every member of it — and the generic ``monospace`` fallback — advances
#: at or below :data:`CHAR_ADVANCE` for :data:`FONT_SIZE`, so a box sized here
#: fits its label in any of them.
FONT_FAMILY = "DejaVu Sans Mono, Menlo, Consolas, monospace"

FONT_SIZE = 12

#: Horizontal advance of one character at :data:`FONT_SIZE`. Monospace faces
#: advance at roughly 0.6 em (7.2 px here); this is rounded **up** to an integer
#: so a label can only ever be narrower than the box it was sized for.
CHAR_ADVANCE = 8

#: Baseline-to-baseline distance of one label line to the next.
LINE_HEIGHT = 16

#: The cap on **every** label line — the node's id as much as each line its
#: title wraps over. A longer line is truncated to this many characters with
#: :data:`TRUNCATION_ELLIPSIS`, and the whole of both goes in the node's
#: ``title`` child, where it costs no layout at all. One cap and no exception is
#: what makes this the sheet's single width lever: nothing drawn inside a box
#: can be wider than the box, so :data:`BOX_WIDTH` is a width the labels fit
#: rather than a width that usually holds.
#:
#: **What the cap is graded on is whether two claims can be told apart, not how
#: much of a title shows.** Since the title wraps (:data:`TITLE_LINES`) rather
#: than being cut at one line, a *collision* — two nodes drawing identical label
#: text from different titles — is the failure that makes a sheet unreadable,
#: and it is what these two constants were ruled against. Over the drawn node
#: sets of ``mini-kb`` (32), ``ModernCorp`` (28), ``ModernCorpPristine`` (43) and
#: ``2609.09855v1`` (156), collisions at ``chars × lines``: 13×1 — the cap before
#: this one — collides on 28% of Pristine and 22% of the arXiv corpus; 16×3 and
#: 18×3 leave one on the arXiv corpus; **18×4 leaves none on any of the four**,
#: as do 20×3, 20×4, 24×2 and every wider setting.
#:
#: **Among the settings that clear it, this is the narrowest that also reads.**
#: Width is the scarce axis — this cap is the only lever that multiplies into
#: sheet width, through ``BOX_WIDTH`` and ``COLUMN_PITCH``, once per column of
#: the widest layer — and on the arXiv sheet 18×4 renders at 7160×3676 against
#: 20×3's 7808×3244: 648px narrower, and 86% of Pristine's titles whole against
#: 63%, for 432px of height on the axis the sheets have empty bands in. 16×4 is
#: narrower still at 6512px but breaks more words mid-token and cuts
#: ``work-bardenet2015``, and 24×2 clears the curve at 9104px, which spends the
#: scarce axis to buy the plentiful one back.
#:
#: The id line lands on the same number independently. A minted id is ten
#: characters by :mod:`kb_tools.kb_schema`'s grammar and a framework id twelve as
#: authored, but a ``work-`` id is a citation key and is bounded by nothing: the
#: longest drawn across the four corpora is ``work-bardenet2015`` at 17, and 18
#: is the smallest cap holding **every** id on **every** one of those sheets
#: whole. The cap before this one cut ``work-lasalle1961`` and
#: ``work-khalil2002`` on ``ModernCorp``. **No finite cap closes that class**, so
#: this is a knee the ids happen to clear rather than a bound derived from them;
#: the line truncates rather than being assumed to fit.
LABEL_CHARS = 18

#: How many lines the title wraps over beneath the id line. The wrap rule and
#: the truncation of a tail that does not fit are
#: :func:`kb_tools.kb_graph.svg._wrapped`'s; this is the count it wraps into,
#: and :data:`BOX_HEIGHT` is a function of it, never of the title actually
#: drawn.
#:
#: **Four is the fewest that leaves no collision on any measured corpus at
#: :data:`LABEL_CHARS`** (the curve is recorded there): three leaves one on the
#: arXiv corpus, four leaves none, and every line past four is spent on a
#: metric that has already saturated.
#:
#: **Past four, a line costs more than it shows, because every box is
#: :data:`BOX_HEIGHT` whether its title fills it or not.** Title lines a node
#: actually uses at this cap, median and 90th percentile: ``mini-kb`` 2 and 4,
#: ``ModernCorp`` 3 and 4, ``ModernCorpPristine`` 4 and 5, ``2609.09855v1`` 6 and
#: 7. So four holds the 90th percentile of three of the four corpora, and a
#: fifth and sixth line — which would take whole titles on the arXiv corpus from
#: 17% to 41% to 76% — is white space in the median box of every other sheet in
#: the tree. Rasterised, that reads as boxes half empty and a sheet a third
#: taller for it.
#:
#: **One setting does not serve the 156-claim sheet the way it serves the other
#: three, and this is ruled rather than split.** That corpus's titles run to a
#: median of 81 characters, so 17% of them are drawn whole here against 86% of
#: Pristine's. What it does get is the property that was actually missing: no two
#: of its 156 claims draw the same label, and the four lines carry enough of each
#: title to say what the claim is about — ``Under-determination of the
#: predictor's input space and paramet…`` is a claim a reader can place, where
#: the single truncated line before it was not. The whole title is in the node's
#: ``title`` tooltip and behind its hyperlink, at no layout cost.
TITLE_LINES = 4

#: The single character a truncated title ends with.
TRUNCATION_ELLIPSIS = "…"

# ---------------------------------------------------------------------------
# Box and grid geometry
# ---------------------------------------------------------------------------

BOX_PADDING_X = 8
BOX_PADDING_Y = 6

#: Box width, a **constant** — a function of the label cap and the character
#: advance, never of the label actually drawn, so a long title never moves a
#: neighbour. Since :data:`LABEL_CHARS` caps every line, this is also a width
#: no label exceeds.
BOX_WIDTH = 2 * BOX_PADDING_X + LABEL_CHARS * CHAR_ADVANCE

#: Box height, a **constant** on the same terms as :data:`BOX_WIDTH`: the id
#: line plus :data:`TITLE_LINES` title lines plus padding — a function of the
#: caps, never of the title actually drawn, so a short title leaves a box the
#: same height as a long one and a long one moves no neighbour.
BOX_HEIGHT = (1 + TITLE_LINES) * LINE_HEIGHT + 2 * BOX_PADDING_Y

#: Blank space between one column's box and the next. ``BOX_WIDTH`` is
#: ``COLUMN_PITCH - COLUMN_GUTTER`` by construction, which is the grid rule read
#: from the other end: the pitch is a constant, never a cumulative sum of box
#: widths, so inserting a node moves nothing to its right.
#:
#: Two padding widths — the blank between two boxes reads as one box's own
#: horizontal padding on each side, which is the narrowest gap that still
#: separates them. It is also the blank half of the ``COLUMN_PITCH`` separation
#: the coordinate phase holds two occupants apart by at its tightest, so every
#: pixel here is paid once per column of the widest layer.
COLUMN_GUTTER = 16
COLUMN_PITCH = BOX_WIDTH + COLUMN_GUTTER

#: Blank space between one layer's boxes and the next layer's: one box height of
#: air, where it was most of two. It buys no width — the sheet is bound by its
#: widest layer — so what it is spent on is how much of the hierarchy stands on
#: a screen at a zoom that reads the labels.
LAYER_GAP = 44
LAYER_PITCH = BOX_HEIGHT + LAYER_GAP

#: How many pitches one concentric ring stands outside the ring within it
#: (:func:`kb_tools.kb_graph.layout._rings`). A multiplier and not a magnitude,
#: so it steps both axes at once and the rings keep the box grid's own
#: proportions.
#:
#: **One pitch puts consecutive rings exactly as far apart as two side-by-side
#: boxes, so nested rectangles tile a lattice and no ring boundary is visible —
#: and no larger step makes one visible either.** Every candidate a form offers
#: is this multiple of its step-1 position, so raising it scales the whole
#: arrangement and scales nothing else: the boxes keep their size, and the
#: occupants of one ring spread along their own ring exactly as fast as the
#: rings separate. Fitted to a screen the picture is the step-1 picture with
#: smaller boxes; at a zoom that reads the labels, a step of 2 or more leaves
#: two or three boxes in the window and takes away the neighbours a boundary
#: would have to be seen against. Rasterised and looked at over both forms and
#: both of ``ModernCorpPristine`` and ``2609.09855v1``, no step in 1 to 4 shows
#: one.
#:
#: **What the step costs grows with its square and what it buys is nothing a
#: reader sees**, measured over those four sheets. Total horizontal edge length
#: multiplies by the step almost exactly: 2, 3 and 4 times, on every one of
#: them. ``viewBox`` area multiplies by 3.7, 8.0 and 14.0 on
#: ``ModernCorpPristine`` and by 2.7, 5.2 and 8.4 on the arXiv corpus, whose
#: orphan block takes the layer and column pitches and so does not scale with
#: this.
#:
#: Crossings do not follow the step in any direction. On the shipped rectangle
#: form they rise slightly — ``ModernCorpPristine`` 47, 49, 50, 49 and the arXiv
#: corpus 113, 115, 115, 116. **The one figure the step does move is crossings
#: on the ellipse form of the arXiv corpus, 136 at 1 against 123 at 2 and no
#: further**, which is a ring at step 1 growing to clear that form's diagonal
#: sector and not the step buying anything; it costs 2.7 times the area, and it
#: is on the form that does not ship.
#:
#: A comment here once recorded the step-2 cost on that corpus as 3% of height,
#: on the reasoning that most rings had already outgrown their first size. The
#: current placer does not reproduce it and the reasoning does not survive the
#: scaling above: the sheet goes from 2452 to 4628 pixels tall.
RING_STEP = 1

#: How many orphans stand in one row of the grid block beneath the hierarchy.
#: Four, so the block comes out tall and narrow rather than wide and short: a
#: long vertical scroll is cheaper to read than a long horizontal one, and the
#: block's height then reads at a glance as how much of the KB is unattached.
#: The block takes the layer pitch and the column pitch above it, so it needs no
#: magnitude of its own.
ORPHAN_ROW = 4

#: Added around the union of the box extents to form the ``viewBox``.
#: Comfortably larger than :data:`HOP_RADIUS`, so a glyph on a boundary edge
#: cannot leave the sheet.
MARGIN = 24

#: Half the opening the hop glyph leaves in the stroke it is drawn on, stepped
#: along that stroke's tangent either side of the crossing. **The arc's own
#: radius is not this**: the glyph stands on the stroke's two cut points and
#: takes half the chord they span, which comes back to this magnitude on a
#: straight run and stands a little under it on a bending one
#: (:func:`kb_tools.kb_graph.svg.draw_hop_over`). Sized against
#: :data:`FONT_SIZE` so the step registers at whatever zoom the labels do;
#: below that the gapped glyph reads as a kink in the line rather than a step
#: over it. It stays under :data:`MARGIN`, so a glyph on a boundary edge cannot
#: leave the sheet, and its opening stays shorter than the shortest run the
#: grid can produce.
#: Two glyphs closer than twice this abut or overlap, which is accepted rather
#: than merged: merging is order-dependent, and a congested region reading as
#: congested is information.
HOP_RADIUS = 12

# ---------------------------------------------------------------------------
# Stroke weights
# ---------------------------------------------------------------------------

NODE_STROKE_WIDTH = 1
EDGE_STROKE_WIDTH = 2
HOP_STROKE_WIDTH = 2

# ---------------------------------------------------------------------------
# The band ramp
# ---------------------------------------------------------------------------
#
# Discrete rungs of the project's own build-band ladder, not a continuous
# gradient: a re-scored claim either moves a band or changes no byte, where a
# gradient rewrites a hex triple on every rescore and drowns the cross-run diff.
#
# Two properties bind, and both are constraints rather than taste: no
# distinction is carried by a red/green pair alone, and the ramp is monotone in
# lightness so it survives greyscale and a screenshot in a review. The sequence
# is Okabe-Ito-derived — a sky-blue tint pair, orange, vermillion, and a dark
# vermillion shade — with relative luminance strictly descending along it.

_BAND_RAMP: tuple[str, ...] = (
    "#bfe3f5",  # ok-to-build
    "#7fc4eb",  # ok-with-caveats
    "#e69f00",  # input-only
    "#d55e00",  # do-not-build
    "#7a2e00",  # refuted
)

#: The off-ladder neutral: ``solidity: null`` / ``fraction: "*pending*"``.
#: A colour, never a dash — dashes are reserved for defects, so colour
#: says how strong, dash says whether the bookkeeping is sound.
PENDING_FILL = "#9e9e9e"

#: One colour per rung of :data:`kb_schema.BUILD_BAND_LADDER`, plus the pending
#: bucket under :data:`kb_schema.UNKNOWN_BAND_SLUG`. Keyed by the ladder's own
#: slugs rather than by a retyped list of them, and zipped ``strict`` so a rung
#: added to the ladder fails loudly here instead of rendering uncoloured.
BAND_PALETTE: dict[str, str] = {
    **{band.slug: colour for band, colour in zip(kb_schema.BUILD_BAND_LADDER, _BAND_RAMP, strict=True)},
    kb_schema.UNKNOWN_BAND_SLUG: PENDING_FILL,
}

#: A ``depends`` edge onto an invariant or an axiom. Framework
#: dependencies contribute 1.0 to the solidity min and never pend, so the edge
#: takes the ladder's **top rung** — read from the ladder rather than named as a
#: hex here, because the rung is that rule's answer and not this module's.
FRAMEWORK_EDGE_COLOUR = BAND_PALETTE[kb_schema.BUILD_BAND_LADDER[0].slug]


def band_colour(value: float | str | None) -> str:
    """The ramp colour for one strength value: a ``supports`` edge's on-point
    ``fraction`` or a ``strengthens`` edge's ``strength``.

    The band comes from :func:`kb_schema.band_for_solidity` — the project's own
    ladder, which both the build and the query sides already read — so the ramp
    here is a palette over that vocabulary and never a second one. Anything
    non-numeric is the pending case: ``None``, or the literal
    :data:`kb_schema.PENDING_LITERAL` a fraction may carry. It is recognised by
    *not being a number* rather than by comparing against a typed-out string,
    and it renders in the off-ladder neutral — a colour, never a dash, because
    dashes are reserved for defects.
    """
    numeric = value if isinstance(value, (int, float)) and not isinstance(value, bool) else None
    band = kb_schema.band_for_solidity(numeric)
    return BAND_PALETTE[kb_schema.UNKNOWN_BAND_SLUG if band is None else band.slug]


# ---------------------------------------------------------------------------
# Node and edge presentation
# ---------------------------------------------------------------------------

#: An invariant or axiom: a distinct framework fill, deliberately **not** a rung
#: of the ramp. Bedrock is a convention of the solidity rule rather than a
#: stored value, and painting it at the top rung would assert a score that does
#: not exist.
FRAMEWORK_FILL = "#e3d3ec"

#: An experiment carries no solidity of any kind; its ``status`` goes on its own
#: label line rather than being asserted as a score.
EXPERIMENT_FILL = PENDING_FILL

NODE_STROKE = "#333333"
LABEL_FILL = "#111111"
SHEET_BACKGROUND = "#ffffff"

#: A ghost id: a stub with a distinct outline, its id shown and no title.
STUB_FILL = "none"
STUB_STROKE = "#b00020"

#: A one-hop foreign neighbour on a domain sheet: outline only, no fill.
FOREIGN_FILL = "none"

#: Dash patterns, the one channel reserved for defects. Values are SVG
#: ``stroke-dasharray`` strings rather than magnitudes: nothing computes with
#: them, and no coordinate is derived from one.
DASH_STUB = "3 3"
DASH_BACK_EDGE = "6 4"

#: The mark a stroke carrying two relations for one fact takes.
CONFLICT_STROKE = "#b00020"

# ---------------------------------------------------------------------------
# The declared order tuples
# ---------------------------------------------------------------------------
#
# The ``FACT`` census lines are emitted in these orders and no other. A census
# that iterated a dict of counts would order its lines by whatever the corpus
# happened to contain first, and no incidental order may reach an output
# position.
#
# There is no node-type order here: that one is
# :data:`kb_schema.NODE_KINDS`' own declared order, which is the vocabulary a
# node-type census iterates. A tuple here would be a second spelling of it, and
# the kind it omitted would be the kind the census never reported.

#: Relation census order.
#:
#: Equal in value to :data:`kb_tools.kb_graph.model.RELATION_PRECEDENCE` and
#: deliberately not imported from it: this module's only dependency is
#: ``kb_schema``, and importing ``model`` would break that. The two constants
#: also answer different questions — that one is the dedupe *semantics* (which
#: relation survives a group disagreeing on relation), this one is the *report
#: order*. Their coincidence is pinned by a test rather than asserted here, so a
#: future divergence surfaces as a decision instead of a silent drift.
CENSUS_RELATIONS: tuple[str, ...] = ("depends", "supports", "strengthens", "rests-on", "references")

#: Defect-class census order.
CENSUS_DEFECT_CLASSES: tuple[str, ...] = (
    "ghost-id",
    "back-edge",
    "isolated-node",
    "disconnected-component",
    "relation-conflict",
)
