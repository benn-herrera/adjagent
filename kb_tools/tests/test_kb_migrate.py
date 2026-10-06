"""The 0.9.0 → 1.0.0 conversion against kbase's golden pairs and kbase's converter cases.

The goldens (`fixtures/format-1.0.0/`, see its README) are kbase's conformance test: the `0.9.0`
tree converted is the `1.0.0` tree byte for byte. The document cases are kbase's
`TestDocumentYAMLFrontmatter` table (`internal/migrate/migrate_test.go`), driven through `chain`.
"""

import json
import time
from pathlib import Path

import pytest

from kb_tools import kb_migrate, kb_yaml
from kb_tools.kb_migrate import MigrationError

GOLDENS = Path(__file__).parent / "fixtures" / "format-1.0.0"
DOCUMENT = "kb-root/doc.md"
ENTRY_POINT = "kb-root/entry-point.md"
INDEX = "kb-root/.index/claims.jsonl"


def _tree(root: Path) -> dict[str, str]:
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            with path.open(encoding="utf-8", newline="") as handle:
                files[path.relative_to(root).as_posix()] = handle.read()
    return files


def _convert(path: str, text: str) -> str:
    converted = kb_migrate.chain("0.9.0", "1.0.0", {path: text})
    return converted.files[path]


def test_the_0_9_0_golden_tree_converts_to_the_1_0_0_tree_byte_for_byte() -> None:
    converted = kb_migrate.chain("0.9.0", "1.0.0", _tree(GOLDENS / "0.9.0"))

    want = _tree(GOLDENS / "1.0.0")
    assert sorted(converted.files) == sorted(want)
    assert [path for path in want if converted.files[path] != want[path]] == []


def test_the_obsolete_set_is_exactly_the_build_records_and_the_jsonl_index() -> None:
    given = _tree(GOLDENS / "0.9.0")

    converted = kb_migrate.chain("0.9.0", "1.0.0", given)

    expected = sorted(path for path in given if path.endswith((".json", ".jsonl")))
    assert len(expected) == 9
    assert list(converted.obsolete) == expected
    assert not set(converted.obsolete) & set(converted.files)
    assert set(kb_migrate.SUPERSEDED_RECORD_PATHS) <= set(converted.obsolete)


