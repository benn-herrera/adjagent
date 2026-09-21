"""Read-only measurement over rendered claim-graph sheets.

Runs no op and touches no KB: every figure below is read out of an SVG a
sanctioned runner target already wrote (``just regenerate-mini-kb-golden``, or
``just --justfile kb-testing/justfile render-claim-graph <repo>``).

**It imports nothing from ``kb_tools`` — not even a constant.** An instrument
that took the renderer's own ``BOX_WIDTH`` and ``COLUMN_PITCH`` as its yardstick
could never report that a sheet disagrees with the geometry it was meant to
have, having adopted that geometry as the definition of correct; it would
detect staleness and nothing else. Both magnitudes are in the document. The box
size is a node ``rect``'s ``width`` and ``height``, which every box shares by
construction — checked here, and a violation is reported rather than assumed
away. The column pitch is the smallest positive gap between two boxes standing
on one row, which is the grid step the sheet was actually drawn on; a sheet
where no row holds two boxes implies no pitch, and every figure derived from
one reads 0.

**There is no ``layers``, ``layer0`` or ``layer0_px`` column.** All three read a
layer off a screen row, which works only while the occupants are arranged
linearly and a layer and a row are the same thing: ``layers`` counted the
distinct box rows at or above the baseline, ``layer0`` the boxes standing on
``y == 0``, and ``layer0_px`` the width that many columns cannot go below.
Where the arrangement is concentric a layer is a ring index and stands at a
radius rather than on a row — the bedrock is the centre and nothing lands on
``y == 0`` — so none of the three is on the document. ``layers`` said so by
disagreeing with the census; the two ``layer0`` figures said nothing and read a
plausible zero on every ring sheet instead. Recovering any of them would
mean deriving the sheet's centre and step and reconstructing the placer's
geometry — the instrument holding the sheet to the generator's own geometry,
which is the one thing it must not do. A figure that cannot be read off the
document is not imported: the column goes.

Strokes and hop glyphs are both ``path`` elements and are told apart by
``class`` — ``edge`` and ``hop`` — which is the only thing that separates them.

**``hop_glyphs`` counts glyphs and not crossings**, which is why it is not
called ``crossings``: the renderer marks a crossing only where the gap the
glyph needs leaves stroke on both sides of it, so one too near a box or a bend
is drawn plain and nothing on the document distinguishes it from uncrossed
stroke. The geometric count is not here and is not derivable. A stroke on the
document carries its ``d`` and its colour and no node identity, while the
crossings a census counts exclude every pair of edges sharing a node — a fan-in
at one box's anchor coincides in coordinates and is not a crossing — so
intersecting every stroke pair would count those; and it would have to pick
between the chords a crossing is defined over and the curves actually drawn,
both of which are the generator's choice rather than the document's.

A stroke a hop crosses is emitted **open**: one ``path`` whose ``d`` is several
subpaths, broken at the arc's two feet. Those subpaths are one stroke — one
edge with holes punched in it — so they are spliced back into a single chain
and a gapped edge counts once, at the length it was drawn. The two points
either side of a break are the feet, not bends, and dropping them is what lets
every figure here be read without knowing how wide a gap is.

The width-setting layer is the one with the widest occupied span, and its
occupants are boxes plus placeholders — a placeholder is charged a full pitch
exactly as a box is. ``min_w`` is what that many occupants cannot go below,
``(n - 1) * pitch + box_width``; ``slack`` is the layer's actual span less that
floor, and is the only honest "spread" figure. ``hole_px`` is the placeholders'
share of the sheet's own width.

    kb-testing/tools/measure-sheet.py <label>=<sheet.svg> ...

Reached through ``just --justfile kb-testing/justfile measure-sheet``.
"""

import logging
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

_LOG = logging.getLogger("measure-sheet")

_SVG = "{http://www.w3.org/2000/svg}"

#: How many coordinate tokens each path command carries. The last is the point
#: the stroke passes through; any before it are control points, which are where
#: the curve is pulled and not where the chain bends. A straight run is written
#: ``L`` and a curved one ``C``, and both name one vertex.
_COMMAND_VERTICES = {"M": 1, "L": 1, "C": 3}

#: Reported in this order, which is the order the tables in a measurement row
#: are read in.
COLUMNS = (
    "view_w",
    "view_h",
    "bytes",
    "boxes",
    "strokes",
    "straight",
    "routed",
    "dummies",
    "hop_glyphs",
    "edge_len",
    "box_w",
    "pitch",
    "occ_n",
    "occ_box",
    "occ_hole",
    "occ_floor",
    "wide_n",
    "wide_box",
    "wide_hole",
    "min_w",
    "span_w",
    "slack",
    "hole_px",
    "hole_pct",
)


