"""The sheet-measuring instrument, against sheets it did not compute.

``tools/measure-sheet.py`` reads a rendered claim-graph SVG and reports the
figures a measurement row runs on. It went wrong silently once: when strokes
became ``path`` elements it went on looking for ``polyline`` and reported
``strokes 0`` against a sheet carrying 53, which reads as a measurement rather
than as a failure. Most tests here guard a figure that could go to zero because
the instrument stopped finding the thing it counts.

A figure can move as silently as it can zero. A stroke a hop crosses is emitted
open — one ``path``, several subpaths, broken at the arc's feet — and reading
those subpaths as separate strokes inflates ``strokes``, turns two feet into
bends the edge was routed through, and drops the span the pen was up for out of
``edge_len``. Every one of those is a plausible number. What says it did not
happen is measuring one sheet twice, with the holes and without.

The instrument is this tree's tooling, reached through this tree's
``measure-sheet`` recipe, so these run under ``integration-test`` and never
under the root ``test``.

Two independent yardsticks, neither of them the renderer's own constants:

* a hand-built sheet whose geometry is known because it was written down here;
* a real sheet rendered by the shipped op, checked against the ``FACT`` census
  that same run printed — two readings of one drawing that share no code.
"""

import importlib.util
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_INSTRUMENT = _REPO_ROOT / "kb-testing" / "tools" / "measure-sheet.py"

#: The one sheet in the tree that is committed rather than staged, so these
#: never skip for want of a corpus.
_GOLDEN = _REPO_ROOT / "kb_tools" / "tests" / "fixtures" / "graph" / "mini-kb.svg"

#: Where a staging recipe leaves built KBs. Gitignored, and absent on a fresh
#: checkout — the ordinary state of this tree, not a failure.
_STAGED = _REPO_ROOT / "kb-testing" / "test-data" / "transient"


