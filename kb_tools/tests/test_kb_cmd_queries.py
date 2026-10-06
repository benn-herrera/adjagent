"""Tests for the ``kb_cmd`` query surface: ``find`` and ``referenced-by``.

``find`` is a pure filter over the claims already loaded in the Index.
``referenced-by`` is a LIVE, leaf-granular reverse-find that scans KB leaf
bodies via the shared ``kb_links`` primitives — no persisted artifact.

``kb_cmd`` is a normal package (``from kb_tools.kb_cmd import index``); fixtures
are built per-test in a tmp dir: a stamped KB with a minimal ``.index/`` plus a
small leaf tree, so nothing depends on live KB state.
"""

import shutil
from pathlib import Path

from kb_tools import kb_index_lib
from kb_tools.kb_cmd import index as kb_index
from kb_tools.tests._stamped_kb import write_index, write_stamped_kb

_GOLDENS_0_9_0 = Path(__file__).parent / "fixtures" / "format-1.0.0" / "0.9.0"


def _claim_record(cid: str, title: str, *, solidity: float, build_band: str) -> dict:
    return {
        "node_type": "claim",
        "id": cid,
        "title": title,
        "canonical_path": "main/claim-quality.md",
        "canonical_anchor": title.lower().replace(" ", "-"),
        "confidence": solidity,
        "solidity": solidity,
        "build_status": None,
        "build_band": build_band,
        "rationale": "",
        "depends_on_count": 0,
        "strengthen_by_count": 0,
        "citation_count": 1,
    }


def _cite_record(cid: str, leaf_path: str) -> dict:
    return {"claim_id": cid, "leaf_path": leaf_path, "leaf_kind": "leaf", "tier2_marked": False}


def _build_index_dir(index_dir: Path, claims: list[dict], cites: list[dict]) -> None:
    """A stamped KB at ``index_dir``'s parent; streams other than these two are empty for these queries."""
    kb = write_stamped_kb(index_dir.parent)
    streams = {"claims": claims, "cites": cites}
    for name in kb_index_lib.INDEX_FILES:
        write_index(kb, name, streams.get(name, []))


_LEAF = """\
---
kind: leaf
{front}
---
[↑ Up](../index.md)

# {title}

{body}
"""


def _write_leaf(path: Path, *, front: str, title: str, body: str = "Leaf body.") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_LEAF.format(front=front, title=title, body=body), encoding="utf-8")


# ---------------------------------------------------------------------------
# find
# ---------------------------------------------------------------------------


def _index_with_named_claims(tmp_path: Path):
    claims = [
        _claim_record(
            "clm-aaaaaa", "Proposition 4.3 — Institutional Misalignment", solidity=0.55, build_band="input-only"
        ),
        _claim_record("clm-bbbbbb", "Theorem 4.5 — Positive Invariance of M", solidity=0.90, build_band="ok-to-build"),
        _claim_record(
            "clm-cccccc", "Proposition 4.4 — KPI-Gating as Discrete Pontryagin", solidity=0.55, build_band="input-only"
        ),
    ]
    index_dir = tmp_path / ".index"
    _build_index_dir(index_dir, claims, cites=[])
    return kb_index.load(index_dir)


def test_find_matches_by_number(tmp_path: Path) -> None:
    idx = _index_with_named_claims(tmp_path)
    hits = idx.find("4.3")
    assert [c.id for c in hits] == ["clm-aaaaaa"]


def test_find_matches_by_name_case_insensitive(tmp_path: Path) -> None:
    idx = _index_with_named_claims(tmp_path)
    hits = idx.find("pontryagin")
    assert [c.id for c in hits] == ["clm-cccccc"]
    assert hits[0].title.startswith("Proposition 4.4")


def test_find_returns_ids_and_titles_for_shared_substring(tmp_path: Path) -> None:
    idx = _index_with_named_claims(tmp_path)
    hits = idx.find("Proposition")
    assert {c.id for c in hits} == {"clm-aaaaaa", "clm-cccccc"}
    assert all(c.title and c.id.startswith("clm-") for c in hits)


