"""The stamp at the commands that read a KB, and a migration landing on refresh.

An older KB is the `0.9.0` golden tree (``fixtures/format-1.0.0/0.9.0``), copied
out as a migration's input; a current one is its `1.0.0` twin. Refresh lands the
migration and then refreshes; verify reports an older KB stale and checks
nothing else; the queries and render-citation read it converted; the write ops,
the claim-graph stages and the citation gate refuse it naming the refresh; none
of them writes a byte where it refuses or only reads; and a KB newer than this
toolchain is refused by all of them.
"""

import shutil
from pathlib import Path

import pytest

from kb_tools import (
    kb_index_lib,
    kb_load,
    kb_schema,
    kb_util,
    kb_yaml,
    refresh_kb_metadata,
    verify_citations,
    verify_kb_metadata,
    verify_md_links,
)
from kb_tools.kb_claimgraph.__main__ import main as claimgraph_main
from kb_tools.kb_cmd import cli as kb_cli
from kb_tools.kb_cmd import index as kb_index
from kb_tools.kb_write import ops
from kb_tools.tests._in_process import run_main
from kb_tools.tests._shared_builds import tree_digest
from kb_tools.tests._stamped_kb import write_stamped_kb

_GOLDENS = Path(__file__).resolve().parent / "fixtures" / "format-1.0.0"
_OLDER = _GOLDENS / "0.9.0"
_CURRENT = _GOLDENS / "1.0.0"


def _repo(tmp_path: Path, source: Path) -> Path:
    """A repository holding a copy of ``source``'s KB and the build records beside it."""
    return shutil.copytree(source, tmp_path / "repo")


def _refresh(repo: Path):
    return run_main(refresh_kb_metadata.main, ["--kb-root", str(repo / "kb-root")])


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    span = kb_yaml.find_frontmatter(text)
    assert span is not None, path
    return kb_yaml.parse(text[span.body_start : span.body_end])


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------


def test_refresh_lands_an_older_kb_in_the_current_format_then_refreshes_it(tmp_path: Path) -> None:
    repo = _repo(tmp_path, _OLDER)

    result = _refresh(repo)

    assert result.returncode == 0, result.stdout + result.stderr
    assert f"from format {kb_schema.UNSTAMPED_FORMAT_VERSION} to {kb_schema.FORMAT_VERSION}" in result.stdout
    assert not list(repo.rglob("*.jsonl")) and not list(repo.glob("kb-build-*.json"))
    fields = _frontmatter(repo / "kb-root" / "entry-point.md")
    assert list(fields)[-1] == kb_schema.FORMAT_KEY and fields[kb_schema.FORMAT_KEY] == kb_schema.FORMAT_VERSION
    # Refresh derives the index and the entry point's aggregates; the leaves and
    # the build records it does not own stand exactly as the conversion wrote them.
    for relative in ("kb-root/a.md", "kb-root/b/c.md", *(f"{stem}.yaml" for stem in kb_load.RECORD_STEMS)):
        assert (repo / relative).read_bytes() == (_CURRENT / relative).read_bytes(), relative
    assert kb_load.open_kb(repo / "kb-root") == kb_load.KbFormat(version=kb_schema.FORMAT_VERSION, current=True)


def test_refresh_over_a_current_kb_migrates_nothing(tmp_path: Path) -> None:
    repo = _repo(tmp_path, _OLDER)
    assert _refresh(repo).returncode == 0
    landed = tree_digest(repo)

    again = _refresh(repo)

    assert again.returncode == 0, again.stdout + again.stderr
    assert "Migrated" not in again.stdout
    assert tree_digest(repo) == landed


