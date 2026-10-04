"""Letter asks: the reader against a stub server, the templates' shape, and the stage's decisions.

The reader checks run the production :func:`ask.ask_without_tools` against the
loopback stub in ``_chat_stub`` and read the request it sent and the stats it
returned. Everything above the reader runs against a fixed
:class:`~kb_tools.kb_claimgraph.letters.LetterReader`, because a check that
needs a model to be reachable is a check that does not run.
"""

import functools
import json
import re
import threading
import time
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from kb_tools.inference import liaison_tools
from kb_tools.kb_claimgraph import ask, letters
from kb_tools.kb_claimgraph.graph import ClaimNode
from kb_tools.kb_claimgraph.report import ClaimGraphError
from kb_tools.kb_driver import prompt_templates
from kb_tools.tests._chat_stub import (  # noqa: F401 - fixtures
    SERVED_MODEL,
    USAGE,
    StubServer,
    chunk,
    served_fixture,
    server_fixture,
    sse,
)

LEAF = ask.ParagraphGroup(
    document="vol/section-2.md",
    body="S1: We study the map.\nS2: It is smooth.\n\nS3: The map is a contraction whenever $k < 1$.\n\nS4: Next, notation.",
)
PARAGRAPHS = (
    ask.ParagraphItem("S1-S2", "S1: We study the map.\nS2: It is smooth."),
    ask.ParagraphItem("S3", "S3: The map is a contraction whenever $k < 1$."),
    ask.ParagraphItem("S4", "S4: Next, notation."),
)

SOURCE = ClaimNode("clm-aaaaaa", "vol/a.md", "Theorem 1", "**Theorem 1**.", "thm:one")
TARGETS = (
    ClaimNode("clm-bbbbbb", "vol/b.md", "Lemma 2", "**Lemma 2**.", "lem:two"),
    ClaimNode("clm-cccccc", "vol/b.md", "Equation (3)", None, None, equation="eq:three"),
)
SOURCE_GROUP = ask.ClassifyGroup(SOURCE, "**Theorem 1**. The map has a unique fixed point.")
UNMARKED_GROUP = ask.UnmarkedGroup(
    document="vol/a.md",
    body="S1: We study the map.\n\n> **Theorem 1**. The map has a unique fixed point.",
    source=SOURCE,
    statement="**Theorem 1**. The map has a unique fixed point.",
)
SHORTLISTED = (
    ask.UnmarkedItem(TARGETS[0], "**Lemma 2**. The map is a contraction."),
    ask.UnmarkedItem(TARGETS[1], "$$ k = \\sup |f'| $$"),
)
CANDIDATES = (
    ask.ClassifyItem(
        TARGETS[0],
        "**Lemma 2**. The map is a contraction.",
        ("vol/a.md:7: By Lemma 2 the map contracts.",),
        tuple(ask.ClassifyLetter),
    ),
    ask.ClassifyItem(
        TARGETS[1],
        "$$ k = \\sup |f'| $$",
        ("vol/a.md:9: with $k$ as in (3).", "vol/a.md:7: By Lemma 2 the map contracts."),
        (ask.ClassifyLetter.SUPPORTED_BY, ask.ClassifyLetter.MENTION),
    ),
)


def _group_asks(kind: letters.Kind) -> tuple[letters.LetterItem, ...]:
    return {
        letters.Kind.PARAGRAPH: lambda: ask.paragraph_asks(LEAF, PARAGRAPHS),
        letters.Kind.CLASSIFY: lambda: ask.classify_asks(SOURCE_GROUP, CANDIDATES),
        letters.Kind.UNMARKED: lambda: ask.unmarked_asks(UNMARKED_GROUP, SHORTLISTED),
    }[kind]()


# --- the reader, against a stub server -----------------------------------------


def _question(prompt: str = "judge this\n") -> letters.LetterQuestion:
    return letters.LetterQuestion(letters.Kind.PARAGRAPH, "vol/one.md", "S1", prompt, tuple(ask.ParagraphLetter))


def test_a_claim_graph_ask_is_one_tool_less_call_under_the_reader_system_fragment(served: StubServer) -> None:
    fragment = prompt_templates.render(prompt_templates.FRAGMENTS[ask.READER_SYSTEM], slots={})

    reply = ask.ask_without_tools(_question("judge this\n"))

    assert (reply.text, reply.confidence) == ("A", None)
    (request,) = served.requests
    body = request["body"]
    assert body["model"] == SERVED_MODEL
    assert body["messages"] == [
        {"role": "system", "content": fragment},
        {"role": "user", "content": "judge this\n"},
    ]
    assert "tools" not in body


def test_with_no_server_named_the_ask_is_refused_naming_the_variable(server: StubServer) -> None:
    with pytest.raises(ValueError, match=liaison_tools.BASE_URL_ENV):
        ask.ask_without_tools(_question())

    assert server.requests == []