# kbase `TestDocumentYAMLFrontmatter`: (case, 0.9.0 text, 1.0.0 text, whether it is the entry point).
DOCUMENT_CASES = [
    ("no block", "# Title\n\ntext\n", "# Title\n\ntext\n", False),
    (
        "scalars and an inline list",
        '<!-- kb-frontmatter\nkind: leaf\npath-stable: "Part I: the setup"\nclaims: [clm-aaaaaa, clm-bbbbbb]\n'
        "experiments: []\nflag: true\nempty:\n-->\n\n# T\n",
        '---\nkind: leaf\npath-stable: "Part I: the setup"\nclaims: [clm-aaaaaa, clm-bbbbbb]\nexperiments: []\n'
        'flag: true\nempty: ""\n---\n\n# T\n',
        False,
    ),
    (
        "a wrapped list and a bullet list",
        "<!-- kb-frontmatter\nkind: index\nsubtree-claims: [clm-aaaaaa,\n  clm-bbbbbb]\nsubtree-experiments:\n"
        "  - exp-cccccc\n  - exp-dddddd\n-->\n",
        "---\nkind: index\nsubtree-claims: [clm-aaaaaa, clm-bbbbbb]\nsubtree-experiments:\n  - exp-cccccc\n"
        "  - exp-dddddd\n---\n",
        False,
    ),
    (
        "an experiment and its scored pairs, a strength the 0.9.0 reader could not read ending the list",
        "<!-- kb-frontmatter\nkind: leaf\nexp-id: exp-cccccc\nstatus: run\nstrengthens:\n  - clm-aaaaaa: 0.8\n"
        "  - clm-bbbbbb: *pending*\n  - clm-dddddd: 0.5\n-->\n",
        "---\nkind: leaf\nexperiment-nodes:\n  - exp-id: exp-cccccc\n    status: run\n    strengthens:\n"
        "      - clm-aaaaaa: 0.8\n---\n",
        False,
    ),
    (
        "two experiments and two supports, a key between",
        "<!-- kb-frontmatter\nkind: leaf\nexp-id: exp-cccccc\nstatus: run\nsup-id: sup-eeeeee\nsupports:\n"
        '  - clm-aaaaaa: 0.5\nno-claim: "hosts nodes"\nexp-id: exp-dddddd\nstrengthens:\n  - clm-bbbbbb: 1.0\n'
        "status: pending\nsup-id: sup-ffffff\n-->\n",
        "---\nkind: leaf\nexperiment-nodes:\n  - exp-id: exp-cccccc\n    status: run\n  - exp-id: exp-dddddd\n"
        "    strengthens:\n      - clm-bbbbbb: 1.0\n    status: pending\nsupport-nodes:\n  - sup-id: sup-eeeeee\n"
        '    supports:\n      - clm-aaaaaa: 0.5\n  - sup-id: sup-ffffff\nno-claim: "hosts nodes"\n---\n',
        False,
    ),
    (
        "an experiments reference list beside a declaration",
        "<!-- kb-frontmatter\nkind: leaf\nexperiments: [exp-dddddd]\nexp-id: exp-cccccc\nstatus: run\n-->\n",
        "---\nkind: leaf\nexperiments: [exp-dddddd]\nexperiment-nodes:\n  - exp-id: exp-cccccc\n    status: run\n---\n",
        False,
    ),
    (
        "a block below the up-link",
        '[↑ KB](entry-point.md)\n\n<!-- kb-frontmatter\nkind: leaf\nno-claim: "prose"\n-->\n\n# A\n',
        "---\nkind: leaf\nno-claim: prose\n---\n[↑ KB](entry-point.md)\n\n\n# A\n",
        False,
    ),
    (
        "declarations and members written with a leading dash",
        "<!-- kb-frontmatter\nkind: leaf\n- exp-id: exp-cccccc\n- status: run\n- sup-id: sup-eeeeee\n-->\n",
        "---\nkind: leaf\nexperiment-nodes:\n  - exp-id: exp-cccccc\n    status: run\nsupport-nodes:\n"
        "  - sup-id: sup-eeeeee\n---\n",
        False,
    ),
    (
        "pairs without a bullet",
        "<!-- kb-frontmatter\nkind: leaf\nexp-id: exp-cccccc\nstatus: run\nstrengthens:\nclm-aaaaaa: 0.8\n"
        "clm-bbbbbb: 0.5\n-->\n",
        "---\nkind: leaf\nexperiment-nodes:\n  - exp-id: exp-cccccc\n    status: run\n    strengthens:\n"
        "      - clm-aaaaaa: 0.8\n      - clm-bbbbbb: 0.5\n---\n",
        False,
    ),
    (
        "a member after another key attaches to its kind's latest node",
        "<!-- kb-frontmatter\nexp-id: exp-cccccc\nkind: leaf\nstatus: run\nexp-id: exp-dddddd\nclaims: [clm-aaaaaa]\n"
        "status: pending\n-->\n",
        "---\nexperiment-nodes:\n  - exp-id: exp-cccccc\n    status: run\n  - exp-id: exp-dddddd\n"
        "    status: pending\nkind: leaf\nclaims: [clm-aaaaaa]\n---\n",
        False,
    ),
    (
        "a declaration inside a pair list opens a node",
        "<!-- kb-frontmatter\nkind: leaf\nexp-id: exp-cccccc\nstatus: run\nstrengthens:\n  - clm-aaaaaa: 0.8\n"
        "  - exp-id: exp-dddddd\nstatus: pending\n-->\n",
        "---\nkind: leaf\nexperiment-nodes:\n  - exp-id: exp-cccccc\n    status: run\n    strengthens:\n"
        "      - clm-aaaaaa: 0.8\n  - exp-id: exp-dddddd\n    status: pending\n---\n",
        False,
    ),
    (
        "a score in exponent form stays a number",
        "<!-- kb-frontmatter\nkind: leaf\nsup-id: sup-eeeeee\nsupports:\n  - clm-aaaaaa: 1e-05\n-->\n",
        "---\nkind: leaf\nsupport-nodes:\n  - sup-id: sup-eeeeee\n    supports:\n      - clm-aaaaaa: 1e-05\n---\n",
        False,
    ),
    (
        "a member with no node of its kind stays a key",
        "<!-- kb-frontmatter\nkind: leaf\nstatus: run\n-->\n",
        "---\nkind: leaf\nstatus: run\n---\n",
        False,
    ),
    (
        "a document already in YAML frontmatter",
        "---\nkind: leaf\n---\n[↑ KB](entry-point.md)\n",
        "---\nkind: leaf\n---\n[↑ KB](entry-point.md)\n",
        False,
    ),
    (
        "a document opening with a prose block between rules converts, the block left as prose",
        "---\nSome notes: with: colons\n---\n<!-- kb-frontmatter\nkind: leaf\n-->\n# T\n",
        "---\nkind: leaf\n---\n---\nSome notes: with: colons\n---\n# T\n",
        False,
    ),
    (
        "an entry point already in YAML frontmatter stamped in place",
        '---\nkb-format: "0.9.0"\nkind: entry-point\n---\n\n# KB\n',
        '---\nkind: entry-point\nkb-format: "1.0.0"\n---\n\n# KB\n',
        True,
    ),
    (
        "the entry point stamped last",
        "<!-- kb-frontmatter\nkb-format: 0.9.0\nkind: entry-point\n-->\n\n# KB\n",
        '---\nkind: entry-point\nkb-format: "1.0.0"\n---\n\n# KB\n',
        True,
    ),
    ("an entry point with no block stamped", "# KB\n", '---\nkb-format: "1.0.0"\n---\n# KB\n', True),
]


