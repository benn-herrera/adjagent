"""The claim-graph sheets: composition against its goldens, and the properties the goldens cannot name.

Nothing here runs Graphviz. Composition needs no binary; a drawn sheet is
``dot.to_svg`` answered in-process; and the suite's own state — the binary
pointed away by ``conftest.py`` — is the absent-``dot`` case.
"""

import dataclasses
import html
import re
import shutil
from pathlib import Path
from xml.etree import ElementTree

import pytest

from kb_tools import claim_sheet, dot, kb_index_lib, kb_load, kb_pipeline, kb_schema, refresh_kb_metadata
from kb_tools.tests._in_process import run_main
from kb_tools.tests._stamped_kb import write_index, write_stamped_kb

#: The repository the fixture stands for: ``kb-root/`` and the unmarked build record beside it.
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "claim-graph-sheet"
KB = FIXTURE / "kb-root"

@pytest.fixture(scope="module")
def sheet() -> claim_sheet.SheetInput:
    return claim_sheet.load(KB)


@pytest.fixture(scope="module")
def sheet_dot(sheet: claim_sheet.SheetInput) -> str:
    return claim_sheet.compose_sheet(sheet)


def _copy_repo(tmp_path: Path) -> Path:
    """A writable copy of the fixture repository; returns its ``kb-root/``."""
    shutil.copytree(FIXTURE, tmp_path / "repo")
    return tmp_path / "repo" / "kb-root"


@pytest.mark.parametrize(
    ("compose", "golden"),
    [
        (claim_sheet.compose_sheet, "claim-graph.dot"),
        (claim_sheet.compose_digest, "claim-graph-digest.dot"),
        (lambda loaded: claim_sheet.compose_volume_sheet(loaded, "alpha"), "alpha-claim-graph.dot"),
    ],
    ids=["sheet", "digest", "alpha-volume"],
)
def test_composition_matches_its_golden(sheet: claim_sheet.SheetInput, compose, golden: str) -> None:
    assert compose(sheet) == (FIXTURE / golden).read_text(encoding="utf-8")


def test_the_fixture_index_streams_hold_only_records() -> None:
    for name in kb_index_lib.INDEX_FILES:
        assert kb_load.read_index(KB, name)[1] == [], name


def test_record_order_does_not_reach_the_text(tmp_path: Path, sheet: claim_sheet.SheetInput) -> None:
    kb = _copy_repo(tmp_path)
    for name in ("claims", "depends-on", "cites"):
        path = kb_load.index_path(kb, name)
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text("\n".join(reversed(lines)) + "\n", encoding="utf-8")

    reloaded = claim_sheet.load(kb)

    assert claim_sheet.compose_sheet(reloaded) == claim_sheet.compose_sheet(sheet)
    assert claim_sheet.compose_digest(reloaded) == claim_sheet.compose_digest(sheet)
    assert claim_sheet.compose_volume_sheet(reloaded, "beta") == claim_sheet.compose_volume_sheet(sheet, "beta")


@pytest.mark.parametrize(
    ("text", "plain", "markup"),
    [
        ("a\\b", '"a\\\\b"', "a\\b"),
        ('say "x"', '"say \\"x\\""', "say &quot;x&quot;"),
        ("\\nabla", '"\\\\nabla"', "\\nabla"),
    ],
    ids=["backslash", "quote", "backslash-n"],
)
def test_each_escaper_escapes_only_its_own_syntax(text: str, plain: str, markup: str) -> None:
    assert claim_sheet._q(text) == plain
    assert claim_sheet._h(text) == markup


def test_a_multi_line_plain_string_breaks_after_escaping() -> None:
    assert claim_sheet._q("a\\", "b") == '"a\\\\\\nb"'


def _as_graphviz_reads_an_html_tooltip(value: str) -> str:
    """An HTML-like label's ``tooltip`` value as Graphviz shows it: entities decoded, then its escString
    pass, where a doubled backslash is one and any other escape expands — marked here so it cannot pass."""
    return re.sub(
        r"\\(.)",
        lambda match: "\\" if match.group(1) == "\\" else f"<expanded \\{match.group(1)}>",
        html.unescape(value),
    )


