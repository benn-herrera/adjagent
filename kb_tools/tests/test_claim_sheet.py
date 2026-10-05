"""The claim-graph sheets: composition against its goldens, and the properties the goldens cannot name.

Nothing here runs Graphviz. Composition needs no binary; a drawn sheet is
``dot.to_svg`` answered in-process; and the suite's own state — the binary
pointed away by ``conftest.py`` — is the absent-``dot`` case.
"""

import dataclasses
import re
import shutil
from pathlib import Path
from xml.etree import ElementTree

import pytest

from kb_tools import claim_sheet, dot, kb_pipeline, kb_schema, refresh_kb_metadata
from kb_tools.kb_cmd import index as kb_index
from kb_tools.tests._in_process import run_main

#: The repository the fixture stands for: ``kb-root/`` and the two build records beside it.
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "claim-graph-sheet"
KB = FIXTURE / "kb-root"

#: A drawn node's statement; the unattached tables, the legend and the sheet link are ``plaintext``.
_NODE_STATEMENT = re.compile(r'^\s+"((?:[^"\\]|\\.)+)" \[shape=(?!plaintext)', re.MULTILINE)
_EDGE_STATEMENT = re.compile(r'^\s+"((?:[^"\\]|\\.)+)" -> "((?:[^"\\]|\\.)+)" \[(.*)\]$', re.MULTILINE)


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


def _drawn_edges(composed: str) -> dict[tuple[str, str], str]:
    return {(tail, head): attributes for tail, head, attributes in _EDGE_STATEMENT.findall(composed)}


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
    composed = compose(sheet)

    assert composed == (FIXTURE / golden).read_text(encoding="utf-8")
    assert compose(claim_sheet.load(KB)) == composed


def test_record_order_does_not_reach_the_text(tmp_path: Path, sheet: claim_sheet.SheetInput) -> None:
    kb = _copy_repo(tmp_path)
    for name in ("claims.jsonl", "depends-on.jsonl", "cites.jsonl"):
        path = kb / ".index" / name
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
        ("a < b", '"a < b"', "a &lt; b"),
        ("a & b", '"a & b"', "a &amp; b"),
        ("\\nabla", '"\\\\nabla"', "\\nabla"),
    ],
    ids=["backslash", "quote", "less-than", "ampersand", "backslash-n"],
)
def test_each_escaper_escapes_only_its_own_syntax(text: str, plain: str, markup: str) -> None:
    assert claim_sheet._q(text) == plain
    assert claim_sheet._h(text) == markup


def test_a_multi_line_plain_string_breaks_after_escaping() -> None:
    assert claim_sheet._q("a\\", "b") == '"a\\\\\\nb"'


def test_maths_and_markup_titles_reach_the_text_escaped_once(sheet_dot: str) -> None:
    nabla = next(line for line in sheet_dot.splitlines() if line.lstrip().startswith('"clm-aaa003" ['))
    beta = next(line for line in sheet_dot.splitlines() if "Beta" in line)

    assert "\\\\nabla" in nabla
    assert "&amp;" in beta and "&quot;" in beta and "&lt;" in beta
    assert "&amp;amp;" not in sheet_dot


def test_every_connected_node_is_drawn_once_and_every_unattached_one_is_listed(
    sheet: claim_sheet.SheetInput, sheet_dot: str
) -> None:
    ends = {end for edge in sheet.edges for end in (edge.source, edge.target)}
    statements = _NODE_STATEMENT.findall(sheet_dot)
    unattached = sorted(node.id for node in sheet.nodes if node.id not in ends)

    assert sorted(statements) == sorted(ends)
    assert unattached == ["clm-aaa005", "clm-aaa006"]
    for node_id in unattached:
        assert f">{node_id} — " in sheet_dot
        assert node_id not in statements


def test_edges_place_the_premise_at_the_head(sheet: claim_sheet.SheetInput, sheet_dot: str) -> None:
    drawn = _drawn_edges(sheet_dot)
    expected = claim_sheet._reduced(sheet.edges)

    assert len(drawn) == len(expected)
    for edge in expected:
        if edge.relation in ("supports", "strengthens"):
            attributes = drawn[(edge.target, edge.source)]
            assert "dir=back" in attributes
        else:
            attributes = drawn[(edge.source, edge.target)]
            assert "dir=back" not in attributes
        assert ("constraint=false" in attributes) is (edge.provenance == claim_sheet.CUT)


