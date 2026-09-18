"""The record toolkit, and the one returned format the driver still reads itself.

Validation is parse-only, so the tests are two tables: shapes that must parse
into the right typed value, and malformed shapes that must be refused rather
than half-read.

The JSON record toolkit at the top is the layer under all of that, and it is the
substance of the module: its other consumer is ``kb_claimgraph.ask``, whose two
inference asks are built out of it. It was ``kb_survey.blocks`` while the design
document's own blocks were read off disk by the survey validator; the document
tree is derived from the sources now and the driver walks it. Its properties are
the model-facing ones — a closed vocabulary in both directions, markers matched
as whole lines, a line that ends at ``\\n`` and nowhere else, and a decode
failure that names a line and a column — and they are asserted here because they
survived the module that used to hold them.
"""

from pathlib import Path

import pytest

import kb_tools
from kb_tools.kb_driver import envelope

# ---------------------------------------------------------------------------
# The JSON record toolkit
# ---------------------------------------------------------------------------

PROBE_OPEN = "<<<KB-DRIVER-PROBE"
PROBE_CLOSE = "KB-DRIVER-PROBE"


def _probe(body: str) -> str:
    """A document carrying one probe block, prose on both sides of it."""
    return f"# Document\n\nSome prose.\n\n{PROBE_OPEN}\n{body}\n{PROBE_CLOSE}\n\nMore prose.\n"


def _extract(text: str) -> str:
    return envelope.extract_block(text, open_marker=PROBE_OPEN, close_marker=PROBE_CLOSE, label="probe")


def _decode(text: str) -> object:
    return envelope.parse_json_block(text, open_marker=PROBE_OPEN, close_marker=PROBE_CLOSE, label="probe")


@pytest.mark.parametrize(
    ("text", "complaint"),
    [
        pytest.param("nothing here at all", "no '<<<KB-DRIVER-PROBE' block", id="absent"),
        pytest.param(f"{PROBE_OPEN}\nbody\n", "never closed", id="unclosed"),
        pytest.param(
            f"{PROBE_OPEN}\na\n{PROBE_CLOSE}\n{PROBE_OPEN}\nb\n{PROBE_CLOSE}\n",
            "2 '<<<KB-DRIVER-PROBE' blocks; exactly one is required",
            id="two-blocks",
        ),
    ],
)
def test_the_marker_pair_owns_three_refusals_and_names_the_marker_in_each(text: str, complaint: str) -> None:
    """Absent, unclosed, duplicated. None of the three is read optimistically."""
    with pytest.raises(envelope.ParseError, match=complaint):
        _extract(text)


def test_a_block_named_in_prose_without_being_opened_does_not_open_one() -> None:
    """Markers are whole stripped lines, so a format can be discussed without being spoken."""
    with pytest.raises(envelope.ParseError, match="no .* block"):
        _extract(f"The block is called {PROBE_CLOSE} and it is written like this.\n")


def test_a_marker_with_a_tail_on_its_line_is_not_a_marker() -> None:
    """A marker is a whole line, not a line's prefix."""
    with pytest.raises(envelope.ParseError, match="no .* block"):
        _extract(f"# Document\n\n{PROBE_OPEN} []\n{PROBE_CLOSE}\n")


def test_an_indented_marker_still_opens_its_block() -> None:
    """Stripped, so leading whitespace a model adds is not a second grammar to learn."""
    assert _extract(f"  {PROBE_OPEN}\n[1]\n   {PROBE_CLOSE}\n") == "[1]"


def test_a_body_that_is_not_json_is_refused_with_the_decoders_own_line_and_column() -> None:
    """A decode failure is precise and repairable where a grammar complaint is a puzzle."""
    with pytest.raises(envelope.ParseError, match=r"not valid JSON: .*line \d+ column \d+"):
        _decode(_probe("a.md: mf:1-a"))


