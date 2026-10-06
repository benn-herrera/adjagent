"""Claim discovery: the labelled render, the paragraph asks, placement, and the run end to end.

**Every check here runs against a fixed inference at the
:class:`~kb_tools.kb_claimgraph.letters.LetterReader` seam**: the fake receives
each question the stage composed and answers it by the leaf and the paragraph it
names. The asks' grouping, placement, the per-leaf write and the run's own exit
condition are exercised and none of it needs a model. One check depends on the
wording of a prompt, and that is its job: the paragraph ask's bytes are pinned
over a leaf of their own.

**Nothing here asserts agreement between two live runs**, and nothing could: the
answers are fixed, so what these checks establish is that the mechanism holds
answers fixed — never that a model would give the same ones twice.

**The fixture is shaped by measurement, not by convenience.** Over the survey
corpus, 74 display-maths fences carry 6 blank lines before them and 59 open
mid-sentence, so the leaf below writes its fence flush against the prose it
interrupts — which is what makes a paragraph crossing a fence findable, and what
a fixture with a blank line on each side would have hidden. One second fence
*is* blank-separated, because that minority is where the paragraph rule bites.

The consuming repository is stood up the way a consumer's is: the real runner
snippet, imported by the line the installer writes, over the installed package.
"""

import tomllib
from collections import Counter
from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest

from kb_tools import kb_index_lib, kb_pipeline, kb_schema, kb_util, refresh_kb_metadata, verify_kb_metadata
from kb_tools.kb_claimgraph import ask, discover, graph, identify, inventory, label, letters, tree
from kb_tools.kb_claimgraph.assemble import BLOCKLESS_REASON
from kb_tools.kb_claimgraph.build import build
from kb_tools.kb_driver import prompt_templates
from kb_tools.kb_write import ops, render
from kb_tools.tests._claimgraph_consumer import install_claimgraph_consumer
from kb_tools.tests._fixture_templates import compose_from_fixture_templates
from kb_tools.tests._shared_builds import copy_build, held_unchanged

# ---------------------------------------------------------------------------
# A four-leaf corpus: one author-marked block, one prose document stating
# results across a hard wrap and carrying two maths fences, and one stating none.
# ---------------------------------------------------------------------------

_ENTRY_POINT = "# Knowledge Base\n\n- [Vol](vol/index.md)\n"
_VOLUME_INDEX = (
    "[↑ Knowledge Base](../entry-point.md)\n\n# Vol\n\n"
    "- [Alpha](alpha.md)\n- [Epsilon](epsilon.md)\n- [Zeta](zeta.md)\n"
)
_UPLINK = "[↑ Vol](index.md)"

_ALPHA = f"""{_UPLINK}

# Alpha

> <span id="thm:alpha">**theorem**</span>
>
> **Theorem 1** (Alpha result). *Alpha holds for every admissible state.*

Alpha is argued directly.
"""

#: One sequence of each class a JSON string cannot carry raw. ``\sigma`` is not
#: a JSON escape and fails loudly inside JSON; ``\beta`` is one, decodes to a
#: backspace, and fails later and silently. Nothing here is JSON any more; what
#: the fixture pins is that the author's bytes reach the KB as written.
_NOT_AN_ESCAPE = "\\sigma"
_IS_AN_ESCAPE = "\\beta"

# The first fence is flush against the sentence it interrupts, which is how this
# corpus writes 59 of its 74; the second is blank-separated, which is how it
# writes the other 6. Both paragraphs below cross a hard wrap, which is the case
# the write API's locator matching exists for.
_EPSILON = f"""{_UPLINK}

# Epsilon

The author marked nothing here. The admissible configuration set is closed
under the operations of the previous section, and every admissible
configuration therefore admits a stationary point. See Fig. 3 for the picture.

The rate parameter satisfies
``` math
\\lambda = \\tfrac{{1}}{{2}} \\mu^2 \\label{{eq:rate}}
```
from which the second result follows: the stationary point is unique whenever
the rate parameter is strictly positive.

An unrelated identity ${_NOT_AN_ESCAPE} < 1$ with ${_IS_AN_ESCAPE} > 0$ is recorded separately.

``` math
\\mu = \\sigma^2 \\label{{eq:mu}}
```

The section ends there.
"""