# The golden tree's landing writes twelve files, the stamped entry point last; the loader's
# tests interrupt it before each, and refresh before the first and before the stamp.
@pytest.mark.parametrize("fail_at", [0, 11])
def test_a_refresh_interrupted_before_the_stamp_reads_old_and_the_next_one_ends_the_same(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fail_at: int
) -> None:
    uninterrupted = _repo(tmp_path / "whole", _OLDER)
    assert _refresh(uninterrupted).returncode == 0

    repo = _repo(tmp_path / "interrupted", _OLDER)
    real_write = kb_load.write_text_atomic
    writes: list[Path] = []

    def failing_write(text: str, path: Path) -> None:
        if len(writes) == fail_at:
            raise OSError(f"injected failure at write {fail_at}")
        writes.append(path)
        real_write(text, path)

    monkeypatch.setattr(kb_load, "write_text_atomic", failing_write)
    stopped = _refresh(repo)
    monkeypatch.setattr(kb_load, "write_text_atomic", real_write)

    assert stopped.returncode == 2 and "next refresh completes it" in stopped.stderr, stopped.stderr
    assert kb_load.open_kb(repo / "kb-root").version == kb_schema.UNSTAMPED_FORMAT_VERSION
    assert _refresh(repo).returncode == 0
    assert tree_digest(repo) == tree_digest(uninterrupted)


# ---------------------------------------------------------------------------
# Verify and the queries on an older KB
# ---------------------------------------------------------------------------


def test_verify_on_an_older_kb_reports_it_stale_checks_nothing_else_and_writes_nothing(tmp_path: Path) -> None:
    repo = _repo(tmp_path, _OLDER)
    before = tree_digest(repo)

    result = run_main(verify_kb_metadata.main, ["--kb-root", str(repo / "kb-root")])

    assert result.returncode == 1
    failures = [line for line in result.stdout.splitlines() if line.startswith("[FAIL]")]
    assert len(failures) == 1 and "index stale" in failures[0], result.stdout
    assert kb_schema.UNSTAMPED_FORMAT_VERSION in failures[0]
    assert "kb_tools.refresh_kb_metadata" in result.stdout
    assert tree_digest(repo) == before


def test_the_queries_read_an_older_kb_as_its_migration_would_and_write_nothing(tmp_path: Path) -> None:
    older = _repo(tmp_path / "older", _OLDER)
    current = _repo(tmp_path / "current", _CURRENT)
    before = tree_digest(older)

    read = kb_index.load(older / "kb-root" / ".index")
    migrated = kb_index.load(current / "kb-root" / ".index")

    assert read.stats == migrated.stats
    assert [node.id for node in read.all_nodes] == [node.id for node in migrated.all_nodes]
    assert read.all_depends_on_edges == migrated.all_depends_on_edges
    for argv in (["stats", "--json"], ["deps", "clm-0dtsyu", "--json"]):
        older_run = run_main(kb_cli.main, [*argv, "--index-dir", str(older / "kb-root" / ".index")])
        current_run = run_main(kb_cli.main, [*argv, "--index-dir", str(current / "kb-root" / ".index")])
        assert older_run.returncode == current_run.returncode == 0, older_run.stderr
        assert older_run.stdout == current_run.stdout
    assert tree_digest(older) == before


def test_a_line_that_is_no_record_is_dropped_by_the_queries(tmp_path: Path) -> None:
    repo = _repo(tmp_path, _CURRENT)
    claims = kb_load.index_path(repo / "kb-root", "claims")
    claims.write_text(claims.read_text(encoding="utf-8") + "not a record\n", encoding="utf-8")

    loaded = kb_index.load(repo / "kb-root" / ".index")

    assert [node.id for node in loaded.all_nodes] == [
        node.id for node in kb_index.load(_CURRENT / "kb-root" / ".index").all_nodes
    ]


# ---------------------------------------------------------------------------
# A newer KB
# ---------------------------------------------------------------------------


def _newer_kb(tmp_path: Path) -> Path:
    repo = _repo(tmp_path, _CURRENT)
    entry = repo / "kb-root" / "entry-point.md"
    entry.write_text(
        entry.read_text(encoding="utf-8").replace(f'"{kb_schema.FORMAT_VERSION}"', '"1.1.0"'), encoding="utf-8"
    )
    return repo


def _refused(result, *, stream: str) -> None:
    text = getattr(result, stream)
    assert result.returncode == 2, result.stdout + result.stderr
    assert kb_schema.FORMAT_KEY in text and "1.1.0" in text and kb_schema.FORMAT_VERSION in text, text
    assert kb_load.UPDATE_REMEDY in text, text