def test_duplicate_records_are_one_stroke_and_a_missing_end_is_a_ghost(sheet: claim_sheet.SheetInput) -> None:
    assert sum(1 for edge in sheet.edges if (edge.source, edge.target) == ("clm-aaa001", "clm-aaa002")) == 1
    assert [node.id for node in sheet.nodes if node.kind == claim_sheet.GHOST_KIND] == ["clm-zzz999"]


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


def test_a_premise_another_route_reaches_is_not_drawn(sheet: claim_sheet.SheetInput) -> None:
    """The fixture triangle: aaa003 rests on aaa002 directly and through aaa001."""
    assert ("clm-aaa003", "clm-aaa002") in {(edge.source, edge.target) for edge in sheet.edges}
    for composed in (claim_sheet.compose_sheet(sheet), claim_sheet.compose_volume_sheet(sheet, "alpha")):
        drawn = _drawn_edges(composed)
        assert ("clm-aaa003", "clm-aaa002") not in drawn
        assert ("clm-aaa003", "clm-aaa001") in drawn and ("clm-aaa001", "clm-aaa002") in drawn


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
# Provenance, from the build records
# ---------------------------------------------------------------------------


def test_each_edge_carries_its_provenance(sheet: claim_sheet.SheetInput) -> None:
    by_pair = {(edge.source, edge.target): edge for edge in sheet.edges}

    assert by_pair[("clm-aaa003", "clm-aaa001")].provenance == claim_sheet.INFERRED
    assert by_pair[("clm-bbb001", "clm-aaa001")].provenance == claim_sheet.CITED  # answered "does not point"
    assert by_pair[("clm-aaa004", "clm-bbb003")].provenance == claim_sheet.CUT
    assert ("clm-bbb003", "clm-aaa004") not in by_pair  # a references row classify did not choose depends for


def test_the_sheets_name_provenance_in_reader_words_only(sheet: claim_sheet.SheetInput, sheet_dot: str) -> None:
    composed = [sheet_dot, claim_sheet.compose_digest(sheet), claim_sheet.compose_volume_sheet(sheet, "alpha")]

    assert "(depends, inferred)" in sheet_dot and "(depends, cited)" in sheet_dot and "(references, cut)" in sheet_dot
    assert "1 cited · 1 inferred" in composed[1] or "2 cited · 1 inferred" in composed[1]
    for text in composed:
        assert not re.search(r"\b(ask|asked|unmarked|demoted)\b", text)


def test_without_build_records_every_depends_is_cited_and_no_references_drawn(tmp_path: Path) -> None:
    kb = _copy_repo(tmp_path)
    for name in (kb_pipeline.UNMARKED_RELPATH, kb_pipeline.CLASSIFICATION_RELPATH):
        (kb.parent / name).unlink()

    loaded = claim_sheet.load(kb)

    assert {edge.provenance for edge in loaded.edges if edge.relation == "depends"} == {claim_sheet.CITED}
    assert not [edge for edge in loaded.edges if edge.relation == "references"]


def test_an_unreadable_build_record_fails_the_render(tmp_path: Path) -> None:
    kb = _copy_repo(tmp_path)
    (kb.parent / kb_pipeline.CLASSIFICATION_RELPATH).write_text("{ not json", encoding="utf-8")

    outcome = claim_sheet.render(kb)

    assert outcome.failed
    assert len(outcome.lines) == 1 and outcome.lines[0].startswith("FAIL: [refresh-sheet] ")
    assert kb_pipeline.CLASSIFICATION_RELPATH in outcome.lines[0]


def test_the_copied_letters_are_the_claim_graphs_own() -> None:
    from kb_tools.kb_claimgraph import ask, attribute, classify

    assert claim_sheet.UNMARKED_POINTS_LETTER == ask.UnmarkedLetter.POINTS
    assert claim_sheet.CLASSIFY_DEPENDS_LETTER == ask.ClassifyLetter.SUPPORTED_BY
    assert classify.LETTER_RELATION[ask.ClassifyLetter.SUPPORTED_BY] is attribute.Relation.SUPPORTED_BY