@pytest.mark.parametrize(
    ("status", "body"),
    [(500, b'{"error": {"message": "out of memory"}}'), (200, sse(chunk({"content": "A"}), done=False))],
    ids=["http-error", "no-done"],
)
def test_a_call_that_never_completes_raises_ask_error_after_the_transport_attempts(
    status: int, body: bytes, served: StubServer
) -> None:
    served.status, served.body = status, body

    with pytest.raises(ask.AskError, match="transport-failure"):
        ask.ask_without_tools(_question())

    assert len(served.requests) == ask.TRANSPORT_ATTEMPTS


#: An inference server aborting a request: its error message as the reply text,
#: a stream reaching ``[DONE]``, and no token read or written.
_ABORTED = sse(
    chunk({"content": "[Error: Request aborted: limit exceeded.]"}, "stop"),
    {"choices": [], "usage": {"prompt_tokens": 0, "completion_tokens": 0}},
)

_ANSWERED_B = sse(
    chunk({"content": "B"}, "stop"), {"choices": [], "usage": {"prompt_tokens": 7578, "completion_tokens": 1}}
)


def test_a_server_error_returned_as_reply_text_raises_ask_error(served: StubServer) -> None:
    served.body = _ABORTED

    with pytest.raises(ask.AskError, match="no token read or written"):
        ask.ask_without_tools(_question())

    assert len(served.requests) == ask.TRANSPORT_ATTEMPTS


def test_a_server_error_is_re_issued_and_the_answer_that_follows_is_the_reply(served: StubServer) -> None:
    served.script = [(200, _ABORTED), (200, _ANSWERED_B)]

    reply = ask.ask_without_tools(_question())

    assert reply.text == "B"
    assert reply.stats is not None
    assert (reply.stats.prompt_tokens, reply.stats.output_tokens) == (7578, 1)
    assert len(served.requests) == 2


def test_a_cut_off_reply_completes_and_is_left_to_the_letter_parse(served: StubServer) -> None:
    served.body = sse(chunk({"content": "The answer is"}, "length"), {"choices": [], "usage": USAGE})

    reply = ask.ask_without_tools(_question())

    assert reply.text == "The answer is"
    assert len(served.requests) == 1


def test_a_reply_that_streamed_reasoning_is_counted_in_the_record(served: StubServer, tmp_path: Path) -> None:
    served.body = sse(
        chunk({"reasoning_content": "We need"}), chunk({"content": "B"}, "stop"), {"choices": [], "usage": USAGE}
    )
    reader = functools.partial(ask.ask_without_tools, captures=tmp_path / "captures")

    record = letters.ask_group(
        kind=letters.Kind.PARAGRAPH,
        group=LEAF.document,
        items=ask.paragraph_asks(LEAF, PARAGRAPHS[:1]),
        reader=reader,
        record_dir=tmp_path / "records",
    )

    (call,) = record.items[0].calls
    assert call.stats is not None
    assert (call.stats.thinking_blocks, call.stats.prompt_tokens, call.stats.cache_read_input_tokens) == (1, 7718, 7711)
    assert call.stats.output_tokens == 1 and call.stats.duration_api_ms is not None
    path = letters.group_record_path(tmp_path / "records", kind=letters.Kind.PARAGRAPH, group=LEAF.document)
    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["items"][0]["calls"][0]["stats"]["thinking_blocks"] == 1
    assert written["items"][0]["letter"] == "B"
    assert len(list((tmp_path / "captures").iterdir())) == 1


# --- the templates: every per-item slot last, every group's prefix shared ------


@pytest.mark.parametrize("kind", list(letters.Kind))
def test_every_per_item_slot_sits_after_every_group_slot(kind: letters.Kind) -> None:
    name = ask.LETTER_TEMPLATES[kind]
    source = prompt_templates.load(name)
    slots = prompt_templates.slots_of(source, source=name)
    item_slots = ask.ITEM_SLOTS[kind]
    group_slots = [
        slot for slot in slots if slot.startswith(prompt_templates.DYNAMIC_PREFIX) and slot not in item_slots
    ]

    assert set(item_slots) <= set(slots)
    assert group_slots
    last_group = max(source.rindex(f"@!{slot}!@") for slot in group_slots)
    first_item = min(source.index(f"@!{slot}!@") for slot in item_slots)
    assert last_group < first_item


def _question_opening(kind: letters.Kind) -> str:
    """The constant line the question section opens with: the last non-blank line before any item slot."""
    lines = prompt_templates.load(ask.LETTER_TEMPLATES[kind]).splitlines()
    first_item = next(
        number for number, line in enumerate(lines) if any(f"@!{slot}!@" in line for slot in ask.ITEM_SLOTS[kind])
    )
    opening = next(line for line in reversed(lines[:first_item]) if line.strip())
    assert prompt_templates.SLOT.search(opening) is None
    return opening


