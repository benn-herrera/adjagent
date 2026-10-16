"""Letter asks: the reader against a stub server, the templates' and questions' shape, and the stage's decisions.

The reader checks run the production :func:`ask.ask_without_tools` against the
loopback stub in ``_chat_stub`` and read the request it sent and the reply it
returned. Everything above the reader runs against a fixed
:class:`~kb_tools.kb_claimgraph.letters.LetterReader`, because a check that
needs a model to be reachable is a check that does not run.
"""

import functools
import json
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
    SERVED_DECISION_MODEL,
    StubServer,
    served_fixture,
    server_fixture,
)
from kb_tools.tests._fixture_templates import compose_from_fixture_templates

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
LINKED = (
    ask.ColinearItem(
        "clm-bbbbbb", SOURCE, "**Theorem 1**. The map has a unique fixed point.\n", TARGETS[0], "**Lemma 2**. Again."
    ),
    ask.ColinearItem("clm-cccccc", SOURCE, "**Theorem 1**. The map has a unique fixed point.", TARGETS[1], "$$ k $$"),
)


def _group_asks(kind: letters.Kind) -> tuple[letters.LetterItem, ...]:
    return {
        letters.Kind.PARAGRAPH: lambda: ask.paragraph_asks(LEAF, PARAGRAPHS),
        letters.Kind.CLASSIFY: lambda: ask.classify_asks(SOURCE_GROUP, CANDIDATES),
        letters.Kind.UNMARKED: lambda: ask.unmarked_asks(UNMARKED_GROUP, SHORTLISTED),
        letters.Kind.COLINEAR: lambda: ask.colinear_asks(LINKED),
    }[kind]()


# --- the reader, against a stub server -----------------------------------------


def _question(
    prompt: str = "judge this\n", *, kind: letters.Kind = letters.Kind.PARAGRAPH, offered: Sequence[str] = ("A", "B")
) -> letters.LetterQuestion:
    return letters.LetterQuestion(kind, "vol/one.md", "S1", prompt, tuple(offered), 1)


def _answers(answers: Mapping[str, object], usage: Mapping[str, int] | None = None) -> bytes:
    usage = {"input_tokens": 812, "output_tokens": 1} if usage is None else usage
    return json.dumps({"model": SERVED_DECISION_MODEL, "answers": answers, "usage": usage}).encode("utf-8")


def _shipped_question(kind: letters.Kind, offered: Sequence[str]) -> prompt_templates.Question:
    return prompt_templates.load_question(ask.question_name(kind, offered), constants=ask.LETTER_SLOTS, offered=offered)


@pytest.mark.parametrize(
    ("kind", "offered", "answer", "confidence"),
    [
        (letters.Kind.PARAGRAPH, ("A", "B"), {"type": "noul", "noul": 0.25}, {"A": 0.25, "B": 0.75}),
        (
            letters.Kind.CLASSIFY,
            ("A", "C"),
            {"type": "choice", "choice": "C", "confidence": 0.9, "probabilities": {"A": 0.1, "C": 0.9}},
            {"A": 0.1, "C": 0.9},
        ),
    ],
    ids=["noul", "choice"],
)
def test_a_claim_graph_ask_is_one_decision_request_with_the_kind_s_question_under_the_item(
    served: StubServer,
    kind: letters.Kind,
    offered: tuple[str, ...],
    answer: dict[str, object],
    confidence: dict[str, float],
) -> None:
    served.body = _answers({"S1": answer})

    reply = ask.ask_without_tools(_question("the state\n", kind=kind, offered=offered))

    assert (reply.text, reply.confidence) == ("", confidence)
    (request,) = served.requests
    asked = _shipped_question(kind, offered)
    assert request["path"] == "/v1" + liaison_tools.DECISION_PATH
    assert request["body"] == {
        "model": SERVED_DECISION_MODEL,
        "state": "the state\n",
        "questions": {"S1": {"type": asked.type, "instructions": asked.instructions, "criteria": dict(asked.criteria)}},
    }
    sent = request["body"]["questions"]["S1"]["criteria"]
    assert list(sent) == sorted(sent), "criteria go on the wire in key order, as kbase's encoder writes a map"


def test_with_no_server_named_the_ask_is_refused_naming_the_variable(server: StubServer) -> None:
    with pytest.raises(ValueError, match=liaison_tools.BASE_URL_ENV):
        ask.ask_without_tools(_question())

    assert server.requests == []


