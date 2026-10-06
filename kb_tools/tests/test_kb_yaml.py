"""The KB YAML dialect against kbase's golden pairs and yaml.v3's writer rules.

The goldens (`fixtures/format-1.0.0/`, see its README) pin the reader and the writer together: a
`1.0.0` file reads to the values its `0.9.0` twin holds, and writing those values gives the `1.0.0`
bytes back. The remaining cases pin what the goldens do not reach: the double-quoted escapes, the
`? key` form, and each construct the reader refuses.
"""

import json
from pathlib import Path

import pytest

from kb_tools import kb_yaml
from kb_tools.kb_yaml import FlowList, KbYamlError, Number

GOLDENS = Path(__file__).parent / "fixtures" / "format-1.0.0"
RECORD_STEMS = ["kb-build-classification", "kb-build-node-pass", "kb-build-unmarked"]
INDEX_NAMES = ["cites", "claims", "depends-on", "strengthen-by", "subtree-aggregates", "supported-by"]

# The frontmatter values kbase's goldens hold for the two leaves, and the entry point's kind with
# its stamp.
FRONTMATTER_VALUES = {
    "a.md": {"kind": "leaf", "no-claim": "prose"},
    "b/c.md": {
        "kind": "leaf",
        "claims": ["clm-0dtsyu"],
        "experiment-nodes": [
            {"exp-id": "exp-k3m9q2", "status": "run", "strengthens": [{"clm-0dtsyu": 0.8}]},
            {"exp-id": "exp-p4n8r1", "status": "pending"},
        ],
        "support-nodes": [
            {"sup-id": "sup-7x1a0c", "supports": [{"clm-0dtsyu": 0.5}, {"clm-2h6i01": "*pending*"}]},
            {"sup-id": "sup-w2v6t5"},
        ],
    },
    "entry-point.md": {"kind": "entry-point", "kb-format": "1.0.0"},
}


def _read(path: Path) -> str:
    with path.open(encoding="utf-8", newline="") as handle:
        return handle.read()


@pytest.mark.parametrize("stem", RECORD_STEMS)
def test_a_record_golden_reads_to_its_json_twin_and_writes_back_byte_equal(stem: str) -> None:
    values = json.loads(_read(GOLDENS / "0.9.0" / f"{stem}.json"))
    text = _read(GOLDENS / "1.0.0" / f"{stem}.yaml")

    assert kb_yaml.parse(text) == values
    assert kb_yaml.dump(values) == text


@pytest.mark.parametrize("name", INDEX_NAMES)
def test_an_index_golden_reads_to_its_jsonl_twin_and_writes_back_byte_equal(name: str) -> None:
    jsonl = _read(GOLDENS / "0.9.0" / "kb-root" / ".index" / f"{name}.jsonl")
    values = [json.loads(line) for line in jsonl.splitlines()]
    text = _read(GOLDENS / "1.0.0" / "kb-root" / ".index" / f"{name}.yaml")

    records, problems = kb_yaml.parse_index(text)

    assert (records, problems) == (values, [])
    assert "".join(kb_yaml.index_line(record) for record in values) == text


@pytest.mark.parametrize("relpath", sorted(FRONTMATTER_VALUES))
def test_a_golden_frontmatter_block_reads_to_the_stated_values_and_writes_back_byte_equal(relpath: str) -> None:
    text = _read(GOLDENS / "1.0.0" / "kb-root" / relpath)
    span = kb_yaml.find_frontmatter(text)
    assert span is not None

    values = kb_yaml.parse(text[span.body_start : span.body_end])
    lines = [line for key, value in values.items() for line in kb_yaml.dump_field(key, value)]

    assert values == FRONTMATTER_VALUES[relpath]
    assert kb_yaml.frontmatter(lines) == text[: span.close_start + len("---")]


def test_the_up_link_begins_where_the_frontmatter_ends() -> None:
    text = _read(GOLDENS / "1.0.0" / "kb-root" / "a.md")
    span = kb_yaml.find_frontmatter(text)
    assert span is not None
    assert text[span.end :].startswith("[\u2191 KB](entry-point.md)\n")