# ---------------------------------------------------------------------------
# Node kind, from the claim's marker in its leaf
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("node_id", "kind"),
    [
        ("clm-aaa001", "block"),  # marker in a labelled blockquote
        ("clm-bbb002", "block"),  # on a block's content line, its label in a <span id>; its title reads as prose
        ("clm-aaa003", "equation"),  # marker inside a math fence; its title reads as prose
        ("clm-aaa004", "prose"),  # marker in a paragraph
        ("clm-aaa002", "equation"),  # no marker: the equation title
        ("clm-bbb001", "block"),  # no leaf: the printed-name title
        ("clm-bbb003", "prose"),  # its leaf cannot be read
        ("sup-aaa007", "support"),
        ("work-smith2020", "work"),
    ],
)
def test_claims_are_read_as_their_sub_kind(sheet: claim_sheet.SheetInput, node_id: str, kind: str) -> None:
    assert next(node.kind for node in sheet.nodes if node.id == node_id) == kind


def test_claims_read_from_the_title_are_counted(sheet: claim_sheet.SheetInput) -> None:
    assert sheet.claims_without_marker == 4  # the markerless equation is read by rule, not counted


# ---------------------------------------------------------------------------
# What each sheet holds and links to
# ---------------------------------------------------------------------------


def test_the_legend_names_only_what_the_sheet_draws(sheet: claim_sheet.SheetInput, sheet_dot: str) -> None:
    variant = dataclasses.replace(
        sheet,
        nodes=tuple(node for node in sheet.nodes if node.kind != "work"),
        edges=tuple(edge for edge in sheet.edges if edge.relation != "rests-on"),
    )
    legend = next(line for line in claim_sheet.compose_sheet(variant).splitlines() if line.lstrip().startswith("legend"))
    full = next(line for line in sheet_dot.splitlines() if line.lstrip().startswith("legend"))

    assert ">work</td>" in full and ">rests-on — " in full
    assert ">work</td>" not in legend and ">rests-on — " not in legend
    # Bands carried only by unattached claims are listed in a table, not drawn.
    assert "refuted, do not use" not in full


def test_a_volume_sheet_links_relative_to_its_own_directory(sheet: claim_sheet.SheetInput) -> None:
    alpha = claim_sheet.compose_volume_sheet(sheet, "alpha")

    assert 'href="claim-quality.md#theorem-1"' in alpha
    assert 'href="claim-quality.md#an-isolated-observation-nothing-cites"' in alpha
    assert 'href="../beta/claim-quality.md#test-example-2"' in alpha
    assert 'href="../invariants.md#invariant-s1"' in alpha
    assert "clm-bbb002" not in alpha  # a beta node no alpha edge touches


def test_the_root_sheets_link_to_each_other_and_the_digest_to_each_volume(sheet: claim_sheet.SheetInput) -> None:
    digest = claim_sheet.compose_digest(sheet)

    assert 'href="claim-graph-digest.svg"' in claim_sheet.compose_sheet(sheet)
    assert 'href="claim-graph.svg"' in digest
    assert 'href="alpha/index.md"' in digest and 'href="alpha/claim-graph.svg"' in digest


def test_an_empty_index_composes_no_clusters_and_no_legend(tmp_path: Path) -> None:
    kb = tmp_path / "kb-root"
    (kb / ".index").mkdir(parents=True)
    for name in kb_index._REQUIRED_FILES:
        (kb / ".index" / name).write_text("", encoding="utf-8")

    empty = claim_sheet.load(kb)

    for composed in (claim_sheet.compose_sheet(empty), claim_sheet.compose_digest(empty)):
        assert "subgraph" not in composed and "legend" not in composed and "->" not in composed
    assert empty.kb_title == "kb-root"


def test_style_tables_are_total_over_their_vocabularies() -> None:
    assert set(claim_sheet._EDGE_STYLES) == set(kb_schema.EDGE_RELATIONS)
    assert set(claim_sheet._BAND_FILLS) == {slug for slug, _ in kb_index.BUILD_BANDS}


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
        "[refresh-sheet] Wrote claim-graph.svg: 14 nodes, 10 edges drawn of 11, 2 unattached, 1 ghost id.",
        "[refresh-sheet] Wrote claim-graph-digest.svg: 3 volumes, 4 bundles.",
        "[refresh-sheet] Wrote alpha/claim-graph.svg: 8 nodes, 3 neighbours, 7 edges drawn.",
        "[refresh-sheet] Wrote beta/claim-graph.svg: 3 nodes, 5 neighbours, 5 edges drawn.",
        _MARKER_NOTE,
    )
    assert second.lines == tuple(line.replace("Wrote", "Unchanged") for line in first.lines)
    assert all((kb / name).read_text(encoding="utf-8") == _FITTED for name in _SHEETS)
    assert stamps == {name: (kb / name).stat().st_mtime_ns for name in _SHEETS}


