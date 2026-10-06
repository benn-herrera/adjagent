"""The stamp-first loader: version reading, reads of an older KB converted, and the migrating save.

KBs are built in-test under `tmp_path`; the one 0.9.0 KB is a copy of kbase's golden tree
(`fixtures/format-1.0.0/0.9.0/`), as migration input, and the landing is checked against the
`1.0.0` golden tree.
"""

import shutil
from pathlib import Path

import pytest

from kb_tools import kb_load
from kb_tools.kb_load import FormatRefusal, KbFormat, Landing
from kb_tools.kb_yaml import IndexLineError

GOLDENS = Path(__file__).parent / "fixtures" / "format-1.0.0"


def _read(path: Path) -> str:
    with path.open(encoding="utf-8", newline="") as handle:
        return handle.read()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def _tree(root: Path) -> dict[str, str]:
    return {path.relative_to(root).as_posix(): _read(path) for path in sorted(root.rglob("*")) if path.is_file()}


def _kb(tmp_path: Path, entry_point: str) -> Path:
    kb_root = tmp_path / "kb-root"
    _write(kb_root / "entry-point.md", entry_point)
    return kb_root


def _golden_0_9_0(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    shutil.copytree(GOLDENS / "0.9.0", repo)
    return repo


STAMPED = '---\nkind: entry-point\nkb-format: "{}"\n---\n\n# KB\n'


@pytest.mark.parametrize(
    ("entry_point", "expected"),
    [
        ("# KB\n", KbFormat("0.9.0", current=False)),
        ("---\nkind: entry-point\n---\n# KB\n", KbFormat("0.9.0", current=False)),
        ('<!-- kb-frontmatter\nkind: entry-point\nkb-format: "0.9.2"\n-->\n# KB\n', KbFormat("0.9.2", current=False)),
        (STAMPED.format("1.0.0"), KbFormat("1.0.0", current=True)),
        (STAMPED.format("1.0.3"), KbFormat("1.0.3", current=True)),
        ('---\r\nkind: entry-point\r\nkb-format: "1.0.0"\r\n---\r\n', KbFormat("1.0.0", current=True)),
    ],
    ids=["no-block", "yaml-without-stamp", "comment-block-stamp", "1.0.0", "1.0.3", "crlf-1.0.0"],
)
def test_the_entry_points_stamp_is_the_kbs_version(tmp_path: Path, entry_point: str, expected: KbFormat) -> None:
    assert kb_load.open_kb(_kb(tmp_path, entry_point)) == expected


@pytest.mark.parametrize(
    "entry_point",
    [STAMPED.format("1.1.0"), STAMPED.format("2.0.0"), "<!-- kb-frontmatter\nkb-format: 1.1.0\n-->\n"],
    ids=["1.1.0", "2.0.0", "comment-block-1.1.0"],
)
def test_a_newer_major_or_minor_is_refused_naming_both_versions_and_the_remedy(
    tmp_path: Path, entry_point: str
) -> None:
    kb_root = _kb(tmp_path, entry_point)

    with pytest.raises(FormatRefusal) as raised:
        kb_load.open_kb(kb_root)

    refusal = raised.value
    assert (refusal.check, refusal.path, refusal.remedy) == ("kb-format", kb_root / "entry-point.md", "update kb_tools")
    assert "1.0.0" in refusal.detail and ("1.1.0" in refusal.detail or "2.0.0" in refusal.detail)


@pytest.mark.parametrize(
    "entry_point",
    [
        STAMPED.format("1.0"),
        STAMPED.format("01.0.0"),
        STAMPED.format("1.0.0-rc1"),
        STAMPED.format(""),
        "---\nkb-format: [1.0.0]\n---\n",
        "---\nkb-format: true\n---\n",
        "---\nkb-format: 1.5\n---\n",
        "---\nkind: 'entry-point'\n---\n",
    ],
    ids=["two-parts", "leading-zero", "pre-release", "empty", "list", "bool", "number", "outside-the-dialect"],
)
def test_a_malformed_stamp_is_refused_naming_kb_format(tmp_path: Path, entry_point: str) -> None:
    with pytest.raises(FormatRefusal) as raised:
        kb_load.open_kb(_kb(tmp_path, entry_point))

    assert raised.value.check == "kb-format" and raised.value.remedy == ""


def test_no_entry_point_is_refused_naming_kb_root(tmp_path: Path) -> None:
    (tmp_path / "kb-root").mkdir()

    with pytest.raises(FormatRefusal) as raised:
        kb_load.open_kb(tmp_path / "kb-root")

    assert raised.value.check == "kb-root"


def test_an_entry_point_that_is_not_utf_8_is_a_refusal_naming_it(tmp_path: Path) -> None:
    entry = tmp_path / "kb-root" / "entry-point.md"
    entry.parent.mkdir()
    entry.write_bytes(b"# K\xff\n")

    with pytest.raises(FormatRefusal, match="entry-point.md: not UTF-8") as raised:
        kb_load.open_kb(tmp_path / "kb-root")

    assert raised.value.check == "kb-root"


def test_an_older_kb_reads_converted_and_nothing_is_written(tmp_path: Path) -> None:
    repo = _golden_0_9_0(tmp_path)
    before = _tree(repo)
    kb_root = repo / "kb-root"

    document = kb_load.read_document(kb_root, "b/c.md")
    claims, problems = kb_load.read_index(kb_root, "claims")
    record = kb_load.read_record(repo, "kb-build-node-pass")

    assert document == _read(GOLDENS / "1.0.0" / "kb-root" / "b" / "c.md")
    assert problems == [] and [claim["id"] for claim in claims][:2] == ["clm-0dtsyu", "clm-2h6i01"]
    assert record["leaves"]["a.md"]["verdicts"][0] == {"line": 3, "verdict": "claim", "cause": None}
    assert _tree(repo) == before


def test_an_older_kb_reads_the_old_spelling_where_both_stand(tmp_path: Path) -> None:
    repo = _golden_0_9_0(tmp_path)
    kb_root = repo / "kb-root"
    _write(kb_root / ".index" / "claims.yaml", '--- {"id": "from-the-new-spelling"}\n')
    _write(repo / "kb-build-unmarked.yaml", "about: from the new spelling\n")
    _write(kb_root / ".index" / "cites.yaml", '--- {"id": "only-the-new-spelling"}\n')
    (kb_root / ".index" / "cites.jsonl").unlink()

    claims, _ = kb_load.read_index(kb_root, "claims")
    record = kb_load.read_record(repo, "kb-build-unmarked")
    cites, _ = kb_load.read_index(kb_root, "cites")

    assert claims[0]["id"] == "clm-0dtsyu"
    assert record["about"].startswith("The claim-graph")
    assert cites == [{"id": "only-the-new-spelling"}]


def test_a_current_kb_reads_the_current_spelling_from_disk(tmp_path: Path) -> None:
    kb_root = _kb(tmp_path, STAMPED.format("1.0.0"))
    _write(kb_root / ".index" / "claims.jsonl", '{"id": "superseded"}\n')
    _write(kb_root / ".index" / "claims.yaml", '--- {"id": "current"}\n')
    _write(tmp_path / "kb-build-unmarked.yaml", "about: current\n")

    assert kb_load.read_index(kb_root, "claims") == ([{"id": "current"}], [])
    assert kb_load.read_record(tmp_path, "kb-build-unmarked") == {"about": "current"}


def test_an_index_line_that_is_not_a_record_is_reported_not_raised(tmp_path: Path) -> None:
    kb_root = _kb(tmp_path, STAMPED.format("1.0.0"))
    _write(kb_root / ".index" / "claims.yaml", '--- {"id": "a"}\nnot a record\n--- {"id": "b"}\n')

    records, problems = kb_load.read_index(kb_root, "claims")

    assert records == [{"id": "a"}, {"id": "b"}]
    assert [problem.line for problem in problems] == [2] and isinstance(problems[0], IndexLineError)


def test_a_superseded_index_line_that_does_not_convert_is_reported_at_its_line_not_raised(tmp_path: Path) -> None:
    """The queries drop it and keep the rest, as they do a bad line of the current form."""
    kb_root = _golden_0_9_0(tmp_path) / "kb-root"
    _write(kb_root / ".index" / "cites.jsonl", '{"id": "a"}\nnot a record\n\n{"id": "b"}\n')

    records, problems = kb_load.read_index(kb_root, "cites")

    assert records == [{"id": "a"}, {"id": "b"}]
    assert [problem.line for problem in problems] == [2] and isinstance(problems[0], IndexLineError)


def test_a_newer_kb_refuses_every_read(tmp_path: Path) -> None:
    kb_root = _kb(tmp_path, STAMPED.format("1.1.0"))
    _write(kb_root / ".index" / "claims.yaml", "")
    _write(tmp_path / "kb-build-unmarked.yaml", "")

    for read in (
        lambda: kb_load.read_document(kb_root, "entry-point.md"),
        lambda: kb_load.read_index(kb_root, "claims"),
        lambda: kb_load.read_record(tmp_path, "kb-build-unmarked"),
        lambda: kb_load.land_migration(kb_root),
    ):
        with pytest.raises(FormatRefusal):
            read()


def test_a_record_standing_in_neither_spelling_is_missing_before_any_kb_is_read(tmp_path: Path) -> None:
    """A repository whose KB does not exist yet holds no record; it is not a refusal."""
    with pytest.raises(FileNotFoundError):
        kb_load.read_record(tmp_path, "kb-build-unmarked")


class RecordingWriter:
    """Stands in for the atomic writer: records each path, and fails at one write index if asked."""

    def __init__(self, write, fail_at: int | None = None) -> None:
        self.write = write
        self.fail_at = fail_at
        self.paths: list[Path] = []

    def __call__(self, text: str, path: Path) -> None:
        if len(self.paths) == self.fail_at:
            raise OSError(f"injected at write {self.fail_at}")
        self.write(text, path)
        self.paths.append(path)


def test_a_landing_writes_the_1_0_0_tree_with_the_entry_point_last(tmp_path: Path, monkeypatch) -> None:
    repo = _golden_0_9_0(tmp_path)
    writer = RecordingWriter(kb_load.write_text_atomic)
    monkeypatch.setattr(kb_load, "write_text_atomic", writer)

    landing = kb_load.land_migration(repo / "kb-root")

    assert _tree(repo) == _tree(GOLDENS / "1.0.0")
    assert writer.paths[-1] == repo / "kb-root" / "entry-point.md"
    assert list(landing.written) == writer.paths and len(landing.written) == 12
    assert sorted(path.relative_to(repo).as_posix() for path in landing.removed) == sorted(
        path.relative_to(GOLDENS / "0.9.0").as_posix()
        for path in (GOLDENS / "0.9.0").rglob("*")
        if path.suffix in (".json", ".jsonl")
    )
    assert kb_load.open_kb(repo / "kb-root") == KbFormat("1.0.0", current=True)
    assert kb_load.land_migration(repo / "kb-root") == Landing(written=(), removed=())


@pytest.mark.parametrize("fail_at", range(12))
def test_a_landing_interrupted_at_any_write_leaves_no_stamp_and_the_next_one_completes(
    tmp_path: Path, monkeypatch, fail_at: int
) -> None:
    repo = _golden_0_9_0(tmp_path)
    kb_root = repo / "kb-root"
    monkeypatch.setattr(kb_load, "write_text_atomic", RecordingWriter(kb_load.write_text_atomic, fail_at))

    with pytest.raises(OSError, match="injected"):
        kb_load.land_migration(kb_root)

    assert kb_load.open_kb(kb_root) == KbFormat("0.9.0", current=False)
    assert kb_load.read_document(kb_root, "b/c.md") == _read(GOLDENS / "1.0.0" / "kb-root" / "b" / "c.md")
    monkeypatch.undo()
    kb_load.land_migration(kb_root)
    assert _tree(repo) == _tree(GOLDENS / "1.0.0")


def test_a_landing_keeps_a_crlf_documents_body_bytes(tmp_path: Path) -> None:
    repo = _golden_0_9_0(tmp_path)
    leaf = repo / "kb-root" / "a.md"
    _write(leaf, _read(leaf).replace("\n", "\r\n"))

    kb_load.land_migration(repo / "kb-root")

    assert _read(leaf) == "---\nkind: leaf\nno-claim: prose\n---\n[↑ KB](entry-point.md)\r\n\r\n\r\n# A\r\n"


def test_a_current_kb_at_another_patch_is_restamped_alone(tmp_path: Path) -> None:
    kb_root = _kb(tmp_path, STAMPED.format("1.0.3"))
    _write(kb_root / "a.md", "<!-- kb-frontmatter\nkind: leaf\n-->\n")

    landing = kb_load.land_migration(kb_root)

    assert landing == Landing(written=(kb_root / "entry-point.md",), removed=())
    assert _read(kb_root / "entry-point.md") == STAMPED.format("1.0.0")
    assert _read(kb_root / "a.md") == "<!-- kb-frontmatter\nkind: leaf\n-->\n"
