"""compare-to-pristine's found-not-authored extraction over in-test claim entries.

The script is loaded by path (its name is not a module name). The verdict file
is written under this repository's `.claude-temp/`; nothing under `test-data/`
is read.
"""

import importlib.util
import shutil
from pathlib import Path

import pytest

from kb_tools.kb_index_lib import ClaimEntry

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRATCH = _REPO_ROOT / ".claude-temp" / "compare-to-pristine-tests"


def _load():
    spec = importlib.util.spec_from_file_location("compare_to_pristine", _REPO_ROOT / "kb-testing" / "tools" / "compare-to-pristine.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


compare = _load()


@pytest.fixture(scope="module", autouse=True)
def _clean_scratch():
    shutil.rmtree(_SCRATCH, ignore_errors=True)
    _SCRATCH.mkdir(parents=True)
    yield
    shutil.rmtree(_SCRATCH, ignore_errors=True)


def _entry(claim_id: str, *, register: str, rationale: str) -> ClaimEntry:
    return ClaimEntry(
        id=claim_id,
        title=f"Title {claim_id}",
        canonical_path=register,
        canonical_anchor=f"anchor-{claim_id}",
        confidence=None,
        solidity=None,
        build_status=None,
        rationale=rationale,
        depends_on=(),
        strengthen_by=(),
    )


ENTRIES = {
    "a": _entry("a", register="p1/claim-quality.md", rationale="Identified in the prose of p1/s1/intro.md; the span is anchored."),
    "b": _entry("b", register="p1/claim-quality.md", rationale="Identified in the prose of p1/s1/intro.md; see also p1/other.md."),
    "c": _entry("c", register="p1/claim-quality.md", rationale="Stated by the author as a labelled Theorem block in p1/s2/main.md"),
    "d": _entry("d", register="p2/claim-quality.md", rationale="Neither dependency attribution nor rigor assessment has run."),
}


@pytest.mark.parametrize(
    ("claim_id", "leaf"),
    [
        ("a", "p1/s1/intro.md"),
        ("b", "p1/s1/intro.md"),  # the first path named, not a later one
        ("c", "p1/s2/main.md"),
        ("d", "p2/claim-quality.md"),  # no path named: the register
    ],
)
def test_hosting_leaf(claim_id: str, leaf: str) -> None:
    assert compare.hosting_leaf(ENTRIES[claim_id]) == leaf


def test_authored_pairs_cover_recalled_classes_only() -> None:
    mapped = {"r1": {"a", "b"}, "r2": {"c"}, "r3": {"d"}, "r4": {"a"}}
    rows = [
        ("r1", "", "r2", "", "depends"),
        ("r3", "", "r4", "", "depends path reversed"),
        ("r2", "", "r3", "", "nothing"),
    ]
    assert compare.authored_pairs(rows, mapped) == {("a", "c"), ("b", "c"), ("d", "a")}


def test_found_not_authored_excludes_authored_and_orders_rows() -> None:
    depends = {("a", "c"), ("c", "d"), ("a", "b"), ("d", "a")}
    rows = compare.found_not_authored(depends=depends, authored={("a", "c"), ("d", "a")}, entries=ENTRIES)
    assert [(row[0], row[5], row[10]) for row in rows] == [
        ("a", "b", "same document"),
        ("c", "d", "cross paper"),
    ]
    assert rows[1][1:5] == ("p1", "p1/s2/main.md", "anchor-c", "Title c")
    assert rows[1][6:10] == ("p2", "p2/claim-quality.md", "anchor-d", "Title d")


def test_locality_same_paper() -> None:
    assert compare.locality("p1/s1/intro.md", "p1/s2/main.md") == "same paper"


def test_verdict_join_keys_on_leaves_and_anchors() -> None:
    path = _SCRATCH / "verdicts.tsv"
    path.write_text(
        "citing_leaf\tciting_register_anchor\tcited_leaf\tcited_register_anchor\tverdict\tbasis\n"
        'p1/s1/intro.md\tanchor-a\tp1/s1/intro.md\tanchor-b\treject\t"quoted" basis\n'
        "p1/s2/main.md\tanchor-c\tp2/claim-quality.md\tanchor-d\treject\tfirst ruling\n"
        "p1/s2/main.md\tanchor-c\tp2/claim-quality.md\tanchor-d\taccept\ta later ruling wins\n"
        "p1/s2/main.md\tanchor-c\tp2/claim-quality.md\tanchor-x\treject\tanchor differs\n",
        encoding="utf-8",
    )
    depends = {("a", "b"), ("c", "d"), ("b", "c")}
    rows = compare.found_not_authored(depends=depends, authored=set(), entries=ENTRIES)
    joined = compare.with_verdicts(rows, compare.read_verdicts(path))
    assert [(row[0], row[5], row[-1]) for row in joined] == [("a", "b", "reject"), ("b", "c", ""), ("c", "d", "accept")]