def test_a_newer_kb_is_refused_by_refresh_verify_and_the_queries_and_nothing_is_written(tmp_path: Path) -> None:
    repo = _newer_kb(tmp_path)
    kb = repo / "kb-root"
    before = tree_digest(repo)

    _refused(_refresh(repo), stream="stderr")
    _refused(run_main(verify_kb_metadata.main, ["--kb-root", str(kb)]), stream="stderr")
    _refused(run_main(verify_md_links.main, ["--root", str(repo)]), stream="stderr")
    _refused(run_main(kb_cli.main, ["stats", "--index-dir", str(kb / ".index")]), stream="stderr")
    assert tree_digest(repo) == before


def test_a_kb_with_no_entry_point_is_refused_naming_the_kb_root(tmp_path: Path) -> None:
    kb = write_stamped_kb(tmp_path / "kb-root")
    (kb / "entry-point.md").unlink()

    for result in (
        run_main(refresh_kb_metadata.main, ["--kb-root", str(kb)]),
        run_main(verify_kb_metadata.main, ["--kb-root", str(kb)]),
        run_main(kb_cli.main, ["stats", "--index-dir", str(kb / ".index")]),
    ):
        assert result.returncode == 2, result.stdout + result.stderr
        assert kb_load.CHECK_KB_ROOT in result.stderr


# ---------------------------------------------------------------------------
# The write ops, render-citation, the claim-graph stages and the citation gate
# ---------------------------------------------------------------------------

#: A set-frontmatter that writes on the current golden KB. The format is read
#: ahead of the values, so every op is handed this one file.
_SET_FRONTMATTER = '[[entry]]\ndocument = "a.md"\nkind = "leaf"\nno-claim = "prose, rewritten"\n'

#: A quotation of the current golden's `b/c.md`, cited from `a.md`.
_CITATION = (
    '[[entry]]\nexcerpt = "Two experiments and two supports."\ncited-document = "b/c.md"\n'
    'anchor = "lemma-2-hölder-bound"\nciting-document = "a.md"\n'
)