def _one_volume_repo(tmp_path: Path) -> Path:
    """The fixture with beta gone: alpha alone holds nodes beside the KB-root bucket."""
    kb = _copy_repo(tmp_path)
    claims = kb / ".index" / "claims.jsonl"
    kept = [line for line in claims.read_text(encoding="utf-8").splitlines() if '"beta/' not in line]
    claims.write_text("\n".join(kept) + "\n", encoding="utf-8")
    shutil.rmtree(kb / "beta")
    return kb


@pytest.mark.parametrize(
    ("rule", "expected"),
    [
        ("two-or-more volumes", (claim_sheet.SHEET_FILENAME,)),
        ("always", (claim_sheet.SHEET_FILENAME, claim_sheet.DIGEST_FILENAME, f"alpha/{claim_sheet.SHEET_FILENAME}")),
    ],
)
def test_one_volume_draws_what_the_volume_rule_calls_for(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rule: str, expected: tuple[str, ...]
) -> None:
    """The live rule is two-or-more; ``always`` is the one-line alternative, kept covered."""
    kb = _one_volume_repo(tmp_path)
    monkeypatch.setattr(dot, "to_svg", lambda _text: _DRAWN)
    if rule == "always":
        monkeypatch.setattr(claim_sheet, "multi_volume", lambda _sheet: True)

    outcome = claim_sheet.render(kb)

    assert not outcome.failed
    written = tuple(line.split(" ")[2].rstrip(":") for line in outcome.lines if " Wrote " in line)
    assert written == expected
    assert claim_sheet.multi_volume(claim_sheet.load(kb)) is (rule == "always")


def test_two_volumes_draw_every_sheet(sheet: claim_sheet.SheetInput) -> None:
    assert claim_sheet.multi_volume(sheet)
    assert [name for name, _, _ in claim_sheet._sheets(sheet)] == list(_SHEETS)


def test_a_volume_holding_no_node_has_no_sheet_and_no_box(sheet: claim_sheet.SheetInput) -> None:
    """``gamma/`` has an ``index.md`` and no node."""
    assert (KB / "gamma" / "index.md").is_file()
    assert "gamma" not in {volume.key for volume in sheet.volumes}
    assert "Gamma Volume" not in claim_sheet.compose_digest(sheet)


def test_a_drawn_sheet_replaces_a_placeholder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    kb = _copy_repo(tmp_path)
    claim_sheet.render(kb)
    monkeypatch.setattr(dot, "to_svg", lambda _text: _DRAWN)

    outcome = claim_sheet.render(kb)

    assert [line.split(" ")[1] for line in outcome.lines[:-1]] == ["Wrote"] * len(_SHEETS)
    assert all((kb / name).read_text(encoding="utf-8") == _FITTED for name in _SHEETS)


def test_a_refused_graph_fails_and_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    kb = _copy_repo(tmp_path)

    def refuse(_text: str) -> str:
        raise dot.DotError("`dot -Tsvg` exited 1: Error: <stdin>: syntax error in line 1")

    monkeypatch.setattr(dot, "to_svg", refuse)

    outcome = claim_sheet.render(kb)

    assert outcome.failed
    assert outcome.lines == (
        "FAIL: [refresh-sheet] drawing claim-graph.svg: `dot -Tsvg` exited 1: Error: <stdin>: syntax error in line 1",
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
    kb = tmp_path / "mini-kb"
    shutil.copytree(Path(__file__).resolve().parent / "fixtures" / "mini-kb", kb)

    result = run_main(refresh_kb_metadata.main, ["--kb-root", str(kb)])

    assert result.returncode == 0, result.stderr
    assert _NOTE_LINE in result.stdout.splitlines()
    assert (kb / ".index" / "claims.jsonl").is_file()
    assert (kb / claim_sheet.SHEET_FILENAME).read_text(encoding="utf-8") == claim_sheet.PLACEHOLDER_SVG