def test_a_letter_ask_needs_the_decision_model_and_not_the_chat_model(
    served: StubServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    served.body = _answers({"S1": {"type": "noul", "noul": 1.0}})
    monkeypatch.delenv(liaison_tools.MODEL_ENV)

    assert ask.ask_without_tools(_question()).confidence == {"A": 1.0, "B": 0.0}

    monkeypatch.delenv(liaison_tools.DECISION_MODEL_ENV)
    with pytest.raises(ValueError, match=liaison_tools.DECISION_MODEL_ENV):
        ask.ask_without_tools(_question())


@pytest.mark.parametrize("status", [429, 500, 503])
def test_a_call_that_never_completes_raises_ask_error_after_the_transport_attempts(
    status: int, served: StubServer
) -> None:
    served.status, served.body = status, b'{"error": {"message": "out of memory"}}'

    with pytest.raises(ask.AskError, match="transport-failure"):
        ask.ask_without_tools(_question())

    assert len(served.requests) == ask.TRANSPORT_ATTEMPTS


@pytest.mark.parametrize(
    ("status", "body"),
    [(400, b'{"error": "bad question"}'), (200, _answers({"S2": {"type": "noul", "noul": 0.5}}))],
    ids=["4xx", "unasked-key"],
)
def test_a_refused_call_raises_ask_error_without_a_re_issue(status: int, body: bytes, served: StubServer) -> None:
    served.status, served.body = status, body

    with pytest.raises(ask.AskError, match="refused"):
        ask.ask_without_tools(_question())

    assert len(served.requests) == 1


def test_a_retry_class_failure_is_re_issued_identically_and_the_answer_that_follows_is_the_reply(
    served: StubServer,
) -> None:
    served.script = [(503, b""), (200, _answers({"S1": {"type": "noul", "noul": 0.9}}, {"input_tokens": 7578}))]

    reply = ask.ask_without_tools(_question())

    assert reply.confidence == pytest.approx({"A": 0.9, "B": 0.1})
    assert reply.stats is not None
    assert (reply.stats.prompt_tokens, reply.stats.output_tokens) == (7578, None)
    first, second = served.requests
    assert first["body"] == second["body"]


@pytest.mark.parametrize(
    ("answer", "offered", "confidence"),
    [
        (
            {"type": "choice", "choice": "B", "confidence": 0.6, "probabilities": {"A": 0.4, "B": 0.6}},
            "AB",
            {"A": 0.4, "B": 0.6},
        ),
        ({"type": "choice", "choice": "B", "confidence": 0.6}, "AB", {"B": 0.6}),
        ({"type": "choice", "choice": "B"}, "AB", {"B": 0.0}),
        ({"type": "choice"}, "AB", None),
        ({"type": "noul", "noul": 0.8}, "AB", {"A": 0.8, "B": pytest.approx(0.2)}),
        ({"type": "noul", "noul": 0.8}, "ABC", {"A": 0.8}),
        ({"type": "noul", "noul": 1.5}, "AB", None),
        ({"type": "noul"}, "AB", {"A": 0.0, "B": 1.0}),
        ({"type": "noul", "noul": "0.5"}, "AB", None),
        ({"type": "noul", "noul": True}, "AB", None),
        ({"type": "score", "score": 0.5}, "AB", None),
        (None, "AB", None),
    ],
    ids=[
        "choice-probabilities",
        "choice-confidence",
        "choice-alone",
        "choice-nothing",
        "noul",
        "noul-over-three",
        "noul-out-of-range",
        "noul-absent-is-a-confident-false",
        "noul-a-string",
        "noul-not-a-number",
        "unknown-type",
        "no-answer",
    ],
)
def test_an_answer_maps_to_a_confidence_over_the_letters(
    answer: dict[str, object] | None, offered: str, confidence: dict[str, float] | None
) -> None:
    assert ask.answer_confidence(answer, true_letter="A", offered=tuple(offered)) == confidence


def test_a_noul_answer_with_its_figure_omitted_decides_the_false_letter(served: StubServer) -> None:
    """An encoder omitting empty fields drops the figure of exactly a confident false, so absence is not unread."""
    served.body = _answers({"S1-S2": {"type": "noul"}})

    (item,) = _ask_paragraphs(ask.ask_without_tools, PARAGRAPHS[:1]).items

    assert (item.letter, item.outcome, len(item.calls)) == (
        ask.ParagraphLetter.NOT_A_CLAIM,
        letters.AskOutcome.ANSWERED,
        1,
    )


def test_an_unanswered_question_is_re_asked_identically_with_its_ordinal_and_defaults(
    served: StubServer, tmp_path: Path
) -> None:
    served.body = _answers({})
    reader = functools.partial(ask.ask_without_tools, captures=tmp_path / "captures")

    record = letters.ask_group(
        kind=letters.Kind.PARAGRAPH,
        group=LEAF.document,
        items=ask.paragraph_asks(LEAF, PARAGRAPHS[:1]),
        reader=reader,
        record_dir=tmp_path / "records",
    )

    (item,) = record.items
    assert (item.letter, item.outcome, len(item.calls)) == (None, letters.AskOutcome.DEFAULTED, 2)
    first, second = served.requests
    assert first["body"] == second["body"]
    captures = sorted(path.name for path in (tmp_path / "captures").iterdir())
    assert [name.rsplit("-", 1)[1] for name in captures] == ["1.capture.jsonl", "2.capture.jsonl"]
    assert item.calls[0].stats is not None and item.calls[0].stats.prompt_tokens == 812
    path = letters.group_record_path(tmp_path / "records", kind=letters.Kind.PARAGRAPH, group=LEAF.document)
    assert json.loads(path.read_text(encoding="utf-8"))["items"][0]["outcome"] == "defaulted"


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
    last_group = max((source.rindex(f"@!{slot}!@") for slot in group_slots), default=-1)
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
    first, second = (entry.compose() for entry in _group_asks(kind)[:2])

    boundary = first.index(f"\n{opening}\n") + len(opening) + 2

    assert first[:boundary] == second[:boundary]
    assert first != second


#: Every (kind, offered letters) an ask can put: every letter of the paragraph,
#: unmarked and colinear asks, and each classify offer the question table names.
_OFFERS = (
    (letters.Kind.PARAGRAPH, tuple(ask.ParagraphLetter)),
    (letters.Kind.UNMARKED, tuple(ask.UnmarkedLetter)),
    (letters.Kind.COLINEAR, tuple(ask.ColinearLetter)),
    *(
        (letters.Kind.CLASSIFY, tuple(letter for letter in ask.ClassifyLetter if letter in offer))
        for offer in ask.CLASSIFY_QUESTIONS
    ),
)


@pytest.mark.parametrize(
    ("kind", "offered"), _OFFERS, ids=lambda value: "".join(value) if isinstance(value, tuple) else value
)
def test_every_offer_an_ask_can_put_loads_a_shipped_question_keyed_by_it(
    kind: letters.Kind, offered: tuple[str, ...]
) -> None:
    """A choice question's criteria are the offered letters; a noul question's true letter is one of them."""
    asked = _shipped_question(kind, offered)

    if asked.type == prompt_templates.NOUL:
        assert len(offered) == 2 and asked.true_letter in offered
    else:
        assert set(asked.criteria) == set(offered)


def test_every_shipped_question_is_one_an_ask_can_put() -> None:
    """A question no offer reaches is never loaded, so nothing else would meet its defects."""
    directory = prompt_templates.PROMPT_TEMPLATES_DIR / prompt_templates.QUESTIONS_DIRNAME
    shipped = {path.name.removesuffix(prompt_templates.QUESTION_SUFFIX) for path in directory.iterdir()}

    assert shipped == {ask.question_name(kind, offered) for kind, offered in _OFFERS}


def test_a_state_names_no_letter() -> None:
    """The letters reach only the question; a state template spelling a letter slot is a second definition."""
    for kind, name in ask.LETTER_TEMPLATES.items():
        slots = prompt_templates.slots_of(prompt_templates.load(name), source=name)
        assert all(slot.startswith(prompt_templates.DYNAMIC_PREFIX) for slot in slots), kind


def test_an_unmarked_ask_is_named_by_its_target_and_offered_both_letters() -> None:
    asks = ask.unmarked_asks(UNMARKED_GROUP, SHORTLISTED)

    assert [entry.item for entry in asks] == [target.id for target in TARGETS]
    assert all(entry.offered == ("A", "B") for entry in asks)


def test_a_colinear_ask_is_named_by_its_key_and_offered_all_three_letters() -> None:
    asks = ask.colinear_asks(LINKED)

    assert [entry.item for entry in asks] == ["clm-bbbbbb", "clm-cccccc"]
    assert all(entry.offered == ("A", "B", "C") for entry in asks)


#: A fixture colinear template, standing in for the working one so the golden
#: below pins the composer and moves with nothing a wording edit touches.
_COLINEAR_FIXTURE = {
    ask.LETTER_TEMPLATES[letters.Kind.COLINEAR]: (
        "First @!dyn.first-line!@\n@!dyn.first-text!@\nSecond @!dyn.second-line!@\n@!dyn.second-text!@\n"
    ),
}

_COLINEAR_GOLDEN = """\
First - `clm-aaaaaa` — Theorem 1 (stated in `vol/a.md`: **Theorem 1**.)
**Theorem 1**. The map has a unique fixed point.
Second - `clm-bbbbbb` — Lemma 2 (stated in `vol/b.md`: **Lemma 2**.)
**Lemma 2**. Again.
"""


def test_the_colinear_ask_composes_byte_for_byte_from_a_fixture_template(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The first claim before the second, each statement's trailing newlines trimmed."""
    compose_from_fixture_templates(monkeypatch, tmp_path, _COLINEAR_FIXTURE)

    assert ask.colinear_asks(LINKED[:1])[0].compose() == _COLINEAR_GOLDEN


def test_a_group_numbers_its_passages_once() -> None:
    """Which of them each candidate names is in the classify pins, ``test_kb_claimgraph_pass2.py``."""
    lemma, equation = (entry.compose() for entry in ask.classify_asks(SOURCE_GROUP, CANDIDATES))

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


def test_a_malformed_reply_is_re_asked_once_identically_with_its_ordinal_then_defaults() -> None:
    reader = FixedReader({"S1-S2": ["Probably A.", "It states a result, so A"]})

    record = _ask_paragraphs(reader, PARAGRAPHS[:1])

    (item,) = record.items
    assert (item.letter, item.outcome) == (None, letters.AskOutcome.DEFAULTED)
    first, second = reader.questions
    assert (first.attempt, second.attempt) == (1, 2)
    assert second.prompt == first.prompt
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
        assert record.prefix + item.calls[0].tail == entry.compose()
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