# kbase's awkward-string list (kbase `internal/migrate/scalars_test.go`, `awkwardStrings`) with
# each one's scalar as written. These bytes are DERIVED from yaml.v3 v3.0.5's double-quoted writer
# (`emitterc.go`, `yaml_emitter_write_double_quoted_scalar`; `yamlprivateh.go`, `is_printable`),
# not measured from kbase; a kbase golden of `RenderFrontmatterField` over this list, once kbase
# supplies one, replaces them.
AWKWARD_STRINGS = [
    ("", '""'),
    ("y", '"y"'),
    ("Y", '"Y"'),
    ("n", '"n"'),
    ("yes", '"yes"'),
    ("Yes", '"Yes"'),
    ("NO", '"NO"'),
    ("on", '"on"'),
    ("Off", '"Off"'),
    ("true", '"true"'),
    ("False", '"False"'),
    ("null", '"null"'),
    ("Null", '"Null"'),
    ("~", '"~"'),
    ("0", '"0"'),
    ("1", '"1"'),
    ("-1", '"-1"'),
    ("1.5", '"1.5"'),
    ("1e5", '"1e5"'),
    ("0x1F", '"0x1F"'),
    ("0o17", '"0o17"'),
    ("1_000", '"1_000"'),
    (".inf", '".inf"'),
    ("-.Inf", '"-.Inf"'),
    (".nan", '".nan"'),
    ("2024-01-01", '"2024-01-01"'),
    ("12:30", '"12:30"'),
    ("1abc", '"1abc"'),
    ("9lives", '"9lives"'),
    ("a'b", '"a\'b"'),
    ('a"b', r'"a\"b"'),
    ("back\\slash", r'"back\\slash"'),
    ("tab\there", r'"tab\there"'),
    ("line\nbreak", r'"line\nbreak"'),
    ("crlf\r\nx", r'"crlf\r\nx"'),
    ("trailing ", '"trailing "'),
    ("  leading", '"  leading"'),
    ("#hash", '"#hash"'),
    ("a #b", '"a #b"'),
    ("a: b", '"a: b"'),
    ("- dash", '"- dash"'),
    ("[x]", '"[x]"'),
    ("{y}", '"{y}"'),
    ("*star", '"*star"'),
    ("&anchor", '"&anchor"'),
    ("!tag", '"!tag"'),
    ("%pct", '"%pct"'),
    ("@at", '"@at"'),
    ("`tick", '"`tick"'),
    ("|pipe", '"|pipe"'),
    (">gt", '">gt"'),
    ("?q", '"?q"'),
    ("\u00e9", '"\u00e9"'),
    ("\u65e5\u672c\u8a9e", '"\u65e5\u672c\u8a9e"'),
    ("emoji \U0001f600", r'"emoji \U0001F600"'),
    ("line\u2028separator", r'"line\Lseparator"'),
    ("next\x85line", r'"next\Nline"'),
    ("\v\f", r'"\v\f"'),
    ("clm-abc123", "clm-abc123"),
    ("kb-root/a.md", "kb-root/a.md"),
    ("a/b_c.d-e", "a/b_c.d-e"),
    ("kind", "kind"),
    ("*pending*", '"*pending*"'),
]
LINE_BREAKS = "\r\n\x85\u2028\u2029"


@pytest.mark.parametrize(("value", "written"), AWKWARD_STRINGS)
def test_an_awkward_string_is_written_by_yaml_v3s_rules_as_a_value_and_as_a_key(value: str, written: str) -> None:
    assert kb_yaml.dump_field("k", value) == [f"k: {written}"]
    key_lines = [f"? {written}", ": v"] if any(ch in LINE_BREAKS for ch in value) else [f"{written}: v"]
    assert kb_yaml.dump_field(value, "v") == key_lines
    assert kb_yaml.parse(kb_yaml.dump({"k": value, value: "v"})) == {"k": value, value: "v"}


@pytest.mark.parametrize(
    ("value", "written"),
    [
        ('\ufeffa \u00e9"\n', r'"\uFEFF\x61\x20\xE9\"\n"'),
        ("x\ufeffy", r'"x\uFEFFy"'),
    ],
    ids=["leading", "inner"],
)
def test_a_leading_byte_order_mark_escapes_every_character_and_an_inner_one_only_itself(
    value: str, written: str
) -> None:
    assert kb_yaml.dump_field("k", value) == [f"k: {written}"]
    assert kb_yaml.parse(kb_yaml.dump({"k": value})) == {"k": value}


LONG_KEY = "k" * 129