@pytest.mark.parametrize(
    ("given", "expected", "entry_point"),
    [case[1:] for case in DOCUMENT_CASES],
    ids=[case[0] for case in DOCUMENT_CASES],
)
def test_a_document_converts_as_kbase_converts_it(given: str, expected: str, entry_point: bool) -> None:
    assert _convert(ENTRY_POINT if entry_point else DOCUMENT, given) == expected


def test_a_crlf_document_keeps_its_body_breaks_and_loses_the_blocks() -> None:
    given = '[↑ KB](entry-point.md)\r\n\r\n<!-- kb-frontmatter\r\nkind: leaf\r\nno-claim: "prose"\r\n-->\r\n\r\n# A\r\n'
    expected = "---\nkind: leaf\nno-claim: prose\n---\n[↑ KB](entry-point.md)\r\n\r\n\r\n# A\r\n"

    assert _convert(DOCUMENT, given) == expected


def test_a_repeated_key_outside_a_node_declaration_is_refused_naming_it() -> None:
    given = "<!-- kb-frontmatter\nkind: leaf\nclaims: [clm-aaaaaa]\nclaims: [clm-bbbbbb]\n-->\n"

    with pytest.raises(MigrationError, match=r"kb-root/doc\.md: frontmatter key 'claims' repeats"):
        _convert(DOCUMENT, given)


@pytest.mark.parametrize(
    ("text", "stamp"),
    [
        ('<!-- kb-frontmatter\nkind: entry-point\nkb-format: "0.9.2"\n-->\n# KB\n', "0.9.2"),
        ("<!-- kb-frontmatter\nkb-format: 2.0.0\n-->\n", "2.0.0"),
        ("<!-- kb-frontmatter\nkind: entry-point\n-->\n", None),
        ("# KB\n", None),
    ],
)
def test_a_comment_blocks_stamp_is_read_quotes_stripped(text: str, stamp: str | None) -> None:
    assert kb_migrate.superseded_stamp(text) == stamp


def test_an_index_line_that_is_not_an_object_is_refused_naming_its_line() -> None:
    with pytest.raises(MigrationError, match="line 2"):
        kb_migrate.chain("0.9.0", "1.0.0", {INDEX: '{"id": "a"}\n[1, 2]\n'})


def test_each_index_record_is_one_physical_line_that_reads_back_to_the_record() -> None:
    long = 'a long title: with "quotes", [brackets], {braces} # and hashes ' * 400
    records = [
        {"title": "first line\nsecond line\r\nthird\rfourth"},
        {"title": "ls\u2028ls ps\u2029ps nel\x85nel fs\x1cfs vt\vvt ff\fff"},
        {"title": long},
        {"title": "- a leading dash", "context": "  indented\n\tand tabbed  "},
        {"title": "c1 \x80 del \x7f bom \ufeff fffe \ufffe ffff \uffff <html> & more"},
    ]
    jsonl = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)

    stream = kb_migrate.chain("0.9.0", "1.0.0", {INDEX: jsonl}).files["kb-root/.index/claims.yaml"]

    assert len(stream.splitlines()) == len(records) and stream.endswith("\n")
    assert kb_yaml.parse_index(stream) == (records, [])