def test_a_tooltip_reaches_graphviz_as_the_whole_title(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sheet_dot: str
) -> None:
    """``clm-aaa005``'s title holds ``\\Gamma``, whose ``\\G`` Graphviz would otherwise read as the graph name."""
    title = next(record["title"] for record in kb_load.read_index(KB, "claims")[0] if record["id"] == "clm-aaa005")
    drawn: list[str] = []
    monkeypatch.setattr(dot, "to_svg", lambda text: drawn.append(text) or _DRAWN)
    claim_sheet.render(_copy_repo(tmp_path))

    assert "\\Gamma" in title
    for composed in (sheet_dot, drawn[0]):
        tooltip = re.search(r'tooltip="(clm-aaa005 [^"]*)"', composed)
        assert tooltip is not None
        assert _as_graphviz_reads_an_html_tooltip(tooltip.group(1)).endswith(f"] {title}")


# ---------------------------------------------------------------------------
# Transitive reduction
# ---------------------------------------------------------------------------


def _depends(*pairs: str) -> list[claim_sheet.SheetEdge]:
    return [claim_sheet.SheetEdge(*pair.split(">"), "depends", claim_sheet.CITED) for pair in pairs]


def _reach(edges: list[claim_sheet.SheetEdge]) -> set[tuple[str, str]]:
    closure = {(edge.source, edge.target) for edge in edges}
    while True:
        grown = closure | {(a, d) for a, b in closure for c, d in closure if b == c}
        if grown == closure:
            return closure
        closure = grown


@pytest.mark.parametrize(
    "pairs",
    [("a>b", "b>c", "a>c"), ("a>b", "b>a", "a>c", "b>c"), ("a>b", "b>c", "c>a", "a>c"), ("a>b", "c>d")],
    ids=["triangle", "two-cycle", "three-cycle", "disjoint"],
)
def test_reduction_never_loses_reachability(pairs: tuple[str, ...]) -> None:
    edges = _depends(*pairs)

    assert _reach(claim_sheet._reduced(edges)) == _reach(edges)


@pytest.mark.parametrize(
    "other",
    [claim_sheet.SheetEdge("a", "c", "rests-on", None), claim_sheet.SheetEdge("a", "b", "rests-on", None)],
    ids=["not-dropped-as-a-shortcut", "not-read-as-a-route"],
)
def test_reduction_reads_and_drops_depends_alone(other: claim_sheet.SheetEdge) -> None:
    """A ``rests-on`` a→c survives beside the route a→b→c; a ``rests-on`` a→b makes no route of a→b→c."""
    edges = [*_depends("a>c", "b>c"), other] if other.target == "b" else [*_depends("a>b", "b>c"), other]

    assert set(claim_sheet._reduced(edges)) == set(edges)


# ---------------------------------------------------------------------------
# Provenance: the unmarked record for depends, the row's origin for a cut
# ---------------------------------------------------------------------------


def test_a_demoted_row_without_a_valid_origin_draws_as_cited(tmp_path: Path) -> None:
    kb = _copy_repo(tmp_path)
    path = kb_load.index_path(kb, "depends-on")
    path.write_text(
        path.read_text(encoding="utf-8").replace('"origin": "inferred"', '"origin": null'), encoding="utf-8"
    )

    by_pair = {(edge.source, edge.target): edge for edge in claim_sheet.load(kb).edges}

    assert by_pair[("clm-aaa001", "clm-aaa004")].provenance == claim_sheet.CITED


def test_without_the_unmarked_record_every_depends_is_cited(tmp_path: Path) -> None:
    kb = _copy_repo(tmp_path)
    (kb.parent / kb_pipeline.UNMARKED_RELPATH).unlink()

    loaded = claim_sheet.load(kb)

    assert {edge.provenance for edge in loaded.edges if edge.relation == "depends"} == {claim_sheet.CITED}