@pytest.mark.parametrize(
    ("values", "text"),
    [
        ({"k" * 128: "v"}, "k" * 128 + ": v\n"),
        ({LONG_KEY: "v"}, f"? {LONG_KEY}\n: v\n"),
        ({"\u00e9" * 64: 1}, '"' + "\u00e9" * 64 + '": 1\n'),
        ({"\u00e9" * 65: 1}, '? "' + "\u00e9" * 65 + '"\n: 1\n'),
        ({LONG_KEY: ["a", "b"]}, f"? {LONG_KEY}\n: - a\n  - b\n"),
        (
            {"leaves": {LONG_KEY: {"state": "landed", "claims": [], "verdicts": [{"line": 3}]}}},
            f"leaves:\n  ? {LONG_KEY}\n  : state: landed\n    claims: []\n    verdicts:\n      - line: 3\n",
        ),
        ({"a\nb": {"x": 1}}, '? "a\\nb"\n: x: 1\n'),
    ],
    ids=["128-bytes", "129-bytes", "128-bytes-of-two-byte-chars", "130-bytes", "list-value", "nested", "break"],
)
def test_a_key_over_128_bytes_or_holding_a_break_takes_the_complex_form(values: dict, text: str) -> None:
    assert kb_yaml.dump(values) == text
    assert kb_yaml.parse(text) == values


def test_a_flow_list_reads_as_a_flow_list_and_a_block_list_as_a_list() -> None:
    text = 'ids: [clm-a, "x y", 2]\nempty: []\nblock:\n  - a\n  - - b\n'

    values = kb_yaml.parse(text)

    assert values == {"ids": ["clm-a", "x y", 2], "empty": [], "block": ["a", ["b"]]}
    assert type(values["ids"]) is FlowList and type(values["empty"]) is FlowList
    assert type(values["block"]) is list
    assert kb_yaml.dump(values) == text


def test_a_number_keeps_its_text_and_a_typed_scalar_its_type() -> None:
    values = {"a": Number("1e-05"), "b": Number("2.50"), "c": True, "d": 1, "e": 0.5, "f": None, "g": {}}

    text = kb_yaml.dump(values)

    assert text == "a: 1e-05\nb: 2.50\nc: true\nd: 1\ne: 0.5\nf: null\ng: {}\n"
    read = kb_yaml.parse(text)
    assert read == {"a": 1e-05, "b": 2.5, "c": True, "d": 1, "e": 0.5, "f": None, "g": {}}
    assert [type(read[key]) for key in "cde"] == [bool, int, float]


@pytest.mark.parametrize("value", [Number("1.2.3"), float("nan"), float("inf")], ids=["number", "nan", "inf"])
def test_a_value_with_no_dialect_form_is_refused_by_the_writer(value: object) -> None:
    with pytest.raises(ValueError):
        kb_yaml.dump({"k": value})


@pytest.mark.parametrize(
    ("text", "line", "named"),
    [
        ("a: 1\nb: &x v\n", 2, "anchor"),
        ("a: 1\nb: *pending*\n", 2, "alias"),
        ("a: 1\nb: !!str v\n", 2, "tag"),
        ("a: 1\nb: |\n  text\n", 2, "block scalar"),
        ("a: 1\nb: >\n  text\n", 2, "block scalar"),
        ("a: 1\nb: 'v'\n", 2, "single-quoted"),
        ("a: 1\nb: one\n  two\n", 3, "continued"),
        ('a: 1\nb: "one\n  two"\n', 2, "continued"),
        ("a: 1\nb: {c: 1}\n", 2, "non-empty flow mapping"),
        ("a: 1\nb: [[c]]\n", 2, "non-scalar"),
        ("a: 1\nb: [{c: 1}]\n", 2, "non-scalar"),
        ("a: 1\nb: 2\na: 3\n", 3, "duplicate key"),
        ("a: 1\n---\nb: 2\n", 2, "document marker"),
        ("a: 1\nb: .inf\n", 2, "non-finite"),
        ("a: 1\nb: -.NaN\n", 2, "non-finite"),
        ("a: 1\nb: 0x1F\n", 2, "hex"),
        ("a: 1\nb: 0o17\n", 2, "octal"),
        ("a: 1\nb: 017\n", 2, "octal"),
        ("a: 1\nb: c: d\n", 2, "': '"),
        ("a: 1\nb: c #d\n", 2, "' #'"),
        ("a: 1\nb: @c\n", 2, "opening with '@'"),
        ("a:\n\tb: 1\n", 2, "tab in indentation"),
        ("a: 1\nb: c\u2028d\n", 2, "line break"),
        ('a: 1\nb:\n  - "abc\n', 3, "continued onto a second line"),
        ('x: 1\n? k\n: "abc\n', 3, "continued onto a second line"),
    ],
    ids=[
        "anchor",
        "alias",
        "tag",
        "literal-block-scalar",
        "folded-block-scalar",
        "single-quoted",
        "plain-continued",
        "double-quoted-continued",
        "flow-mapping",
        "flow-list-in-flow-list",
        "flow-mapping-in-flow-list",
        "duplicate-key",
        "document-marker",
        "inf",
        "nan",
        "hex",
        "octal-1.2",
        "octal-1.1",
        "plain-holding-colon-space",
        "plain-holding-space-hash",
        "plain-opening-with-indicator",
        "tab-indentation",
        "raw-line-separator",
        "double-quoted-unclosed-in-list-item",
        "double-quoted-unclosed-after-value-indicator",
    ],
)
def test_a_construct_outside_the_dialect_is_refused_naming_its_line(text: str, line: int, named: str) -> None:
    with pytest.raises(KbYamlError) as raised:
        kb_yaml.parse(text)

    assert raised.value.line == line
    assert named in raised.value.detail