@pytest.mark.parametrize(
    ("from_version", "to_version", "message"),
    [
        ("0.9.0", "1.2.0", "no converter leads from 1.0.0 toward 1.2.0"),
        ("0.8.0", "1.0.0", "no converter leads from 0.8.0 toward 1.0.0"),
        ("1.0.0", "0.9.0", "1.0.0 is newer than 0.9.0, and nothing downgrades"),
        ("1.0", "1.0.0", "'1.0' is not a major.minor.patch version"),
        ("0.9.0", "01.0.0", "'01.0.0' is not a major.minor.patch version"),
    ],
)
def test_a_chain_it_cannot_walk_is_refused_naming_the_version(from_version: str, to_version: str, message: str) -> None:
    with pytest.raises(MigrationError) as raised:
        kb_migrate.chain(from_version, to_version, {})

    assert str(raised.value) == message


def test_a_chain_to_its_own_version_returns_the_files_unchanged() -> None:
    files = {DOCUMENT: "<!-- kb-frontmatter\nkind: leaf\n-->\n"}

    assert kb_migrate.chain("1.0.0", "1.0.0", files) == kb_migrate.Converted(files=files, obsolete=())


def test_an_indented_closer_ends_the_block_and_the_body_survives() -> None:
    """Closed at column 0 only, the lazy body ran on to the next `-->` in the file — here a marker's."""
    body = "\n# Body\n\n<!-- claim-quality: clm-bbbbbb -->\n"
    given = "<!-- kb-frontmatter\nkind: leaf\nclaims: [clm-aaaaaa]\n  -->\n" + body

    assert _convert(DOCUMENT, given) == "---\nkind: leaf\nclaims: [clm-aaaaaa]\n---\n" + body


def _unterminated(openers: int) -> str:
    """A document of `openers` block openers and no closer at line start."""
    return "<!-- kb-frontmatter\nkind: leaf\nclaims: [clm-aa1111]\n" * openers


def _elapsed(call) -> float:
    started = time.perf_counter()
    call()
    return time.perf_counter() - started


#: Far above the finder's measured cost at `_ADVERSARIAL_OPENERS` (~1 ms), far below the block
#: pattern's own `search` there (~2.5 s).
_BUDGET_SECONDS = 0.5
_ADVERSARIAL_OPENERS = 4_000


def test_a_document_of_openers_and_no_closer_converts_within_the_budget() -> None:
    text = _unterminated(_ADVERSARIAL_OPENERS)

    assert _elapsed(lambda: _convert(DOCUMENT, text)) < _BUDGET_SECONDS
    assert _elapsed(lambda: kb_migrate.superseded_stamp(text)) < _BUDGET_SECONDS
    assert _convert(DOCUMENT, text) == text


@pytest.mark.parametrize(
    "text",
    [
        "# Title\n\nprose\n",
        "<!-- kb-frontmatter\nkind: leaf\n-->\n\n# Body\n",
        "<!-- kb-frontmatter\nkind: leaf\n",
        "<!-- kb-frontmatter\nkind: index\n<!-- kb-frontmatter\nkind: leaf\n-->\n",
        "<!-- kb-frontmatter\nkind: leaf\n-->\n\n<!-- kb-frontmatter\nkind: index\n",
        "-->\n<!-- kb-frontmatter\nkind: leaf\n-->\n",
        "<!-- kb-frontmatter\n\n-->\n",
        "<!-- kb-frontmatter\nkind: leaf\n-->",
        "",
    ],
)
def test_the_one_pass_finder_returns_what_search_returns(text: str) -> None:
    found = kb_migrate._comment_block(text)
    expected = kb_migrate._COMMENT_BLOCK_RE.search(text)

    assert (None if found is None else (found.span(), found.group(1))) == (
        None if expected is None else (expected.span(), expected.group(1))
    )
    assert kb_migrate.holds_superseded_frontmatter(text) is (expected is not None)