# `str.splitlines` breaks on all eight; the block grammar breaks on none of
# them. Each one silently turns one physical line into two accepted ones, which
# is how a marker line acquires an invisible tail.
_SPLITLINES_SEPARATORS = [" ", " ", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e", "\x85"]
_SEPARATOR_IDS = [
    "line-sep",
    "para-sep",
    "vertical-tab",
    "form-feed",
    "file-sep",
    "group-sep",
    "record-sep",
    "next-line",
]


@pytest.mark.parametrize("separator", _SPLITLINES_SEPARATORS, ids=_SEPARATOR_IDS)
def test_a_separator_inside_the_body_does_not_end_the_block_early(separator: str) -> None:
    """The body handed to the decoder is whole: a line ends at ``\\n`` and nowhere else."""
    body = f'["a{separator}b"]'

    assert _extract(_probe(body)) == body


@pytest.mark.parametrize("separator", _SPLITLINES_SEPARATORS, ids=_SEPARATOR_IDS)
def test_a_separator_cannot_smuggle_a_marker_onto_its_own_line(separator: str) -> None:
    """A marker preceded by a separator is a marker with a head, so it opens nothing."""
    with pytest.raises(envelope.ParseError, match="no .* block"):
        _extract(f"# Document\n\nprose{separator}{PROBE_OPEN}\n[]\n{PROBE_CLOSE}\n")


def test_a_crlf_document_still_reads_as_its_lines() -> None:
    """The one separator that is dropped, because it is half of the line ending."""
    assert _decode(_probe('["a", "b"]').replace("\n", "\r\n")) == ["a", "b"]


def test_the_key_vocabulary_is_closed_and_total_in_both_directions() -> None:
    """A key left out is refused by name, and so is a key added."""
    envelope.check_keys({"name": "a", "status": "ok"}, ("name", "status"), label="probe")

    with pytest.raises(envelope.ParseError, match="missing required key.*status"):
        envelope.check_keys({"name": "a"}, ("name", "status"), label="probe")
    with pytest.raises(envelope.ParseError, match="unknown key.*confidence"):
        envelope.check_keys({"name": "a", "status": "ok", "confidence": 0.9}, ("name", "status"), label="probe")


# ---------------------------------------------------------------------------
# The prose blocks beside the JSON
# ---------------------------------------------------------------------------

PROSE = "KB-DRIVER-PROBE-PROSE"

#: One sequence of each class. ``\sigma`` is not a JSON escape and fails loudly
#: inside a JSON string; ``\beta`` is one, decodes to a backspace, and fails
#: later and silently as a value that no longer matches anything. Both are
#: ordinary mathematics in the corpus this toolchain reads.
MATHEMATICS = "supercritical for $\\sigma < 1$, and $\\beta$ decay dominates"


def _blocks(*texts: str, numbers: tuple[int, ...] | None = None) -> str:
    chosen = numbers if numbers is not None else tuple(range(1, len(texts) + 1))
    return "".join(f"<<<{PROSE} {n}\n{text}\n{PROSE} {n}\n" for n, text in zip(chosen, texts, strict=True))


def _prose(text: str) -> envelope.ProseBlocks:
    return envelope.extract_prose_blocks(text, name=PROSE, label="probe")


def test_a_block_no_key_names_is_refused_rather_than_dropped() -> None:
    """Words the seat composed and nothing reads, on ``check_keys``' own argument.

    No surviving record declares a prose key, so *every* block a record carries
    is one no key names. The mathematics is here because it is what the
    transport exists for: a phrase carrying ``\\sigma`` reaches the refusal as
    itself, having gone through no escape grammar on the way.
    """
    blocks = _prose(_blocks(MATHEMATICS, "a second"))

    with pytest.raises(envelope.ParseError, match="named by no key"):
        blocks.check_exhausted()


@pytest.mark.parametrize(
    ("text", "complaint"),
    [
        pytest.param(f"<<<{PROSE} 1\nbody\n", "never closed", id="unclosed"),
        pytest.param(f"<<<{PROSE} 1\nbody\n{PROSE} 2\n", "opened as 1 is closed as 2", id="mismatched-number"),
        pytest.param(_blocks("a", "b", numbers=(1, 1)), "two .* blocks are numbered 1", id="duplicate-number"),
    ],
)
def test_a_malformed_prose_block_is_refused_and_named(text: str, complaint: str) -> None:
    with pytest.raises(envelope.ParseError, match=complaint):
        _prose(text)


def test_a_site_declaring_no_prose_keys_still_refuses_a_prose_block() -> None:
    """Which is what makes an empty declaration a check rather than an omission."""
    payload, blocks = envelope.parse_record(
        _probe('{"a": 1}') + _blocks("uninvited"),
        open_marker=PROBE_OPEN,
        close_marker=PROBE_CLOSE,
        prose_name=PROSE,
        label="probe",
    )

    assert payload == {"a": 1}
    with pytest.raises(envelope.ParseError, match="named by no key"):
        blocks.check_exhausted()


def test_a_levels_declaration_that_is_not_a_partition_is_refused_at_the_point_it_is_made() -> None:
    envelope.check_levels([envelope.Level("fine", ("a", "b"), json=("a",), prose=("b",))])

    for broken in (
        envelope.Level("gap", ("a", "b"), json=("a",), prose=()),
        envelope.Level("overlap", ("a",), json=("a",), prose=("a",)),
        envelope.Level("stray", ("a",), json=("a",), prose=("b",)),
    ):
        with pytest.raises(envelope.ParseError, match="do not partition"):
            envelope.check_levels([broken])


_KB_TOOLS_ROOT = Path(kb_tools.__file__).resolve().parent

#: A phrase from the extractor's own third refusal. Whoever writes a second
#: extractor writes this sentence again — which is what makes its file set a
#: usable proxy for "how many implementations of the grammar ship".
_REFUSAL_PHRASE = "blocks; exactly one is required"


def _shipped_sources() -> dict[str, str]:
    """Every shipped ``kb_tools`` module, keyed by its path relative to the package.

    ``_vendor/`` is out: it is fetched source this repo does not write. Test
    modules are out for the same reason a test may legitimately spell a refusal
    it is asserting on.
    """
    return {
        str(path.relative_to(_KB_TOOLS_ROOT)): path.read_text(encoding="utf-8")
        for path in sorted(_KB_TOOLS_ROOT.rglob("*.py"))
        if "_vendor" not in path.parts and "tests" not in path.parts
    }


def test_the_block_grammar_is_worded_in_exactly_one_place() -> None:
    """One implementation, so a strictness change to marker matching lands once."""
    spelling = sorted(name for name, source in _shipped_sources().items() if _REFUSAL_PHRASE in source)

    assert spelling == ["kb_driver/envelope.py"]


# ---------------------------------------------------------------------------
# The review VERDICT line
# ---------------------------------------------------------------------------


def test_verdict_parses_its_counts() -> None:
    verdict = envelope.parse_verdict("findings…\n\nVERDICT: critical=2 warning=0 note=13\n")

    assert (verdict.critical, verdict.warning, verdict.note) == (2, 0, 13)


def test_the_final_verdict_line_is_the_one_that_counts() -> None:
    text = (
        "quoting the contract:\nVERDICT: critical=0 warning=0 note=0\n\n"
        "findings…\nVERDICT: critical=1 warning=2 note=3"
    )

    assert envelope.parse_verdict(text).critical == 1


@pytest.mark.parametrize(
    "text",
    [
        "no verdict anywhere",
        "VERDICT: critical=1 warning=2",
        "VERDICT: critical=one warning=2 note=3",
        "VERDICT: warning=2 critical=1 note=3",
        "VERDICT: critical=1 warning=2 note=3 blocking=yes",
        "VERDICT:critical=1 warning=2 note=3",
    ],
)
def test_malformed_verdict_lines_are_refused(text: str) -> None:
    with pytest.raises(envelope.ParseError):
        envelope.parse_verdict(text)