def _values(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "values.toml"
    path.write_text(text, encoding="utf-8")
    return path


def _format_failure(result: ops.Result) -> str:
    """The one FAIL line's detail, the line named for the format's check."""
    assert result.exit_code == ops.ExitCode.ENVIRONMENT, result.lines()
    failures = [item for item in result.report if item.status == kb_util.FAIL]
    assert [item.name for item in failures] == [kb_schema.FORMAT_KEY], result.lines()
    return failures[0].detail


def _claimgraph(repo: Path):
    """The declared pass, run from inside ``repo`` (which carries a ``.git``)."""
    return run_main(claimgraph_main, [], cwd=repo)


def test_every_write_op_on_an_older_kb_exits_2_naming_the_refresh_and_writes_nothing(tmp_path: Path) -> None:
    repo = _repo(tmp_path, _OLDER)
    values = _values(tmp_path, _SET_FRONTMATTER)
    before = tree_digest(repo)

    for name, op in ops.OPS.items():
        detail = _format_failure(op.run(kb_root=repo / "kb-root", values_file=values))
        assert kb_schema.UNSTAMPED_FORMAT_VERSION in detail and kb_util.refresh_cmd(repo) in detail, (name, detail)
    assert tree_digest(repo) == before


def test_every_write_op_on_a_newer_kb_exits_2_naming_the_update_and_writes_nothing(tmp_path: Path) -> None:
    repo = _newer_kb(tmp_path)
    values = _values(tmp_path, _SET_FRONTMATTER)
    before = tree_digest(repo)

    for name, op in ops.OPS.items():
        detail = _format_failure(op.run(kb_root=repo / "kb-root", values_file=values))
        assert "1.1.0" in detail and kb_load.UPDATE_REMEDY in detail, (name, detail)
    assert tree_digest(repo) == before


def test_a_write_op_on_a_current_kb_writes(tmp_path: Path) -> None:
    repo = _repo(tmp_path, _CURRENT)

    result = ops.OPS["set-frontmatter"].run(kb_root=repo / "kb-root", values_file=_values(tmp_path, _SET_FRONTMATTER))

    assert result.exit_code == ops.ExitCode.WRITTEN, result.lines()
    assert _frontmatter(repo / "kb-root" / "a.md")["no-claim"] == "prose, rewritten"


def test_render_citation_reads_an_older_kb_as_its_migration_would_and_writes_nothing(tmp_path: Path) -> None:
    older = _repo(tmp_path / "older", _OLDER)
    current = _repo(tmp_path / "current", _CURRENT)
    values = _values(tmp_path, _CITATION)
    before = tree_digest(older)

    read = ops.render_citation(kb_root=older / "kb-root", values_file=values)
    migrated = ops.render_citation(kb_root=current / "kb-root", values_file=values)

    assert read.exit_code == migrated.exit_code == ops.ExitCode.PRINTED, read.lines()
    assert read.printed == migrated.printed
    assert tree_digest(older) == before


def test_render_citation_on_a_newer_kb_exits_2_naming_the_update(tmp_path: Path) -> None:
    repo = _newer_kb(tmp_path)
    before = tree_digest(repo)

    detail = _format_failure(ops.render_citation(kb_root=repo / "kb-root", values_file=_values(tmp_path, _CITATION)))

    assert kb_load.UPDATE_REMEDY in detail
    assert tree_digest(repo) == before


def test_a_write_op_and_render_citation_with_no_entry_point_refuse_naming_the_kb_root(tmp_path: Path) -> None:
    repo = _repo(tmp_path, _CURRENT)
    (repo / "kb-root" / "entry-point.md").unlink()
    before = tree_digest(repo)

    for result in (
        ops.OPS["set-frontmatter"].run(kb_root=repo / "kb-root", values_file=_values(tmp_path, _SET_FRONTMATTER)),
        ops.render_citation(kb_root=repo / "kb-root", values_file=_values(tmp_path, _CITATION)),
    ):
        assert result.exit_code == ops.ExitCode.ENVIRONMENT, result.lines()
        assert [item.name for item in result.report if item.status == kb_util.FAIL] == [kb_load.CHECK_KB_ROOT]
    assert tree_digest(repo) == before


def test_the_claim_graph_stages_and_the_citation_gate_refuse_an_older_kb_naming_the_refresh(tmp_path: Path) -> None:
    repo = _repo(tmp_path, _OLDER)
    (repo / ".git").mkdir()
    before = tree_digest(repo)

    for result in (_claimgraph(repo), run_main(verify_citations.main, ["--kb-root", str(repo / "kb-root")])):
        assert result.returncode == 2, result.stdout + result.stderr
        assert kb_schema.UNSTAMPED_FORMAT_VERSION in result.stderr, result.stderr
        assert kb_util.refresh_cmd(repo) in result.stderr, result.stderr
    assert tree_digest(repo) == before


def test_the_claim_graph_stages_and_the_citation_gate_refuse_a_newer_kb(tmp_path: Path) -> None:
    repo = _newer_kb(tmp_path)
    (repo / ".git").mkdir()
    before = tree_digest(repo)

    _refused(_claimgraph(repo), stream="stderr")
    _refused(run_main(verify_citations.main, ["--kb-root", str(repo / "kb-root")]), stream="stderr")
    assert tree_digest(repo) == before


def test_the_citation_gate_runs_on_a_current_kb(tmp_path: Path) -> None:
    repo = _repo(tmp_path, _CURRENT)

    result = run_main(verify_citations.main, ["--kb-root", str(repo / "kb-root")])

    assert result.returncode == 0, result.stdout + result.stderr


def test_every_index_stream_refresh_writes_is_one_the_inventory_names(tmp_path: Path) -> None:
    repo = _repo(tmp_path, _OLDER)
    assert _refresh(repo).returncode == 0

    written = sorted(path.name for path in (repo / "kb-root" / ".index").iterdir())

    assert written == sorted(kb_load.index_path(repo / "kb-root", name).name for name in kb_index_lib.INDEX_FILES)