def test_one_leading_document_marker_opens_the_document() -> None:
    assert kb_yaml.parse("---\na: 1\n") == {"a": 1}


def test_a_bad_index_line_is_returned_beside_the_records_rather_than_raised() -> None:
    text = '--- {"a": 1}\n{"b": 2}\n\n--- [1]\n--- {bad\n--- {"c": NaN}\n--- {"d": "\\u2028"}\n'

    records, problems = kb_yaml.parse_index(text)

    assert records == [{"a": 1}, {"d": "\u2028"}]
    assert [problem.line for problem in problems] == [2, 4, 5, 6]


def test_an_index_line_escapes_what_a_stream_reader_takes_as_a_break() -> None:
    record = {"s": 'a"b\\c\n\t\x01\u00e9', "breaks": "\u2028\u2029\x85\x7f\ufeff\ufffe\uffff", "n": None}

    line = kb_yaml.index_line(record)

    assert line == (
        '--- {"s": "a\\"b\\\\c\\n\\t\\u0001\u00e9", '
        '"breaks": "\\u2028\\u2029\\u0085\\u007f\\ufeff\\ufffe\\uffff", "n": null}\n'
    )
    assert kb_yaml.parse_index(line) == ([record], [])


# kbase's `TestConverterFindsFrontmatterAsKBDoes` documents, each with whether kbase's
# `kb.FindFrontmatter` finds frontmatter in it.
@pytest.mark.parametrize(
    ("text", "found"),
    [
        ("# T\n", False),
        ("---\n---\n", True),
        ("---\n\n---\n", True),
        ("---\nkind: leaf\n---\n", True),
        ("---\r\nkind: leaf\r\n---\r\n", True),
        ("---\n\nkind: leaf\n---\n", True),
        ("---\nkey: [unclosed\n---\n", True),
        ("---\nSome notes: with: colons\n---\n", False),
        ("---\nPlain prose.\n---\n", False),
        ("---\n- a list\n---\n", False),
        ("---\n  indented: x\n---\n", False),
        ("---\nKind: leaf\n---\n", False),
        ('---\nkb-format: "1.0.0"\n---\n', True),
        ("---\nunclosed: true\n", False),
        ("--- a rule\n", False),
    ],
)
def test_frontmatter_is_found_where_kbase_finds_it(text: str, found: bool) -> None:
    assert (kb_yaml.find_frontmatter(text) is not None) is found


def test_a_crlf_frontmatter_span_excludes_the_breaks_around_its_body() -> None:
    text = "---\r\nkind: leaf\r\n---\r\n[\u2191 KB](entry-point.md)\r\n"

    span = kb_yaml.find_frontmatter(text)

    assert span is not None
    assert text[span.body_start : span.body_end] == "kind: leaf"
    assert text[span.close_start : span.close_start + 3] == "---"
    assert text[span.end :].startswith("[\u2191 KB]")