_ZETA = f"""{_UPLINK}

# Zeta

This section fixes notation. The symbol used throughout for the rate parameter
is written as it is in the source, and nothing is asserted about it here.
"""

_TREE = {
    "entry-point.md": _ENTRY_POINT,
    "vol/index.md": _VOLUME_INDEX,
    "vol/alpha.md": _ALPHA,
    "vol/epsilon.md": _EPSILON,
    "vol/zeta.md": _ZETA,
}

#: The labels the render gives Epsilon. Read off the render in
#: ``test_the_render_labels_one_sentence_per_line``, and named here so every
#: later check states a label rather than an ordinal nobody can follow.
_CLOSURE_LABEL = "S2"

#: Epsilon's paragraphs by their label ranges. The second runs across the fence
#: flush against the prose it interrupts; the blank-separated fence is a
#: paragraph of its own. The heading carries no label, a heading being no
#: sentence of the leaf's prose.
_OPENING = "S1-S3"
_RATE = "S4-S8"
_IDENTITY = "S9"
_SEPARATED_FENCE_LOCATOR = "S10-S12"
_CLOSING = "S13"

#: Each title is its paragraph's first sentence that could open a claim.
_OPENING_TITLE = "The author marked nothing here."
_RATE_TITLE = "The rate parameter satisfies"

_CLAIM = ask.ParagraphLetter.CLAIM.value

#: What a run over this corpus is told, by ``(leaf, paragraph)``. Anything else is not a claim.
_ANSWERS: dict[tuple[str, str], str] = {
    ("vol/epsilon.md", _OPENING): _CLAIM,
    ("vol/epsilon.md", _RATE): _CLAIM,
}


class FixedReader:
    """A :class:`letters.LetterReader` answering from a table keyed by leaf and paragraph.

    ``stop_on`` names a leaf whose first ask never completes. ``questions`` is
    every question put, as the stage composed it.
    """

    def __init__(self, answers: Mapping[tuple[str, str], str] | None = None, *, stop_on: str | None = None):
        self._answers = _ANSWERS if answers is None else answers
        self._stop_on = stop_on
        self.questions: list[letters.LetterQuestion] = []

    def __call__(self, question: letters.LetterQuestion) -> letters.Reply:
        if question.group == self._stop_on:
            raise ask.AskError("inference-failed", f"{question.group}: the call never completed")
        self.questions.append(question)
        return letters.Reply(text=self._answers.get((question.group, question.item), "B"))

    def groups(self) -> list[str]:
        return list(dict.fromkeys(question.group for question in self.questions))


# ---------------------------------------------------------------------------
# The consuming repository, and the declared pass over it
# ---------------------------------------------------------------------------


@pytest.fixture
def consumer(tmp_path: Path) -> Path:
    return install_claimgraph_consumer(tmp_path / "consumer", _TREE)


def _scratch(repo: Path) -> Path:
    return repo / kb_util.scratch_dirname() / "claimgraph"