@pytest.mark.parametrize("kind", list(letters.Kind))
def test_two_asks_of_one_group_differ_only_after_the_question_opens(kind: letters.Kind) -> None:
    opening = _question_opening(kind)
    first, second = (entry.compose(None) for entry in _group_asks(kind)[:2])

    boundary = first.index(f"\n{opening}\n") + len(opening) + 2

    assert first[:boundary] == second[:boundary]
    assert first != second


@pytest.mark.parametrize("kind", list(letters.Kind))
def test_a_re_ask_is_the_first_prompt_with_the_correction_after_the_question(kind: letters.Kind) -> None:
    entry = _group_asks(kind)[0]
    first = entry.compose(None)

    reask = entry.compose("I would say the answer is probably the first one")

    assert first.endswith("\n")
    assert reask.startswith(first.removesuffix("\n"))
    assert "I would say the answer is probably the first one" in reask[len(first) - 1 :]


@pytest.mark.parametrize("candidate", CANDIDATES, ids=lambda candidate: candidate.target.id)
def test_a_classify_question_closes_naming_exactly_the_letters_it_offers(candidate: ask.ClassifyItem) -> None:
    (entry,) = ask.classify_asks(SOURCE_GROUP, [candidate])
    closing = entry.compose(None).rsplit("````````````", maxsplit=1)[1]

    assert set(entry.offered) == set(candidate.offered)
    assert set(re.findall(r"\b[A-Z]\b", closing)) == set(entry.offered)


def test_an_unmarked_ask_is_named_by_its_target_and_offered_both_letters() -> None:
    asks = ask.unmarked_asks(UNMARKED_GROUP, SHORTLISTED)

    assert [entry.item for entry in asks] == [target.id for target in TARGETS]
    assert all(entry.offered == ("A", "B") for entry in asks)


def test_a_group_numbers_its_passages_once() -> None:
    """Which of them each candidate names is in the classify pins, ``test_kb_claimgraph_pass2.py``."""
    lemma, equation = (entry.compose(None) for entry in ask.classify_asks(SOURCE_GROUP, CANDIDATES))

    numbered = "P1: vol/a.md:7: By Lemma 2 the map contracts.\nP2: vol/a.md:9: with $k$ as in (3)."
    assert numbered in lemma and numbered in equation


# --- the stage's decisions, over a fixed reader --------------------------------


class FixedReader:
    """Answers each item from a script of replies, in order, and records every question it was put."""

    def __init__(self, replies: Mapping[str, Sequence[letters.Reply | str]]) -> None:
        self._replies = {item: list(script) for item, script in replies.items()}
        self.questions: list[letters.LetterQuestion] = []
        self._lock = threading.Lock()

    def __call__(self, question: letters.LetterQuestion) -> letters.Reply:
        with self._lock:
            self.questions.append(question)
            reply = self._replies[question.item].pop(0)
        return reply if isinstance(reply, letters.Reply) else letters.Reply(reply)


def _ask_paragraphs(
    reader: letters.LetterReader, items: Sequence[ask.ParagraphItem] = PARAGRAPHS
) -> letters.GroupRecord:
    return letters.ask_group(
        kind=letters.Kind.PARAGRAPH, group=LEAF.document, items=ask.paragraph_asks(LEAF, items), reader=reader
    )


@pytest.mark.parametrize(
    ("text", "letter"),
    [("A", "A"), ("  B\n", "B"), ("A.", None), ("AB", None), ("a", None), ("", None), ("C", None)],
)
def test_the_strict_parse_takes_exactly_one_offered_letter(text: str, letter: str | None) -> None:
    assert letters.decide(letters.Reply(text), tuple(ask.ParagraphLetter)) == letter


def test_a_malformed_reply_is_re_asked_once_with_the_correction_then_defaults() -> None:
    reader = FixedReader({"S1-S2": ["Probably A.", "It states a result, so A"]})

    record = _ask_paragraphs(reader, PARAGRAPHS[:1])

    (item,) = record.items
    assert (item.letter, item.outcome) == (None, letters.AskOutcome.DEFAULTED)
    first, second = reader.questions
    assert second.prompt.startswith(first.prompt.removesuffix("\n"))
    assert "Probably A." in second.prompt[len(first.prompt) - 1 :]
    assert [call.reply for call in item.calls] == ["Probably A.", "It states a result, so A"]


def test_a_re_ask_answered_with_an_offered_letter_is_recorded_as_re_asked() -> None:
    reader = FixedReader({"S1-S2": ["yes", "A"]})

    (item,) = _ask_paragraphs(reader, PARAGRAPHS[:1]).items

    assert (item.letter, item.outcome, len(item.calls)) == ("A", letters.AskOutcome.REASKED, 2)