def test_an_unreadable_unmarked_record_fails_the_render(tmp_path: Path) -> None:
    kb = _copy_repo(tmp_path)
    (kb.parent / kb_pipeline.UNMARKED_RELPATH).write_text("{ not yaml", encoding="utf-8")

    outcome = claim_sheet.render(kb)

    assert outcome.failed
    assert len(outcome.lines) == 1 and outcome.lines[0].startswith("FAIL: [refresh-sheet] ")
    assert kb_pipeline.UNMARKED_RELPATH in outcome.lines[0]


def test_a_record_beside_a_kb_not_named_kb_root_fails_refresh_with_a_line_not_a_traceback(tmp_path: Path) -> None:
    """Records are read against ``<repository>/kb-root``; a copy named otherwise has none to read them for."""
    kb = _copy_repo(tmp_path)
    renamed = kb.rename(kb.parent / "copied-kb")

    result = run_main(refresh_kb_metadata.main, ["--kb-root", str(renamed)])

    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    assert [line for line in result.stderr.splitlines() if line.startswith("FAIL: ")] == [
        f"FAIL: [refresh-sheet] the build records beside {renamed} are not read for it: "
        f"kb-root: {renamed.parent / 'kb-root' / 'entry-point.md'}: {renamed.parent / 'kb-root'} has no entry-point.md"
    ]


def test_the_classification_record_is_not_read(tmp_path: Path, sheet: claim_sheet.SheetInput) -> None:
    kb = _copy_repo(tmp_path)
    (kb.parent / kb_pipeline.CLASSIFICATION_RELPATH).write_text("{ not yaml", encoding="utf-8")

    loaded = claim_sheet.load(kb)

    assert not claim_sheet.render(kb).failed
    assert claim_sheet.compose_sheet(loaded) == claim_sheet.compose_sheet(sheet)


# ---------------------------------------------------------------------------
# What each sheet holds and links to
# ---------------------------------------------------------------------------


def test_the_legend_names_only_what_the_sheet_draws(sheet: claim_sheet.SheetInput, sheet_dot: str) -> None:
    variant = dataclasses.replace(
        sheet,
        nodes=tuple(node for node in sheet.nodes if node.kind != "work"),
        edges=tuple(edge for edge in sheet.edges if edge.relation != "rests-on"),
    )
    legend = next(
        line for line in claim_sheet.compose_sheet(variant).splitlines() if line.lstrip().startswith("legend")
    )
    full = next(line for line in sheet_dot.splitlines() if line.lstrip().startswith("legend"))

    assert ">work</td>" in full and ">rests-on — " in full
    assert ">work</td>" not in legend and ">rests-on — " not in legend
    # Bands carried only by unattached claims are listed in a table, not drawn.
    assert "refuted, do not use" not in full


def test_an_empty_index_composes_no_clusters_and_no_legend(tmp_path: Path) -> None:
    kb = write_stamped_kb(tmp_path / "kb-root", {"entry-point.md": ""})
    for name in kb_index_lib.INDEX_FILES:
        write_index(kb, name, [])

    empty = claim_sheet.load(kb)

    for composed in (claim_sheet.compose_sheet(empty), claim_sheet.compose_digest(empty)):
        assert "subgraph" not in composed and "legend" not in composed and "->" not in composed
    assert empty.kb_title == "kb-root"


def test_a_relation_without_a_style_is_refused() -> None:
    with pytest.raises(ValueError, match="handles no \\['spawns'\\]"):
        claim_sheet._require_total(
            claim_sheet._EDGE_STYLES, (*kb_schema.EDGE_RELATIONS, "spawns"), what="claim-sheet edge styles"
        )


def test_fit_leaves_an_svg_without_a_fixed_size_as_it_came() -> None:
    assert claim_sheet.fit('<svg width="10pt" height="20pt" viewBox="0 0 10 20">') == (
        '<svg width="100%" viewBox="0 0 10 20">'
    )
    assert claim_sheet.fit('<svg viewBox="0 0 10 20">') == '<svg viewBox="0 0 10 20">'


# ---------------------------------------------------------------------------
# Rendering, with the seam answered in-process
# ---------------------------------------------------------------------------