@pytest.fixture(scope="module")
def declared_build(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    repo = install_claimgraph_consumer(tmp_path_factory.mktemp("cinf-declared") / "consumer", _TREE)
    outcome = build(kb_root=repo / "kb-root", repo_root=repo, scratch=_scratch(repo))
    assert not outcome.failed, outcome.lines()
    with held_unchanged(repo, name="cinf declared"):
        yield repo


@pytest.fixture
def declared(declared_build: Path, tmp_path: Path) -> Path:
    """This test's own copy of ``consumer`` after the declared pass has run and its gates are green."""
    return copy_build(declared_build, tmp_path / "consumer")


def _discover(repo: Path, reader: letters.LetterReader):
    return discover.build(kb_root=repo / "kb-root", repo_root=repo, scratch=_scratch(repo), reader=reader)


def _texts(kb_root: Path) -> dict[str, str]:
    return {path: document.text for path, document in tree.read(kb_root).documents.items()}


def _reading(repo: Path, path: str) -> identify.Reading:
    documents = tree.read(repo / "kb-root")
    return identify.reading_of(documents.documents[path], inventory.scan(documents))


def _span(rendered: label.Render, locator: str) -> label.Span:
    """The run of sentences a label or label range (``S3``, ``S3-S5``) names, read off the render."""
    first, _, last = locator.partition("-")
    labels = [sentence.label for sentence in rendered.sentences]
    return label.Span(sentences=rendered.sentences[labels.index(first) : labels.index(last or first) + 1])


def _slice(repo: Path, locator: str, *, path: str = "vol/epsilon.md") -> str:
    """The bytes a locator names — the tool's own slice."""
    return _span(_reading(repo, path).render, locator).excerpt


def _entries(repo: Path):
    register = repo / "kb-root" / "vol" / "claim-quality.md"
    return kb_index_lib.parse_claim_quality_file(register, repo / "kb-root")


def _judged(reading: identify.Reading, yes: set[str]) -> identify.Identification:
    """``reading`` judged with the asked paragraphs named in ``yes`` a claim and every other one not."""
    return identify.judge(reading, [(asked, asked.name in yes) for asked in identify.asked_paragraphs(reading)])


# ---------------------------------------------------------------------------
# 1 — the entry condition and the scope
# ---------------------------------------------------------------------------


def test_the_declared_pass_records_every_leaf_unread_and_nothing_else(declared: Path):
    """The node pass's scope is the record's leaves, and the declared pass lists every one of them."""
    record = kb_pipeline.read_node_pass(declared)

    assert record is not None
    assert sorted(record.leaves) == ["vol/alpha.md", "vol/epsilon.md", "vol/zeta.md"]
    assert {entry.state for entry in record.leaves.values()} == {kb_pipeline.ReadState.UNREAD}


def test_a_leaf_hosting_a_block_is_read_too(declared: Path):
    """THESIS gap 1 is any claim constructed in prose, with no exception for a leaf that also has blocks."""
    reader = FixedReader()
    assert not _discover(declared, reader).failed
    assert reader.groups() == ["vol/alpha.md", "vol/epsilon.md", "vol/zeta.md"]


def test_a_leaf_the_record_holds_landed_is_not_asked_again(declared: Path):
    record = kb_pipeline.read_node_pass(declared)
    kb_pipeline.write_node_pass(
        declared,
        record.with_leaf(
            "vol/zeta.md",
            kb_pipeline.LeafEntry(state=kb_pipeline.ReadState.LANDED, outcome=kb_pipeline.LeafOutcome.NO_CLAIM),
        ),
    )
    reader = FixedReader()
    assert not _discover(declared, reader).failed
    assert "vol/zeta.md" not in reader.groups()


def test_a_run_with_no_record_stops_before_the_ask(consumer: Path):
    """No declared pass has run, so nothing says which leaves are this pass's."""
    reader = FixedReader()
    report = _discover(consumer, reader)
    assert report.failed
    assert any("node-pass-record" in line for line in report.lines()), report.lines()
    assert reader.questions == []


# ---------------------------------------------------------------------------
# 2 — the labelled render, which is what the seat is shown
# ---------------------------------------------------------------------------


def test_the_render_labels_one_sentence_per_line_with_the_wraps_collapsed(declared: Path):
    rendered = _reading(declared, "vol/epsilon.md").render
    labelled = {sentence.label: sentence.text for sentence in rendered.sentences}

    assert "# Epsilon" not in labelled.values(), "a heading is shown unlabelled: it states nothing"
    assert labelled["S1"] == "The author marked nothing here."
    assert labelled[_CLOSURE_LABEL].startswith("The admissible configuration set is closed under")
    assert labelled[_CLOSURE_LABEL].endswith("admits a stationary point.")
    assert "\n" not in labelled[_CLOSURE_LABEL]
    assert labelled["S4"] == "The rate parameter satisfies"
    assert labelled["S5"] == "``` math"


def test_an_abbreviation_followed_by_a_numeral_is_not_a_sentence_end(declared: Path):
    """``Fig. 3`` is what a naive split on a full stop and a space gets wrong."""
    labelled = {sentence.label: sentence.text for sentence in _reading(declared, "vol/epsilon.md").render.sentences}
    assert labelled["S3"] == "See Fig. 3 for the picture."


def test_inline_maths_carrying_a_decimal_point_is_not_two_sentences():
    """``$x = 1.5$`` is one sentence's worth of maths, and the split must not enter it."""
    body = "---\nkind: leaf\n---\n\nThe bound is $x = 1.5$ here. A second sentence follows.\n"
    rendered = label.render(body)

    assert [sentence.text for sentence in rendered.sentences] == [
        "The bound is $x = 1.5$ here.",
        "A second sentence follows.",
    ]


def test_navigation_and_the_frontmatter_block_carry_no_label(declared: Path):
    """What the render never offers, no paragraph ask names."""
    reading = _reading(declared, "vol/epsilon.md")
    rendered = reading.render

    assert _UPLINK in rendered.text
    assert "no-claim:" in rendered.text
    assert all(_UPLINK not in sentence.text for sentence in rendered.sentences)
    assert all("no-claim:" not in sentence.text for sentence in rendered.sentences)
    assert min(sentence.line for sentence in rendered.sentences) > 0


def test_a_fence_flush_against_its_prose_stays_inside_that_paragraph(declared: Path):
    """The measured majority: a paragraph crossing such a fence is findable."""
    reading = _reading(declared, "vol/epsilon.md")
    span = _span(reading.render, _RATE)

    assert len(span.paragraphs) == 1
    assert "``` math" in span.excerpt
    assert ops.excerpt_lines(reading.text, span.excerpt) == (span.line,)


def test_a_blank_separated_fence_is_a_paragraph_of_its_own(declared: Path):
    """The measured minority, and the reason the paragraph rule is stated over blank lines.

    ``ops.excerpt_lines`` joins each body line's collapsed text with single
    spaces, so a blank line puts two into the haystack and no slice can cross
    one. A paragraph here is exactly a run of lines a slice can span, which is
    what makes the paragraph rule a findability rule.
    """
    reading = _reading(declared, "vol/epsilon.md")
    separated = _span(reading.render, _SEPARATED_FENCE_LOCATOR)

    assert len(separated.paragraphs) == 1
    assert ops.excerpt_lines(reading.text, separated.excerpt) == (separated.line,)

    crossing = _span(reading.render, f"{_IDENTITY}-S12")
    assert len(crossing.paragraphs) > 1
    assert ops.excerpt_lines(reading.text, crossing.excerpt) == ()


def test_a_heading_opens_a_paragraph_of_its_own(declared: Path):
    """So a paragraph cannot run out of a stated result and into the section holding it."""
    reading = _reading(declared, "vol/epsilon.md")
    rendered = label.render(reading.body, fences=reading.fences)
    assert rendered.sentences[0].text == "# Epsilon"
    assert len(_span(rendered, "S1-S2").paragraphs) == 2


# ---------------------------------------------------------------------------
# 3 — the asks: one group per leaf, one question per paragraph
# ---------------------------------------------------------------------------


def test_each_ask_shows_its_leaf_alone_and_names_one_paragraph(declared: Path, monkeypatch: pytest.MonkeyPatch):
    """The leaf's render is the group's context, and no other document's words are in front of the seat."""
    monkeypatch.setenv(letters.READER_CONCURRENCY_ENV, "1")  # the reader records calls in arrival order
    reader = FixedReader()
    assert not _discover(declared, reader).failed
    epsilon = [question for question in reader.questions if question.group == "vol/epsilon.md"]

    assert [question.item for question in epsilon] == [_OPENING, _RATE, _IDENTITY, _CLOSING]
    assert {question.offered for question in epsilon} == {tuple(ask.ParagraphLetter)}
    for question in epsilon:
        assert f"{_CLOSURE_LABEL}: The admissible configuration set" in question.prompt
        assert "Alpha holds for every admissible state" not in question.prompt
    assert all(question.kind is letters.Kind.PARAGRAPH for question in reader.questions)


def test_the_prompt_shows_the_body_with_an_earlier_pass_s_markers_taken_off(declared: Path):
    marked = "vol/alpha.md"
    leaf = declared / "kb-root" / marked
    leaf.write_text(leaf.read_text(encoding="utf-8").rstrip("\n") + " <!-- claim-quality: clm-aaaaaa -->\n", "utf-8")
    reading = _reading(declared, marked)
    assert "clm-aaaaaa" in reading.text and "clm-aaaaaa" not in reading.body
    assert len(reading.text.splitlines()) == len(reading.body.splitlines())
    assert "clm-aaaaaa" not in reading.render.text


def test_a_call_that_never_completes_stops_the_stage_with_nothing_written_for_its_leaf(declared: Path):
    before = (declared / "kb-root" / "vol" / "epsilon.md").read_text(encoding="utf-8")
    report = _discover(declared, FixedReader(stop_on="vol/epsilon.md"))

    assert report.failed and any("inference-failed" in line for line in report.lines())
    assert (declared / "kb-root" / "vol" / "epsilon.md").read_text(encoding="utf-8") == before
    assert len(_entries(declared)) == 1, "the register carries the declared pass's entry and nothing else"
    assert kb_pipeline.read_node_pass(declared).leaves["vol/epsilon.md"].state is kb_pipeline.ReadState.UNREAD


def test_each_leaf_s_ask_record_lands_where_the_stage_is_told(declared: Path, tmp_path: Path):
    records = tmp_path / "asks"
    report = discover.build(
        kb_root=declared / "kb-root",
        repo_root=declared,
        scratch=_scratch(declared),
        reader=FixedReader(),
        record_dir=records,
    )
    assert not report.failed, report.lines()
    assert sorted(path.name for path in records.iterdir()) == [
        letters.group_record_path(records, kind=letters.Kind.PARAGRAPH, group=leaf).name
        for leaf in ("vol/alpha.md", "vol/epsilon.md", "vol/zeta.md")
    ]
    assert any("stage-C-asks" in line and "items=6" in line for line in report.lines()), report.lines()


#: Fixture templates for the paragraph ask, standing in for the working ones so
#: the goldens below pin the composer and move with nothing a wording edit
#: touches. They carry every slot kind the working template does: per-call
#: ``dyn.`` slots, composer-filled letters, and the ``correction`` alternative,
#: whose fragment ends without a newline.
_FIXTURE_TEMPLATES = {
    ask.LETTER_TEMPLATES[letters.Kind.PARAGRAPH]: (
        "Letters @!letter-claim!@ and @!letter-not-a-claim!@.\n"
        "In @!dyn.document!@:\n"
        "@!dyn.body!@\n"
        "Item @!dyn.paragraph!@:\n"
        "@!dyn.paragraph-text!@\n"
        "Answer @!letter-claim!@ or @!letter-not-a-claim!@.@!correction!@\n"
    ),
    prompt_templates.ALTERNATIVES[ask.LETTER_CORRECTION]: "\n\nAgain; it read:\n@!dyn.returned!@\nOne letter.",
}

_GOLDEN_LEAF = ask.ParagraphGroup(
    document="vol/one.md",
    body="# One\n\nS1: It contracts whenever $\\frac{1}{2} k < 1$.\n\nS2: Notation.\n",
)
_GOLDEN_PARAGRAPHS = (
    ask.ParagraphItem("S1", "S1: It contracts whenever $\\frac{1}{2} k < 1$.\n"),
    ask.ParagraphItem("S2", "S2: Notation.\n"),
)

#: Every ask of the leaf opens with these bytes: the group's slots, filled once
#: and identically, end before the first item slot.
_GOLDEN_PREFIX = """\
Letters A and B.
In vol/one.md:
# One

S1: It contracts whenever $\\frac{1}{2} k < 1$.

S2: Notation.
Item """

_GOLDEN_ITEMS = (
    """\
S1:
S1: It contracts whenever $\\frac{1}{2} k < 1$.
Answer A or B.""",
    """\
S2:
S2: Notation.
Answer A or B.""",
)

#: A re-ask is the first ask with the correction after the question, carrying
#: what came back stripped.
_GOLDEN_CORRECTION = """

Again; it read:
I would say B, probably.
One letter."""


@pytest.mark.parametrize("returned", [None, "  I would say B, probably.\n"], ids=["first-ask", "re-ask"])
@pytest.mark.parametrize("index", [0, 1], ids=["S1", "S2"])
def test_the_paragraph_ask_composes_byte_for_byte_from_fixture_templates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, index: int, returned: str | None
):
    compose_from_fixture_templates(monkeypatch, tmp_path, _FIXTURE_TEMPLATES)
    entry = ask.paragraph_asks(_GOLDEN_LEAF, _GOLDEN_PARAGRAPHS)[index]

    correction = "" if returned is None else _GOLDEN_CORRECTION
    assert entry.compose(returned) == _GOLDEN_PREFIX + _GOLDEN_ITEMS[index] + correction + "\n"