def test_a_letter_outside_the_offered_set_is_malformed() -> None:
    """``B`` is a classify letter, but not one a candidate refused *in support of* is offered."""
    reader = FixedReader({TARGETS[1].id: ["B", "B"]})
    items = ask.classify_asks(SOURCE_GROUP, CANDIDATES[1:])

    record = letters.ask_group(kind=letters.Kind.CLASSIFY, group=SOURCE.id, items=items, reader=reader)

    (item,) = record.items
    assert (item.letter, item.outcome, len(item.calls)) == (None, letters.AskOutcome.DEFAULTED, 2)


def test_a_transport_failure_stops_the_group() -> None:
    def failing(question: letters.LetterQuestion) -> letters.Reply:
        raise ask.AskError("inference-failed", f"{question.item}: the call never completed")

    with pytest.raises(ask.AskError):
        _ask_paragraphs(failing)


def test_a_reader_returning_confidence_is_decided_by_argmax_over_the_offered_letters() -> None:
    distribution = {"B": 0.7, "A": 0.2, "C": 0.1}
    reader = FixedReader({TARGETS[1].id: [letters.Reply("ignored text", confidence=distribution)]})
    items = ask.classify_asks(SOURCE_GROUP, CANDIDATES[1:])

    (item,) = letters.ask_group(kind=letters.Kind.CLASSIFY, group=SOURCE.id, items=items, reader=reader).items

    assert (item.letter, item.outcome, item.confidence) == ("A", letters.AskOutcome.ANSWERED, distribution)


def test_concurrency_issues_the_first_ask_alone_and_keeps_item_order(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(letters.READER_CONCURRENCY_ENV, "3")
    events: list[tuple[str, str]] = []
    lock = threading.Lock()
    delays = {"S1-S2": 0.05, "S3": 0.05, "S4": 0.0}

    def reader(question: letters.LetterQuestion) -> letters.Reply:
        with lock:
            events.append(("start", question.item))
        time.sleep(delays[question.item])
        with lock:
            events.append(("end", question.item))
        return letters.Reply("A" if question.item != "S4" else "B")

    record = _ask_paragraphs(reader)

    assert events[:2] == [("start", "S1-S2"), ("end", "S1-S2")]
    assert events.index(("end", "S4")) < events.index(("end", "S3"))
    assert [(item.item, item.letter) for item in record.items] == [("S1-S2", "A"), ("S3", "A"), ("S4", "B")]


@pytest.mark.parametrize("value", ["0", "-2", "four", ""])
def test_an_unusable_reader_concurrency_is_refused_by_name(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv(letters.READER_CONCURRENCY_ENV, value)

    with pytest.raises(ClaimGraphError, match=letters.READER_CONCURRENCY_ENV):
        letters.reader_concurrency()


def test_reader_concurrency_defaults_to_four(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(letters.READER_CONCURRENCY_ENV, raising=False)

    assert letters.reader_concurrency() == 4


def test_the_record_holds_the_prefix_once_and_each_call_its_tail() -> None:
    record = _ask_paragraphs(FixedReader({"S1-S2": ["A"], "S3": ["A"], "S4": ["B"]}))

    for entry, item in zip(ask.paragraph_asks(LEAF, PARAGRAPHS), record.items, strict=True):
        assert record.prefix + item.calls[0].tail == entry.compose(None)
    assert record.prefix.endswith(f"\n{_question_opening(letters.Kind.PARAGRAPH)}\n\n")


def test_totals_count_outcomes_and_take_the_cache_share_over_warm_calls_only() -> None:
    def stats(prompt: int, cached: int) -> letters.CallStats:
        return letters.CallStats(
            duration_api_ms=500,
            output_tokens=1,
            thinking_blocks=0,
            cache_read_input_tokens=cached,
            prompt_tokens=prompt,
        )

    reader = FixedReader(
        {
            "S1-S2": [letters.Reply("A", stats=stats(1000, 0))],
            "S3": [letters.Reply("maybe", stats=stats(1000, 900)), letters.Reply("B", stats=stats(1100, 950))],
            "S4": ["nope", "still no"],
        }
    )

    totals = letters.AskTotals.of([_ask_paragraphs(reader)])

    assert (totals.items, totals.answered, totals.reasked, totals.defaulted) == (3, 1, 1, 1)
    assert (totals.calls, totals.unmeasured, totals.output_tokens) == (5, 2, 3)
    assert (totals.warm_cache_read_tokens, totals.warm_prompt_tokens) == (1850, 2100)
    assert "defaulted=1" in totals.detail() and "thinking-blocks=0" in totals.detail()