@dataclass(frozen=True)
class Box:
    """One drawn node, as the document gives it."""

    x: int
    y: int
    width: int
    height: int

    @property
    def centre(self) -> int:
        """The column the box stands in, which is where its strokes anchor."""
        return self.x + self.width // 2


@dataclass(frozen=True)
class Grid:
    """The sheet's own geometry, read off the boxes it drew and nowhere else."""

    box_width: int
    box_height: int
    pitch: int

    def floor(self, occupants: int) -> int:
        """The least width ``occupants`` columns can occupy on this grid."""
        return max(occupants - 1, 0) * self.pitch + (self.box_width if occupants else 0)


def _boxes(root: ET.Element) -> list[Box]:
    """Every node box. The one ``rect`` that is not one carries ``class="sheet"``."""
    return [
        Box(
            x=int(rect.get("x", "0")),
            y=int(rect.get("y", "0")),
            width=int(rect.get("width", "0")),
            height=int(rect.get("height", "0")),
        )
        for rect in root.iter(f"{_SVG}rect")
        if rect.get("class") != "sheet"
    ]


def _grid(boxes: Sequence[Box], *, sheet: Path) -> Grid:
    """The box size and column pitch this sheet was drawn on.

    Both are measured, and the two readings that could come out wrong are
    reported rather than absorbed: boxes of more than one size mean the
    document is not what a single box size describes, and a sheet with no row
    holding two boxes states no pitch at all. Measuring against the commonest
    size keeps one rogue box from moving every other figure.
    """
    if not boxes:
        return Grid(box_width=0, box_height=0, pitch=0)

    widths = Counter(box.width for box in boxes)
    heights = Counter(box.height for box in boxes)
    if len(widths) > 1:
        _LOG.error("%s: node boxes are not one width — %s; measuring against the commonest", sheet, dict(widths))
    if len(heights) > 1:
        _LOG.error("%s: node boxes are not one height — %s; measuring against the commonest", sheet, dict(heights))

    rows: dict[int, list[int]] = {}
    for box in boxes:
        rows.setdefault(box.y, []).append(box.x)
    gaps = [
        second - first for row in rows.values() for first, second in zip(sorted(row), sorted(row)[1:]) if second > first
    ]
    if not gaps:
        _LOG.warning(
            "%s: no row holds two boxes, so the sheet states no column pitch — figures derived from one read 0", sheet
        )

    return Grid(
        box_width=widths.most_common(1)[0][0],
        box_height=heights.most_common(1)[0][0],
        pitch=min(gaps, default=0),
    )


def _subpaths(data: str) -> list[list[tuple[float, float]]]:
    """One point list per pen-down run in ``data``, control points dropped.

    An ``M`` after the first is the pen coming back down, which opens a new
    run. Coordinates are read as written: a break coordinate is fractional and
    carrying it is what keeps a spliced chain honest about where the pen was.
    """
    tokens = data.split()
    runs: list[list[tuple[float, float]]] = []
    index = 0
    while index < len(tokens):
        command = tokens[index]
        carried = _COMMAND_VERTICES.get(command)
        if carried is None:
            raise ValueError(f"unsupported path command {command!r} in {data!r}")
        x, _, y = tokens[index + carried].partition(",")
        point = (float(x), float(y))
        if command == "M":
            runs.append([point])
        elif runs:
            runs[-1].append(point)
        else:
            raise ValueError(f"path data opens with {command!r} rather than a move: {data!r}")
        index += carried + 1
    return runs


def _chain(data: str) -> list[tuple[float, float]]:
    """The vertices one stroke is drawn through, control points dropped.

    A chain's shape is what it is routed through, not how it is painted: an
    adjacent-layer run is written ``L`` and a spanning one ``C``, and both carry
    the same one vertex per run. Reading the vertices rather than the commands
    is what makes the dummy count survive a change of stroke shape.

    The subpaths of one ``path`` element are one stroke, and splicing them is
    what keeps that true of the figures: a hop punches a hole in an edge, so
    the point a subpath ends on and the point the next begins on are the two
    feet of that arc rather than vertices the edge is routed through. Dropping
    the pair and joining the runs leaves one chain, continuous across the gap —
    which is why a gapped edge is one stroke and not two, and why its run is
    measured end to end rather than hole by hole.
    """
    runs = _subpaths(data)
    chain: list[tuple[float, float]] = runs[0] if runs else []
    for run in runs[1:]:
        chain = chain[:-1] + run[1:]
    return chain