def test_find_empty_query_matches_all(tmp_path: Path) -> None:
    idx = _index_with_named_claims(tmp_path)
    assert len(idx.find("")) == 3


def test_find_no_match(tmp_path: Path) -> None:
    idx = _index_with_named_claims(tmp_path)
    assert idx.find("no-such-claim") == []


# ---------------------------------------------------------------------------
# referenced-by
# ---------------------------------------------------------------------------


def test_referenced_by_returns_linking_leaf(tmp_path: Path) -> None:
    """A leaf body that links to a claim's originating leaf is returned."""
    kb = tmp_path / "kb-root"
    # clm-aaaaaa originates in origin.md.
    claims = [_claim_record("clm-aaaaaa", "Origin Claim", solidity=0.5, build_band="input-only")]
    cites = [_cite_record("clm-aaaaaa", "main/origin.md")]
    _build_index_dir(kb / ".index", claims, cites)

    _write_leaf(kb / "main" / "origin.md", front="claims: [clm-aaaaaa]", title="Origin Claim")
    # A sibling leaf links to the origin leaf in its body.
    _write_leaf(
        kb / "main" / "citing.md",
        front='no-claim: "links to origin"',
        title="Citing Leaf",
        body="See [the origin](origin.md) for the derivation.",
    )
    # An index container also links to origin — must NOT count (not a leaf body).
    (kb / "main" / "index.md").parent.mkdir(parents=True, exist_ok=True)
    (kb / "main" / "index.md").write_text(
        "---\nkind: index\n---\n\n# Index\n\n[origin](origin.md)\n",
        encoding="utf-8",
    )

    idx = kb_index.load(kb / ".index")
    assert idx.originating_leaf("clm-aaaaaa") == "main/origin.md"
    result = idx.referenced_by("clm-aaaaaa", kb_root=kb)
    assert result == ["main/citing.md"]


def test_referenced_by_empty_when_no_leaf_links(tmp_path: Path) -> None:
    """The today's-KB case: no inter-leaf body links -> empty, not an error."""
    kb = tmp_path / "kb-root"
    claims = [_claim_record("clm-aaaaaa", "Origin Claim", solidity=0.5, build_band="input-only")]
    cites = [_cite_record("clm-aaaaaa", "main/origin.md")]
    _build_index_dir(kb / ".index", claims, cites)

    _write_leaf(kb / "main" / "origin.md", front="claims: [clm-aaaaaa]", title="Origin Claim")
    _write_leaf(
        kb / "main" / "other.md",
        front='no-claim: "no links"',
        title="Other Leaf",
        body="No links here.",
    )

    idx = kb_index.load(kb / ".index")
    assert idx.referenced_by("clm-aaaaaa", kb_root=kb) == []


def test_referenced_by_unknown_claim_returns_empty(tmp_path: Path) -> None:
    idx = _index_with_named_claims(tmp_path)
    assert idx.referenced_by("clm-zzzzzz", kb_root=tmp_path) == []


def test_referenced_by_reads_an_older_kb_converted_and_writes_nothing(tmp_path: Path) -> None:
    """A 0.9.0 leaf's comment block reads as its frontmatter once converted; nothing on disk moves."""
    repo = tmp_path / "repo"
    shutil.copytree(_GOLDENS_0_9_0, repo)
    kb = repo / "kb-root"
    citing = kb / "b" / "c.md"
    citing.write_text(citing.read_text(encoding="utf-8") + "\nSee [A](../a.md).\n", encoding="utf-8")
    before = {path: path.read_bytes() for path in sorted(repo.rglob("*")) if path.is_file()}

    idx = kb_index.load(kb / ".index")

    assert idx.originating_leaf("clm-0dtsyu") == "a.md"
    assert idx.referenced_by("clm-0dtsyu", kb_root=kb) == ["b/c.md"]
    assert {path: path.read_bytes() for path in sorted(repo.rglob("*")) if path.is_file()} == before