# ---------------------------------------------------------------------------
# 4 — placement: a yes is its whole paragraph, located by the write API's own matching
# ---------------------------------------------------------------------------


def test_a_yes_paragraph_carrying_an_equation_is_its_whole_paragraph(declared: Path):
    """The ordinary way this corpus states a result, and refusing it would refuse most of them."""
    reading = _reading(declared, "vol/epsilon.md")
    (claim,) = _judged(reading, {_RATE}).claims

    assert claim.locator == _RATE
    assert claim.title == _RATE_TITLE
    assert "``` math" in claim.excerpt
    assert ops.excerpt_lines(reading.text, claim.excerpt) == (claim.line,), "the op's own matching, same bytes"


def test_a_paragraph_whose_words_repeat_is_unplaceable_and_defaulted(declared: Path):
    """No line of the document names it alone, so it cannot be marked: it costs that paragraph and nothing else."""
    body = (
        "---\nkind: leaf\n---\n\n"
        "The bound holds here.\n\nThe bound holds here.\n\nThe operator is monotone on the cone.\n"
    )
    reading = identify.Reading(document="vol/leaf.md", text=body, body=body)
    asked = identify.asked_paragraphs(reading)
    found = identify.judge(reading, [(paragraph, True) for paragraph in asked])

    assert [claim.title for claim in found.claims] == ["The operator is monotone on the cone."]
    assert [(verdict.judgement, verdict.cause) for verdict in found.verdicts] == [
        (kb_pipeline.Judgement.DEFAULTED, kb_pipeline.DefaultCause.UNPLACEABLE),
        (kb_pipeline.Judgement.DEFAULTED, kb_pipeline.DefaultCause.UNPLACEABLE),
        (kb_pipeline.Judgement.CLAIM, None),
    ]