_DRAWN = '<svg width="120pt" height="80pt" viewBox="0.00 0.00 120.00 80.00">drawn</svg>\n'
_FITTED = '<svg width="100%" viewBox="0.00 0.00 120.00 80.00">drawn</svg>\n'
_SHEETS = (
    claim_sheet.SHEET_FILENAME,
    claim_sheet.DIGEST_FILENAME,
    f"alpha/{claim_sheet.SHEET_FILENAME}",
    f"beta/{claim_sheet.SHEET_FILENAME}",
)
_MARKER_NOTE = "[refresh-sheet] NOTE 4 claims without a readable marker; kind read from the title."


def test_render_writes_every_sheet_fitted_and_then_leaves_them_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    kb = _copy_repo(tmp_path)
    drawn: list[str] = []
    monkeypatch.setattr(dot, "to_svg", lambda text: drawn.append(text) or _DRAWN)

    first = claim_sheet.render(kb)
    stamps = {name: (kb / name).stat().st_mtime_ns for name in _SHEETS}
    second = claim_sheet.render(kb)

    loaded = claim_sheet.load(kb)
    assert drawn[:2] == [claim_sheet.compose_sheet(loaded), claim_sheet.compose_digest(loaded)]
    assert not first.failed and not second.failed
    assert first.lines == (
        "[refresh-sheet] Wrote claim-graph.svg: 14 nodes, 11 edges drawn of 12, 2 unattached, 1 ghost id.",
        "[refresh-sheet] Wrote claim-graph-digest.svg: 3 volumes, 4 bundles.",
        "[refresh-sheet] Wrote alpha/claim-graph.svg: 8 nodes, 2 neighbours, 8 edges drawn.",
        "[refresh-sheet] Wrote beta/claim-graph.svg: 3 nodes, 5 neighbours, 5 edges drawn.",
        _MARKER_NOTE,
    )
    assert second.lines == tuple(line.replace("Wrote", "Unchanged") for line in first.lines)
    assert all((kb / name).read_text(encoding="utf-8") == _FITTED for name in _SHEETS)
    assert stamps == {name: (kb / name).stat().st_mtime_ns for name in _SHEETS}


def _drop_beta_nodes(kb: Path) -> None:
    claims = kb_load.index_path(kb, "claims")
    kept = [line for line in claims.read_text(encoding="utf-8").splitlines() if '"beta/' not in line]
    claims.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _one_volume_repo(tmp_path: Path) -> Path:
    """The fixture with beta gone: alpha alone holds nodes beside the KB-root bucket."""
    kb = _copy_repo(tmp_path)
    _drop_beta_nodes(kb)
    shutil.rmtree(kb / "beta")
    return kb


@pytest.mark.parametrize("drawing", [True, False], ids=["drawn", "without-dot"])
def test_a_kb_shrinking_to_one_volume_loses_every_sheet_but_the_root_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, drawing: bool
) -> None:
    kb = _copy_repo(tmp_path)
    absent_dot = dot.to_svg
    monkeypatch.setattr(dot, "to_svg", lambda _text: _DRAWN)
    claim_sheet.render(kb)
    _drop_beta_nodes(kb)
    if not drawing:
        monkeypatch.setattr(dot, "to_svg", absent_dot)

    outcome = claim_sheet.render(kb)

    assert not outcome.failed
    assert [line for line in outcome.lines if " Removed " in line] == [
        f"[refresh-sheet] Removed {name}: no longer called for." for name in _SHEETS[1:]
    ]
    assert sorted(path.relative_to(kb).as_posix() for path in kb.rglob("*.svg")) == [claim_sheet.SHEET_FILENAME]