def _load_instrument() -> ModuleType:
    """Load the instrument by path: ``measure-sheet.py`` is not a module name."""
    spec = importlib.util.spec_from_file_location("measure_sheet", _INSTRUMENT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


measure_sheet = _load_instrument()


# ---------------------------------------------------------------------------
# The committed sheet, counted a second way
# ---------------------------------------------------------------------------


def test_a_sheet_carrying_strokes_reports_them() -> None:
    """The breakage this file exists for: zeros that look like data.

    The second reading is a substring count over the bytes, which shares no
    code with the parse — an element name the instrument has stopped looking
    for is still in the file.
    """
    text = _GOLDEN.read_text(encoding="utf-8")
    figures = measure_sheet.measure(_GOLDEN)

    assert figures["strokes"] > 0, "the golden carries strokes and the instrument found none"
    assert figures["strokes"] == text.count('<path class="edge"')
    assert figures["hop_glyphs"] == text.count('<path class="hop"')
    assert figures["boxes"] == text.count("<rect ") - text.count('<rect class="sheet"')


# ---------------------------------------------------------------------------
# The arithmetic, against a sheet whose geometry is written down here
# ---------------------------------------------------------------------------


#: Four boxes 160 wide on a 176 pitch: two on the baseline, one a layer above,
#: and one in the orphan block below it. Two strokes — a straight run between
#: adjacent layers, and one routed through a single placeholder, written as
#: curves the way a spanning stroke is. One hop glyph.
_HAND_BUILT = """<?xml version="1.0" encoding="utf-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="-24 -160 600 420">
  <rect class="sheet" x="-24" y="-160" width="600" height="420" fill="#ffffff" />
  <g class="edges">
    <path class="edge" d="M 80,0 L 168,-44" fill="none" stroke="#bfe3f5" stroke-width="2" />
    <path class="edge" d="M 256,0 C 270,-30 290,-60 300,-90 C 260,-105 200,-120 168,-44" fill="none" stroke="#bfe3f5" stroke-width="2" />
  </g>
  <g class="hops">
    <path class="hop" d="M 200,-20 C 205,-28 215,-28 220,-20" fill="none" stroke="#bfe3f5" stroke-width="2" />
  </g>
  <rect x="0" y="0" width="160" height="92" fill="#e3d3ec" stroke="#333333" stroke-width="1" />
  <rect x="176" y="0" width="160" height="92" fill="#e3d3ec" stroke="#333333" stroke-width="1" />
  <rect x="88" y="-136" width="160" height="92" fill="#e3d3ec" stroke="#333333" stroke-width="1" />
  <rect x="0" y="136" width="160" height="92" fill="#e3d3ec" stroke="#333333" stroke-width="1" />
</svg>
"""


@pytest.mark.parametrize(
    ("column", "expected"),
    [
        ("boxes", 4),
        ("strokes", 2),
        ("straight", 1),
        ("routed", 1),
        # The one interior vertex of the routed chain, at y=-90: a bend sits
        # half a box below its layer's top edge, which puts it on y=-136.
        ("dummies", 1),
        ("hop_glyphs", 1),
        ("box_w", 160),
        ("pitch", 176),
        # |168-80| for the straight run, then |300-256| + |168-300| for the
        # routed one, which is measured at its vertices and not along its curve.
        ("edge_len", 264),
    ],
)
def test_the_figures_a_written_down_sheet_implies(tmp_path: Path, column: str, expected: int) -> None:
    sheet = tmp_path / "hand-built.svg"
    sheet.write_text(_HAND_BUILT, encoding="utf-8")
    assert measure_sheet.measure(sheet)[column] == expected


#: The hand-built sheet as the renderer would emit it with a hop crossing each
#: stroke: the ``path`` stays single and its ``d`` breaks at the arc's two feet,
#: which are fractional and are not where the edge bends. Both holes sit inside
#: a run, so the chain each stroke is drawn through is unchanged — which is
#: what the test below reads. Written as substitutions so the two sheets cannot
#: drift into differing anywhere else.
_HOLES = {
    'd="M 80,0 L 168,-44"': 'd="M 80,0 L 116.845,-18.422 M 131.155,-25.578 L 168,-44"',
    'd="M 256,0 C 270,-30 290,-60 300,-90 C 260,-105 200,-120 168,-44"': (
        'd="M 256,0 C 270,-30 290,-60 300,-90 C 280,-99 260,-92 241.554,-69.633'
        ' M 226.446,-64.367 C 210,-58 190,-51 168,-44"'
    ),
    '  </g>\n  <rect x="0"': (
        '    <path class="hop" d="M 116.845 -18.422 A 8.000 8.000 0 0 1 131.155 -25.578" fill="none" />\n'
        '    <path class="hop" d="M 241.554 -69.633 A 8.000 8.000 0 0 1 226.446 -64.367" fill="none" />\n'
        '  </g>\n  <rect x="0"'
    ),
}


def _punch_holes(sheet: str) -> str:
    """``sheet`` with each stroke broken where a hop crosses it.

    A substitution that matched nothing would leave a sheet with no holes in
    it, which every test below would then pass against while exercising none of
    what it is for — so each one is required to hit.
    """
    for intact, gapped in _HOLES.items():
        assert intact in sheet, f"the hand-built sheet no longer carries {intact!r}"
        sheet = sheet.replace(intact, gapped)
    return sheet


def test_a_hop_crossing_a_stroke_moves_no_figure_but_the_glyph_count(tmp_path: Path) -> None:
    """The load-bearing claim: the subpaths of one ``path`` are one stroke.

    Punching a hole changes what the sheet says about the drawing in exactly
    one way — there is a hop there now. It changes nothing about how many
    edges there are, where they are routed, or how far they run, because a
    hole is an absence of ink and not a property of the graph. Reading the
    two sheets and differencing them states that without writing a single
    figure down twice.
    """
    intact = tmp_path / "intact.svg"
    intact.write_text(_HAND_BUILT, encoding="utf-8")
    gapped = tmp_path / "gapped.svg"
    gapped.write_text(_punch_holes(_HAND_BUILT), encoding="utf-8")

    before = measure_sheet.measure(intact)
    after = measure_sheet.measure(gapped)

    assert after["hop_glyphs"] == before["hop_glyphs"] + 2
    moved = {column for column in measure_sheet.COLUMNS if before[column] != after[column]}
    assert moved == {"bytes", "hop_glyphs"}, "a hole in a stroke moved a figure the graph decides"


def test_a_stroke_ending_inside_a_hole_is_measured_where_the_pen_stopped(tmp_path: Path) -> None:
    """The one place a fraction reaches a figure instead of being spliced out.

    A hole over a stroke's own end leaves a foot with nothing to splice to, so
    that coordinate is the endpoint. Truncating it is a silent shortening of
    ``edge_len`` — the figure stays plausible — and ``int()`` did exactly that
    to every coordinate until it met one it could not parse at all.
    """
    sheet = tmp_path / "clipped.svg"
    sheet.write_text(_HAND_BUILT.replace('d="M 80,0 L 168,-44"', 'd="M 80,0 L 156.9,-44"'), encoding="utf-8")

    # The intact sheet's 264 less this stroke's full 88-wide run, plus the
    # 76.9 it now stops at: 252.9, which truncation would report as 252.
    assert measure_sheet.measure(sheet)["edge_len"] == 253


def test_boxes_of_more_than_one_size_are_reported_rather_than_averaged_away(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A finding the instrument could not make while it took the box width on trust."""
    sheet = tmp_path / "ragged.svg"
    sheet.write_text(
        _HAND_BUILT.replace('<rect x="88" y="-136" width="160"', '<rect x="88" y="-136" width="240"'), encoding="utf-8"
    )

    with caplog.at_level(logging.ERROR):
        figures = measure_sheet.measure(sheet)

    assert "not one width" in caplog.text
    assert figures["box_w"] == 160, "the commonest size, so one rogue box moves no other figure"


# ---------------------------------------------------------------------------
# A real sheet, against the census the run that drew it printed
# ---------------------------------------------------------------------------

#: The `FACT` lines read here, and each one's headline number — the first
#: integer after its name. `FACT layers` is not among them: a layer is a ring
#: index under the arrangement that ships and stands at a radius rather than on
#: a row, so nothing on the drawing states it without reconstructing the
#: placer's geometry.
_CENSUS_FIGURES = ("nodes", "edges", "crossings")

_FACT = re.compile(rf"FACT ({'|'.join(_CENSUS_FIGURES)})\s+(\d+)")

#: What the census calls a figure, against what this instrument calls it, for
#: the figures that are one quantity counted twice. `FACT crossings` is not one
#: of them: it is the crossings the geometry has, while the drawing carries a
#: glyph only where one could be fitted, so what the two support is the bound
#: below and never an equality.
_CENSUS_TO_COLUMN = {"nodes": "boxes", "edges": "strokes"}


def _staged_kb_roots() -> list[Path]:
    return sorted(_STAGED.glob("*/kb-root")) if _STAGED.is_dir() else []


def _render(kb_root: Path, *, into: Path) -> tuple[dict[str, int], Path]:
    """Draw one staged KB's sheet through the shipped op, and its census.

    The KB is copied out because the op resolves its repository from the
    working directory and writes the sheet beside the tree it read — staged
    data is read, never written.
    """
    shutil.copytree(kb_root, into / "kb-root")
    subprocess.run(["git", "init", "-q", "."], cwd=into, check=True)
    finished = subprocess.run(
        [sys.executable, "-m", "kb_tools.kb_util", "render-claim-graph"],
        cwd=into,
        env={**os.environ, "PYTHONPATH": str(_REPO_ROOT)},
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert finished.returncode == 0, finished.stderr
    census = {name: int(value) for name, value in _FACT.findall(finished.stdout + finished.stderr)}
    assert set(census) == set(_CENSUS_FIGURES), f"the census changed shape: {finished.stderr}"
    return census, into / "kb-root" / "claim-graph.svg"


def test_the_drawing_and_the_census_of_the_run_that_drew_it_agree(tmp_path: Path) -> None:
    """The cross-check that shares no code with the renderer.

    Every staged KB is measured, because a sheet's shape is a property of its
    KB and the one that would have caught the ``polyline`` breakage is a sheet
    with strokes on it — so at least one has to be found, or there is nothing
    here to check.

    The glyphs are checked against the census's crossing count as the bound they
    are: a marked crossing is a crossing, so a sheet carrying more glyphs than
    the run found crossings is the instrument counting something else as one.
    """
    kb_roots = _staged_kb_roots()
    if not kb_roots:
        pytest.skip("no corpus staged")

    drawn = 0
    for kb_root in kb_roots:
        census, sheet = _render(kb_root, into=tmp_path / kb_root.parent.name)
        figures = measure_sheet.measure(sheet)
        measured = {name: figures[column] for name, column in _CENSUS_TO_COLUMN.items()}
        assert measured == {
            name: census[name] for name in _CENSUS_TO_COLUMN
        }, f"{kb_root.parent.name}: the sheet and its own census disagree"
        assert figures["hop_glyphs"] <= census["crossings"], (
            f"{kb_root.parent.name}: {figures['hop_glyphs']} glyphs on a sheet whose own run "
            f"reported {census['crossings']} crossings"
        )
        drawn += census["edges"]

    assert drawn > 0, "no staged KB drew a stroke, so nothing here exercised the stroke count"