def test_mathematical_prose_reaches_the_register_and_the_marker_line_byte_identical(declared: Path):
    """Byte identity from the author's text through to the written tree.

    The title is the paragraph's own first sentence and the locator its own
    slice, and both carry sequences an escape grammar would have taken: ``\\sigma``
    and ``\\beta`` in the title, and ``\\lambda`` and ``\\tfrac`` — which opens
    with ``\\t`` — in the slice.
    """
    answers = {**_ANSWERS, ("vol/epsilon.md", _IDENTITY): _CLAIM}
    assert not _discover(declared, FixedReader(answers)).failed

    title = f"An unrelated identity ${_NOT_AN_ESCAPE} < 1$ with ${_IS_AN_ESCAPE} > 0$ is recorded separately."
    assert title in [entry.title for entry in _entries(declared)]

    documents = tree.read(declared / "kb-root")
    text = documents.documents["vol/epsilon.md"].text
    marked = next(
        node for node in graph.read(documents, inventory.scan(documents)).nodes.values() if node.title == _RATE_TITLE
    )
    slice_of = _slice(declared, _RATE)
    assert "\\lambda" in slice_of and "\\tfrac" in slice_of
    assert slice_of in (_scratch(declared) / "cinf-vol_epsilon.md-4-mark-claim-in-leaf.toml").read_text("utf-8")
    lines = ops.excerpt_lines(tree.strip_markers(text), slice_of)
    assert len(lines) == 1
    assert render.render_tier2_marker(marked.id) in text.splitlines()[lines[0]]
    assert marked.locator == tree.strip_markers(text.splitlines()[lines[0]]).strip()