def measure(path: Path) -> dict[str, int]:
    """Every figure this instrument reports for one rendered sheet."""
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    _, _, view_w, view_h = (int(value) for value in root.get("viewBox", "0 0 0 0").split())

    boxes = _boxes(root)
    grid = _grid(boxes, sheet=path)
    strokes = [
        _chain(path_element.get("d", ""))
        for path_element in root.iter(f"{_SVG}path")
        if path_element.get("class") == "edge"
    ]
    glyphs = [path_element for path_element in root.iter(f"{_SVG}path") if path_element.get("class") == "hop"]

    # A bend sits at its layer's vertical middle, half a box below the boxes'
    # top edge, so subtracting that puts a placeholder on the row of the boxes
    # it stands among.
    bend_offset = grid.box_height // 2
    hole_columns: dict[float, set[float]] = {}
    hole_count: Counter[float] = Counter()
    horizontal = 0.0
    straight = routed = dummies = 0
    # A stroke's interior vertices are the placeholders it is routed through:
    # two vertices is a straight run between adjacent layers, and every vertex
    # beyond those two is one dummy column a spanning edge cost its layer.
    for chain in strokes:
        horizontal += sum(abs(second[0] - first[0]) for first, second in zip(chain, chain[1:]))
        dummies += max(len(chain) - 2, 0)
        straight += len(chain) == 2
        routed += len(chain) > 2
        for x, y in chain[1:-1]:
            hole_columns.setdefault(y - bend_offset, set()).add(x)
            hole_count[y - bend_offset] += 1

    box_columns: dict[float, set[float]] = {}
    for box in boxes:
        box_columns.setdefault(box.y, set()).add(box.centre)
    box_count: Counter[float] = Counter(box.y for box in boxes)
    columns = {
        y: box_columns.get(y, set()) | hole_columns.get(y, set()) for y in box_columns.keys() | hole_columns.keys()
    }

    # The most-occupied row, counted as occupants rather than as distinct
    # columns: two placeholders the coordinate phase pulled onto one x are two
    # occupants and are charged a pitch each, so the de-duplicated column sets
    # undercount them. This is the count the width floor is owed, `wide_*`
    # below the one the drawn span is read from.
    occupancy = box_count + hole_count
    busiest_y = max(occupancy, key=lambda y: (occupancy[y], -y), default=0)

    # Every figure below is in the column grid's own frame — centre to centre,
    # plus one box width for the two half-boxes at the ends. The sheet's own
    # `viewBox` can exceed `span_w` by up to one box width, because a box in a
    # neighbouring layer overhangs a placeholder column by half a box and the
    # view box unions every layer.
    spans = {y: max(xs) - min(xs) for y, xs in columns.items() if xs}
    widest_y = max(spans, key=lambda y: (spans[y], y), default=0)
    wide_n = len(columns.get(widest_y, ()))
    wide_span = spans.get(widest_y, 0)
    wide_boxes = len(box_columns.get(widest_y, set()))
    wide_holes = len(hole_columns.get(widest_y, set()) - box_columns.get(widest_y, set()))

    return {
        "view_w": view_w,
        "view_h": view_h,
        "bytes": path.stat().st_size,
        "boxes": len(boxes),
        "strokes": len(strokes),
        "straight": straight,
        "routed": routed,
        "dummies": dummies,
        "hop_glyphs": len(glyphs),
        # Summed over the carried coordinates and rounded once, at the end: the
        # column is a pixel length like every other, and rounding each span
        # instead would accumulate the error a fractional foot introduces.
        "edge_len": round(horizontal),
        "box_w": grid.box_width,
        "pitch": grid.pitch,
        "occ_n": occupancy.get(busiest_y, 0),
        "occ_box": box_count.get(busiest_y, 0),
        "occ_hole": hole_count.get(busiest_y, 0),
        "occ_floor": grid.floor(occupancy.get(busiest_y, 0)),
        "wide_n": wide_n,
        "wide_box": wide_boxes,
        "wide_hole": wide_holes,
        "min_w": grid.floor(wide_n),
        "span_w": round(wide_span + (grid.box_width if wide_n else 0)),
        "slack": round(wide_span - max(wide_n - 1, 0) * grid.pitch),
        "hole_px": wide_holes * grid.pitch,
        "hole_pct": round(100 * wide_holes * grid.pitch / view_w) if view_w else 0,
    }


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="measure-sheet: %(levelname)s %(message)s", stream=sys.stderr)
    if not argv:
        _LOG.error("no sheets named — pass <label>=<sheet.svg> pairs")
        return 2
    print(f"{'sheet':<26}" + "".join(f"{name:>11}" for name in COLUMNS))
    for argument in argv:
        label, separator, sheet = argument.partition("=")
        if not separator:
            _LOG.error("%r is not a <label>=<sheet.svg> pair", argument)
            return 2
        figures = measure(Path(sheet))
        print(f"{label:<26}" + "".join(f"{figures[name]:>11}" for name in COLUMNS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