def test_one_volume_draws_what_the_volume_rule_calls_for(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    kb = _one_volume_repo(tmp_path)
    monkeypatch.setattr(dot, "to_svg", lambda _text: _DRAWN)

    outcome = claim_sheet.render(kb)

    assert not outcome.failed
    written = tuple(line.split(" ")[2].rstrip(":") for line in outcome.lines if " Wrote " in line)
    assert written == (claim_sheet.SHEET_FILENAME,)
    assert not claim_sheet.multi_volume(claim_sheet.load(kb))


def test_a_drawn_sheet_replaces_a_placeholder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    kb = _copy_repo(tmp_path)
    claim_sheet.render(kb)
    monkeypatch.setattr(dot, "to_svg", lambda _text: _DRAWN)

    outcome = claim_sheet.render(kb)

    assert [line.split(" ")[1] for line in outcome.lines[:-1]] == ["Wrote"] * len(_SHEETS)
    assert all((kb / name).read_text(encoding="utf-8") == _FITTED for name in _SHEETS)


def test_a_refused_graph_fails_and_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The second sheet is refused, so a sheet written as soon as it was drawn would be left behind."""
    kb = _copy_repo(tmp_path)
    calls: list[str] = []

    def refuse_the_second(text: str) -> str:
        calls.append(text)
        if len(calls) == 2:
            raise dot.DotError("`dot -Tsvg` exited 1: Error: <stdin>: syntax error in line 1")
        return _DRAWN

    monkeypatch.setattr(dot, "to_svg", refuse_the_second)

    outcome = claim_sheet.render(kb)

    assert outcome.failed
    assert outcome.lines == (
        "FAIL: [refresh-sheet] drawing claim-graph-digest.svg: "
        "`dot -Tsvg` exited 1: Error: <stdin>: syntax error in line 1",
    )
    assert not any((kb / name).exists() for name in _SHEETS)


# ---------------------------------------------------------------------------
# Without `dot`: the suite's own state (conftest points the binary away)
# ---------------------------------------------------------------------------

_NOTE_LINE = (
    "[refresh-sheet] NOTE Graphviz `kb-tools-tests-run-without-graphviz` is not on PATH. This toolchain draws the "
    "claim-graph sheets by invoking it and does not install or vendor it — install Graphviz "
    "(https://graphviz.org/download/) and re-run."
)


def test_the_placeholder_is_a_small_svg_naming_graphviz_and_its_install_page() -> None:
    root = ElementTree.fromstring(claim_sheet.PLACEHOLDER_SVG)
    text = " ".join(element.text or "" for element in root.iter("{http://www.w3.org/2000/svg}text"))

    assert len(claim_sheet.PLACEHOLDER_SVG.encode("utf-8")) < 1024
    assert root.get("width") == "100%" and root.get("viewBox") and root.get("height") is None
    assert "Graphviz dot" in text and "https://graphviz.org/download/" in text


def test_without_dot_every_absent_sheet_becomes_a_placeholder(tmp_path: Path) -> None:
    kb = _copy_repo(tmp_path)

    outcome = claim_sheet.render(kb)

    assert not outcome.failed
    assert outcome.lines == (*(f"[refresh-sheet] Placeholder {name}." for name in _SHEETS), _NOTE_LINE, _MARKER_NOTE)
    assert all((kb / name).read_text(encoding="utf-8") == claim_sheet.PLACEHOLDER_SVG for name in _SHEETS)


def test_without_dot_an_existing_sheet_is_kept(tmp_path: Path) -> None:
    kb = _copy_repo(tmp_path)
    (kb / claim_sheet.SHEET_FILENAME).write_text(_FITTED, encoding="utf-8")

    outcome = claim_sheet.render(kb)

    assert not outcome.failed
    assert outcome.lines[:2] == (
        "[refresh-sheet] Kept claim-graph.svg.",
        "[refresh-sheet] Placeholder claim-graph-digest.svg.",
    )
    assert (kb / claim_sheet.SHEET_FILENAME).read_text(encoding="utf-8") == _FITTED
    assert (kb / claim_sheet.DIGEST_FILENAME).read_text(encoding="utf-8") == claim_sheet.PLACEHOLDER_SVG


def test_without_dot_refresh_completes(tmp_path: Path) -> None:
    kb = tmp_path / "kb-root"
    shutil.copytree(Path(__file__).resolve().parent / "fixtures" / "mini-kb", kb)

    result = run_main(refresh_kb_metadata.main, ["--kb-root", str(kb)])

    assert result.returncode == 0, result.stderr
    assert _NOTE_LINE in result.stdout.splitlines()
    assert kb_load.index_path(kb, "claims").is_file()
    assert (kb / claim_sheet.SHEET_FILENAME).read_text(encoding="utf-8") == claim_sheet.PLACEHOLDER_SVG