# ---------------------------------------------------------------------------
# 5 — the run end to end
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def discovered_build(declared_build: Path, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    repo = copy_build(declared_build, tmp_path_factory.mktemp("cinf-discovered") / "consumer")
    reader = FixedReader()
    report = _discover(repo, reader)
    assert not report.failed, report.lines()
    assert reader.groups() == ["vol/alpha.md", "vol/epsilon.md", "vol/zeta.md"]
    with held_unchanged(repo, name="cinf discovered"):
        yield repo


@pytest.fixture
def discovered(discovered_build: Path, tmp_path: Path) -> Path:
    return copy_build(discovered_build, tmp_path / "consumer")


def test_the_run_exits_zero_and_refresh_and_verify_are_green(discovered: Path):
    kb = discovered / "kb-root"
    assert refresh_kb_metadata.main(["--kb-root", str(kb)]) == 0
    assert verify_kb_metadata.main(["--kb-root", str(kb)]) == 0


def test_every_leaf_is_landed_with_its_outcome(discovered: Path):
    leaves = kb_pipeline.read_node_pass(discovered).leaves
    assert {entry.state for entry in leaves.values()} == {kb_pipeline.ReadState.LANDED}
    assert {path: entry.outcome for path, entry in leaves.items()} == {
        "vol/alpha.md": kb_pipeline.LeafOutcome.NO_CLAIM,
        "vol/epsilon.md": kb_pipeline.LeafOutcome.MINTED,
        "vol/zeta.md": kb_pipeline.LeafOutcome.NO_CLAIM,
    }
    assert [claim.title for claim in leaves["vol/epsilon.md"].claims] == [_OPENING_TITLE, _RATE_TITLE]


def test_a_blockless_leaf_minting_nothing_keeps_the_declared_pass_s_reason(discovered: Path):
    fields = kb_index_lib.parse_frontmatter((discovered / "kb-root" / "vol" / "zeta.md").read_text(encoding="utf-8"))
    assert fields["no-claim"] == BLOCKLESS_REASON


def test_no_number_is_authored(discovered: Path):
    register = (discovered / "kb-root" / "vol" / "claim-quality.md").read_text(encoding="utf-8")
    assert register.count(f"- confidence: {kb_schema.PENDING_LITERAL}") == 3
    assert all(entry.confidence is None for entry in _entries(discovered))
    # At the authoring boundary rather than after refresh: the only rigor this
    # stage ever hands the write API is the pending literal.
    values = tomllib.loads(
        (_scratch(discovered) / "cinf-vol_epsilon.md-1-insert-claim-entry.toml").read_text(encoding="utf-8")
    )
    assert [entry["rigor"] for entry in values["entry"]] == [kb_schema.PENDING_LITERAL] * 2
    assert all(not isinstance(value, (int, float)) for entry in values["entry"] for value in entry.values())


def test_every_minted_slice_locates_exactly_once_and_outside_every_exclusion(discovered: Path):
    """Re-run over the written tree, against a fresh inventory scan.

    Over the marker-stripped bytes, which is what the check was made against:
    the run appends a marker to the first line of each paragraph.
    """
    documents = tree.read(discovered / "kb-root")
    sites = inventory.scan(documents)
    authored = graph.read(documents, sites)
    prose = [node for node in authored.nodes.values() if node.document == "vol/epsilon.md"]
    assert len(prose) == 2

    text = tree.strip_markers(documents.documents["vol/epsilon.md"].text)
    fences = [fence for fence in sites.fences if fence.document == "vol/epsilon.md"]
    blocks = [block for block in sites.claim_blocks() if block.document == "vol/epsilon.md"]
    assert fences and not blocks
    for node in prose:
        lines = ops.excerpt_lines(text, node.locator)
        assert len(lines) == 1
        line = lines[0]
        assert line != 0
        assert not any(fence.start <= line < fence.end for fence in fences)
        assert not any(block.start <= line < block.end for block in blocks)


def test_every_minted_claim_carries_a_marker_the_graph_recovers_its_locator_from(discovered: Path):
    documents = tree.read(discovered / "kb-root")
    authored = graph.read(documents, inventory.scan(documents))
    text = documents.documents["vol/epsilon.md"].text
    lines = text.splitlines()
    prose = {node.id: node for node in authored.nodes.values() if node.document == "vol/epsilon.md"}
    assert len(prose) == 2

    def marked_line(node_id: str) -> int:
        carrying = [number for number, line in enumerate(lines) if render.render_tier2_marker(node_id) in line]
        assert len(carrying) == 1
        return carrying[0]

    for node_id, node in prose.items():
        assert node.locator == graph.marker_locator(text, node_id)
        assert node.locator == tree.strip_markers(lines[marked_line(node_id)]).strip()

    # Each marker sits on the line its own paragraph located to. Matched over
    # the marker-stripped text: a marker is appended to the paragraph's FIRST
    # line, so where the paragraph crosses a hard wrap the marker lands inside
    # it and the slice no longer matches the written bytes.
    unmarked = tree.strip_markers(text)
    cut = [_slice(discovered, locator) for locator in (_OPENING, _RATE)]
    assert sorted(ops.excerpt_lines(unmarked, excerpt)[0] for excerpt in cut) == sorted(
        marked_line(node_id) for node_id in prose
    )


def test_block_coverage_is_untouched(discovered: Path):
    """No C-inf span sits inside a claim-bearing block, and every block is still named once."""
    documents = tree.read(discovered / "kb-root")
    sites = inventory.scan(documents)
    claims = identify.block_claims(sites)
    identify.check_block_coverage(claims, sites)
    assert len(claims) == 1


def test_body_preservation_holds_over_the_discovery_run(declared: Path):
    """Every line added belongs to a frontmatter block; every line rewritten gained a marker."""
    before = _texts(declared / "kb-root")
    assert not _discover(declared, FixedReader()).failed
    after = _texts(declared / "kb-root")

    # Every line the run added or rewrote outside a frontmatter block, in both
    # directions, so a pair a marker relates is matched whole rather than by
    # position. The frontmatter block is excluded because it is what the run is
    # entitled to write; the body is what it may not move.
    for path, old in before.items():
        new = after[path]
        lost = Counter(kb_index_lib.strip_frontmatter(old).splitlines())
        lost -= Counter(kb_index_lib.strip_frontmatter(new).splitlines())
        gained = Counter(kb_index_lib.strip_frontmatter(new).splitlines())
        gained -= Counter(kb_index_lib.strip_frontmatter(old).splitlines())

        marked = Counter()
        for line, count in gained.items():
            stripped = tree.strip_markers(line)
            assert stripped != line, f"{path}: {line!r} is prose this run added"
            marked[stripped] += count
        assert marked == lost, path


def test_a_re_run_mints_nothing_and_leaves_the_tree_byte_identical(discovered: Path):
    before = _texts(discovered / "kb-root")
    registers = {
        path.name: path.read_text(encoding="utf-8") for path in (discovered / "kb-root").rglob("claim-quality.md")
    }
    reader = FixedReader()
    report = _discover(discovered, reader)

    assert not report.failed, report.lines()
    assert reader.questions == [], "a landed leaf is not re-read"
    assert _texts(discovered / "kb-root") == before
    assert {p.name: p.read_text(encoding="utf-8") for p in (discovered / "kb-root").rglob("claim-quality.md")} == (
        registers
    )


def test_the_write_op_composes_every_metadata_byte(discovered: Path):
    """The values files carry titles, slices and ids; no marker or bullet is spelled here.

    A leaf minting nothing writes nothing: the frontmatter it carries already says so.
    """
    values = sorted(_scratch(discovered).glob("cinf-*.toml"))
    assert [path.name for path in values] == [
        "cinf-vol_epsilon.md-1-insert-claim-entry.toml",
        "cinf-vol_epsilon.md-2-set-frontmatter.toml",
        "cinf-vol_epsilon.md-4-mark-claim-in-leaf.toml",
    ]
    marks = values[2].read_text(encoding="utf-8")
    assert _slice(discovered, _RATE) in marks and "<!--" not in marks
