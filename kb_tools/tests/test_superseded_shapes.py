"""A `0.9.0` KB in the shapes a hand-built KB of that format holds, through migration, refresh and verify.

``fixtures/superseded-shapes/`` (see its README) is a migration's input only: a repository whose
``kb-root/`` the `0.9.0` toolchain left fresh. Each test reads a copy of it landed by refresh.
"""

import shutil
from pathlib import Path

import pytest

from kb_tools import (
    claim_sheet,
    kb_load,
    kb_schema,
    refresh_kb_metadata,
    verify_citations,
    verify_kb_metadata,
    verify_md_links,
)
from kb_tools.tests._in_process import run_main

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "superseded-shapes"

#: The two claims the KB-root register holds.
_ROOT_REGISTER_CLAIMS = ("clm-drf024", "clm-drf025")


@pytest.fixture(scope="module")
def refreshed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The fixture copied out and refreshed, which migrates it; returns its ``kb-root/``."""
    repo = shutil.copytree(FIXTURE, tmp_path_factory.mktemp("superseded-shapes") / "repo")
    result = run_main(refresh_kb_metadata.main, ["--kb-root", str(repo / "kb-root")])
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"from format {kb_schema.UNSTAMPED_FORMAT_VERSION} to {kb_schema.FORMAT_VERSION}" in result.stdout
    return repo / "kb-root"


@pytest.fixture(scope="module")
def sheet(refreshed: Path) -> claim_sheet.SheetInput:
    return claim_sheet.load(refreshed)


def _tree(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_refresh_after_the_migration_rewrites_nothing_but_the_sheets(tmp_path: Path, refreshed: Path) -> None:
    """The fixture was fresh in its own format, so its migration alone is what refresh leaves."""
    migrated = shutil.copytree(FIXTURE, tmp_path / "migrated") / "kb-root"
    kb_load.land_migration(migrated)

    sheets = {name for name in _tree(refreshed) if name.endswith(".svg")}
    assert sheets == {
        claim_sheet.SHEET_FILENAME,
        claim_sheet.DIGEST_FILENAME,
        f"alpha/{claim_sheet.SHEET_FILENAME}",
        f"beta/{claim_sheet.SHEET_FILENAME}",
    }
    assert {name: text for name, text in _tree(refreshed).items() if name not in sheets} == _tree(migrated)
    # The empty `0.9.0` stream lands as an empty stream, not as a missing one.
    assert kb_load.index_path(refreshed, "supported-by").read_text(encoding="utf-8") == ""


def test_the_migrated_kb_verifies_green(refreshed: Path) -> None:
    """``kb-verify``'s two verifiers, over every shape the fixture holds, bare ids in index prose included."""
    links = run_main(verify_md_links.main, ["--root", str(refreshed.parent)])
    metadata = run_main(verify_kb_metadata.main, ["--kb-root", str(refreshed)])

    assert links.returncode == 0, links.stdout + links.stderr
    assert metadata.returncode == 0, metadata.stdout + metadata.stderr


def test_bare_ids_in_index_prose_and_a_register_preamble_are_the_citation_grammars_alone(refreshed: Path) -> None:
    """Green under ``kb-verify`` above; the build-time citation grammar is what names them."""
    ids = {record["id"] for record in kb_load.read_index(refreshed, "claims")[0]}
    flagged = {
        (finding.path, claim_id)
        for finding in verify_citations.scan(refreshed)
        if finding.check == "channel"
        for claim_id in ids
        if finding.message.startswith(f"'{claim_id}'")
    }

    assert {
        ("entry-point.md", "clm-alp011"),
        ("core/index.md", "clm-drf024"),
        ("core/index.md", "clm-drf025"),
        ("alpha/index.md", "clm-alp011"),
        ("beta/index.md", "clm-bet021"),
        ("claim-quality.md", "clm-drf024"),
        ("alpha/claim-quality.md", "clm-alp011"),
    } <= flagged


def test_the_root_registers_claims_sit_in_the_root_bucket_on_the_sheet_and_the_digest(
    sheet: claim_sheet.SheetInput,
) -> None:
    """Their leaves sit in ``core/``, which registers nothing, so ``core`` is no volume and holds no node."""
    by_id = {node.id: node for node in sheet.nodes}
    root_box = next(
        line
        for line in claim_sheet.compose_digest(sheet).splitlines()
        if f'href="{kb_schema.ENTRY_POINT_FILENAME}"' in line
    )

    assert {node_id: by_id[node_id].volume_key for node_id in _ROOT_REGISTER_CLAIMS} == {
        "clm-drf024": "",
        "clm-drf025": "",
    }
    assert [volume.key for volume in sheet.volumes] == ["alpha", "beta", ""]
    assert ">2 nodes: 2 prose<" in root_box and ">within: 1 cited<" in root_box


def test_a_marker_above_a_bold_paragraph_reads_prose_over_a_block_title(sheet: claim_sheet.SheetInput) -> None:
    """``clm-drf024``'s title names a Proposition; its marker sits on its own line, outside any blockquote."""
    kinds = {node.id: node.kind for node in sheet.nodes}

    assert kinds["clm-drf024"] == "prose" and kinds["clm-drf025"] == "prose"
    # The single-claim leaves carry no marker, so those two are read from their titles.
    assert kinds["clm-alp011"] == "block" and kinds["clm-bet021"] == "block"
    assert sheet.claims_without_marker == 2
