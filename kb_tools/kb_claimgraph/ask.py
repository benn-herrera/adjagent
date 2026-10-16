"""This package's asks: what is asked, how it is asked, and the reader that asks it.

**Every claim-graph ask is a letter ask**: one decision, answered with one
letter from a closed set (:mod:`letters`). Four kinds. A **paragraph** ask puts
one paragraph of a leaf to the reader — does it state a result — with the leaf as
:mod:`label` renders it for context; its group is the leaf. A **classify** ask
puts one edge candidate — is the source *supported by* it, *in support of* it,
or does it merely *mention* it — with the source claim and the passages its
references sit in for context; its group is the source claim. An **unmarked**
ask puts one shortlisted pair no cross-reference links — does the source claim
continue the argument the candidate is part of — with the source's leaf and its
statement for context; its group is the source claim. A **colinear** ask puts
one linked pair, its two claims shown in reading order — does either add
nothing to the other — with nothing but the two claims; its group is the
caller's. What each kind asks is stated in its question file, not here.

**One letter-to-meaning table per kind** (:class:`ParagraphLetter`,
:class:`ClassifyLetter`, :class:`UnmarkedLetter`, :class:`ColinearLetter`). A question offering fewer meanings withholds their
letters and never relabels the rest, so a letter means one thing in every ask
of its kind. The letters reach a question file only as composer constants
(:data:`LETTER_SLOTS`): a file spelling one would be a second definition of
the string the decision is read against.

**An ask is a state and a question.** The state is a template under
``kb_driver/prompt-templates/`` rendered with the item's values; the question
is the kind's file under its ``questions/`` (:func:`question_name`), which
carries the instructions and the per-letter criteria. Every slot of an item
(:data:`ITEM_SLOTS`) sits in a template's final section, after every slot of
its group, so every state of a group opens with the same bytes and a server can
serve that prefix from cache. No prompt is written here: this module hands the
composer values and names the question.

**The reader is one decision call.** :func:`ask_without_tools` is the
production :class:`~.letters.LetterReader`: the state and the kind's question,
keyed by the item's name, through :func:`kb_tools.inference.call_decision` on
the environment's decision model — no system message and no tool, so an answer
rests on the state and nothing a model chose to look at. The answer becomes a
per-letter confidence (:func:`answer_confidence`), and its capture is read by
:func:`kb_tools.inference.read_decision_capture` into
:class:`~.letters.CallStats`. A call in the retry class is re-issued
identically up to :data:`TRANSPORT_ATTEMPTS`; one that never completes, or that
the server refuses, raises :class:`AskError`, which is the one thing that stops
a stage — no answer arrived, and defaulting every remaining item would hide a
dead model behind what looks like a finished run.
"""

import re
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from functools import partial
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from types import MappingProxyType

from .. import inference, kb_pipeline
from ..kb_driver import prompt_templates
from .graph import ClaimNode
from .letters import CallStats, Kind, LetterItem, LetterQuestion, Reply
from .report import ClaimGraphError

#: How many times a call that did not come back is re-issued **identically**
#: before the stage stops. The layer below retries nothing by design — policy
#: is the caller's — so a bound belongs here or nowhere, and a writer that never
#: yields is a wedge rather than a retry.
TRANSPORT_ATTEMPTS = 3

#: How long one blocking socket operation of a call — the connect, or a read of
#: its response — may wait. The outer edge of "something is wrong", not an
#: expectation; nothing bounds the call as a whole.
SOCKET_TIMEOUT_SECONDS = 600.0


class AskError(ClaimGraphError):
    """The call did not come back. No answer arrived, so no re-ask can be spent on one.

    A letter ask whose reply carries no offered letter is not this: it is
    re-asked once and then takes its default (:mod:`letters`).
    """


def _claim_line(node: ClaimNode) -> str:
    where = f": {node.locator}" if node.locator else ""
    return f"- `{node.id}` — {node.title} (stated in `{node.document}`{where})"


# --- the letter asks -----------------------------------------------------------


class ParagraphLetter(StrEnum):
    """The paragraph ask's letters: does the paragraph itself state a result."""

    CLAIM = "A"
    NOT_A_CLAIM = "B"


class ClassifyLetter(StrEnum):
    """The classify ask's letters: how the source claim relates to the candidate."""

    SUPPORTED_BY = "A"
    IN_SUPPORT_OF = "B"
    MENTION = "C"


class UnmarkedLetter(StrEnum):
    """The unmarked ask's letters: does the source claim continue the argument the candidate is part of."""

    POINTS = kb_pipeline.UNMARKED_POINTS_LETTER
    DOES_NOT = "B"


class ColinearLetter(StrEnum):
    """The colinear ask's letters: which of two claims, first and second in reading order, adds nothing."""

    SECOND_ADDS_NOTHING = "A"
    FIRST_ADDS_NOTHING = "B"
    DISTINCT = "C"


#: The letters as the question files name them.
LETTER_SLOTS: Mapping[str, str] = MappingProxyType(
    {
        "letter-claim": ParagraphLetter.CLAIM,
        "letter-not-a-claim": ParagraphLetter.NOT_A_CLAIM,
        "letter-supported-by": ClassifyLetter.SUPPORTED_BY,
        "letter-in-support-of": ClassifyLetter.IN_SUPPORT_OF,
        "letter-mention": ClassifyLetter.MENTION,
        "letter-points": UnmarkedLetter.POINTS,
        "letter-does-not-point": UnmarkedLetter.DOES_NOT,
        "letter-second-adds-nothing": ColinearLetter.SECOND_ADDS_NOTHING,
        "letter-first-adds-nothing": ColinearLetter.FIRST_ADDS_NOTHING,
        "letter-distinct": ColinearLetter.DISTINCT,
    }
)

LETTER_TEMPLATES: Mapping[Kind, str] = MappingProxyType(
    {
        Kind.PARAGRAPH: "paragraph.tmpl.md",
        Kind.CLASSIFY: "classify.tmpl.md",
        Kind.UNMARKED: "unmarked.tmpl.md",
        Kind.COLINEAR: "colinear.tmpl.md",
    }
)

#: Each kind's per-item slots, as a template spells them. Everything before the
#: first of them is the group's and identical across the group's asks; a
#: colinear state is all item, its group sharing only the template's opening.
ITEM_SLOTS: Mapping[Kind, tuple[str, ...]] = MappingProxyType(
    {
        Kind.PARAGRAPH: ("dyn.paragraph", "dyn.paragraph-text"),
        Kind.CLASSIFY: ("dyn.candidate-line", "dyn.candidate-text", "dyn.candidate-passages"),
        Kind.UNMARKED: ("dyn.candidate-line", "dyn.candidate-text"),
        Kind.COLINEAR: ("dyn.first-line", "dyn.first-text", "dyn.second-line", "dyn.second-text"),
    }
)

#: The questions of the kinds that ask one whatever the item, under ``prompt-templates/questions/``.
LETTER_QUESTIONS: Mapping[Kind, str] = MappingProxyType(
    {Kind.PARAGRAPH: "paragraph", Kind.UNMARKED: "unmarked", Kind.COLINEAR: "colinear"}
)

#: The classify ask's question, by the letters it offers. Every offered set holds
#: *supported by* and *mention*; *in support of* is the one a candidate may be
#: refused.
CLASSIFY_QUESTIONS: Mapping[frozenset[str], str] = MappingProxyType(
    {
        frozenset(ClassifyLetter): "classify-three",
        frozenset({ClassifyLetter.SUPPORTED_BY, ClassifyLetter.MENTION}): "classify-two",
    }
)


def question_name(kind: Kind, offered: Sequence[str]) -> str:
    """The question file an ask of ``kind`` offering ``offered`` asks."""
    return CLASSIFY_QUESTIONS[frozenset(offered)] if kind is Kind.CLASSIFY else LETTER_QUESTIONS[kind]


def _letter_prompt(kind: Kind, slots: Mapping[str, str]) -> str:
    """One letter ask's state: the template of ``kind`` over ``slots``."""
    return prompt_templates.render(LETTER_TEMPLATES[kind], slots=slots)


@dataclass(frozen=True)
class ParagraphGroup:
    """A leaf: its path, and its body as :func:`label.render` shows it."""

    document: str
    body: str


@dataclass(frozen=True)
class ParagraphItem:
    """One paragraph: its label range, and its labelled lines."""

    paragraph: str
    text: str


def _paragraph_prompt(group: ParagraphGroup, item: ParagraphItem) -> str:
    return _letter_prompt(
        Kind.PARAGRAPH,
        {
            "document": group.document,
            "body": group.body.rstrip("\n"),
            "paragraph": item.paragraph,
            "paragraph-text": item.text.rstrip("\n"),
        },
    )


def paragraph_asks(group: ParagraphGroup, items: Sequence[ParagraphItem]) -> tuple[LetterItem, ...]:
    """One leaf's paragraph asks, each named by its label range and offered both letters."""
    offered = tuple(ParagraphLetter)
    return tuple(LetterItem(item.paragraph, offered, partial(_paragraph_prompt, group, item)) for item in items)


@dataclass(frozen=True)
class ClassifyGroup:
    """A source claim, and its statement: block content, prose paragraph or equation fence."""

    source: ClaimNode
    statement: str


@dataclass(frozen=True)
class ClassifyItem:
    """One edge candidate: its target, the target's statement, its own passages, its letters."""

    target: ClaimNode
    statement: str
    passages: tuple[str, ...]
    offered: tuple[ClassifyLetter, ...]


def _classify_prompt(group: ClassifyGroup, item: ClassifyItem, *, numbers: Mapping[str, int]) -> str:
    return _letter_prompt(
        Kind.CLASSIFY,
        {
            "claim-line": _claim_line(group.source),
            "claim-text": group.statement.rstrip("\n"),
            "reference-lines": "\n".join(f"P{number}: {passage}" for passage, number in numbers.items()),
            "candidate-line": _claim_line(item.target),
            "candidate-text": item.statement.rstrip("\n"),
            "candidate-passages": ", ".join(f"P{number}" for number in sorted({numbers[p] for p in item.passages})),
        },
    )


def classify_asks(group: ClassifyGroup, items: Sequence[ClassifyItem]) -> tuple[LetterItem, ...]:
    """One source claim's classify asks, each named by its target's id.

    The group's passages are every item's, sorted and deduplicated and numbered
    ``P1``…, so each ask names its own by number against one shared list.
    """
    passages = sorted({passage for item in items for passage in item.passages})
    numbers = {passage: number for number, passage in enumerate(passages, start=1)}
    asks = []
    for item in items:
        offered = tuple(letter for letter in ClassifyLetter if letter in item.offered)
        compose = partial(_classify_prompt, group, item, numbers=numbers)
        asks.append(LetterItem(item.target.id, offered, compose))
    return tuple(asks)


@dataclass(frozen=True)
class UnmarkedGroup:
    """A source claim with its statement, and the leaf it is stated in: its path and its :func:`label.render` body."""

    document: str
    body: str
    source: ClaimNode
    statement: str


@dataclass(frozen=True)
class UnmarkedItem:
    """One shortlisted target, and its statement."""

    target: ClaimNode
    statement: str


def _unmarked_prompt(group: UnmarkedGroup, item: UnmarkedItem) -> str:
    return _letter_prompt(
        Kind.UNMARKED,
        {
            "document": group.document,
            "body": group.body.rstrip("\n"),
            "claim-line": _claim_line(group.source),
            "claim-text": group.statement.rstrip("\n"),
            "candidate-line": _claim_line(item.target),
            "candidate-text": item.statement.rstrip("\n"),
        },
    )


def unmarked_asks(group: UnmarkedGroup, items: Sequence[UnmarkedItem]) -> tuple[LetterItem, ...]:
    """One source claim's unmarked asks, each named by its target's id and offered both letters."""
    offered = tuple(UnmarkedLetter)
    return tuple(LetterItem(item.target.id, offered, partial(_unmarked_prompt, group, item)) for item in items)


@dataclass(frozen=True)
class ColinearItem:
    """One linked pair, named by ``key``: its two claims in reading order, each with its statement."""

    key: str
    first: ClaimNode
    first_statement: str
    second: ClaimNode
    second_statement: str


def _colinear_prompt(item: ColinearItem) -> str:
    return _letter_prompt(
        Kind.COLINEAR,
        {
            "first-line": _claim_line(item.first),
            "first-text": item.first_statement.rstrip("\n"),
            "second-line": _claim_line(item.second),
            "second-text": item.second_statement.rstrip("\n"),
        },
    )


def colinear_asks(items: Sequence[ColinearItem]) -> tuple[LetterItem, ...]:
    """One group's colinear asks, each named by its item's ``key`` and offered all three letters."""
    offered = tuple(ColinearLetter)
    return tuple(LetterItem(item.key, offered, partial(_colinear_prompt, item)) for item in items)


#: Characters a capture's file name keeps from the ask it is named after.
_FILE_NAME_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")
_FILE_STEM_MAX_CHARS = 150


@contextmanager
def _capture_path(captures: Path | None, question: LetterQuestion) -> Iterator[Path]:
    """Where one question's attempts are captured: under ``captures``, or in a spool that does not outlive the call.

    Named by the ask, its state's digest and its attempt ordinal — the re-ask's
    state is the first ask's, so the ordinal is what lands the two apart — and
    emptied first, so a resumed run asking again counts one call.
    """
    digest = sha256(question.prompt.encode("utf-8")).hexdigest()[:12]
    stem = _FILE_NAME_UNSAFE.sub("_", f"{question.kind}-{question.group}-{question.item}")[:_FILE_STEM_MAX_CHARS]
    name = f"{stem}-{digest}-{question.attempt}.capture.jsonl"
    if captures is None:
        with TemporaryDirectory(prefix="kb-letter-ask-") as spool:
            yield Path(spool) / name
        return
    captures.mkdir(parents=True, exist_ok=True)
    path = captures / name
    path.unlink(missing_ok=True)
    yield path


def _call_stats(capture: inference.CaptureStats) -> CallStats:
    """The capture's figures, under the names the ask record keeps: each attempt that reasoned is one thinking block."""
    return CallStats(
        duration_api_ms=capture.duration_ms,
        output_tokens=capture.completion_tokens,
        thinking_blocks=capture.reasoning_attempts,
        cache_read_input_tokens=capture.cached_tokens,
        prompt_tokens=capture.prompt_tokens,
    )


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def answer_confidence(
    answer: Mapping[str, object] | None, *, true_letter: str | None, offered: Sequence[str]
) -> dict[str, float] | None:
    """A decision answer as a per-letter confidence, or ``None`` where it decides nothing.

    By the answer's own ``type``: a ``choice`` answer gives its
    ``probabilities`` where it carries them, else its ``choice`` holding its
    ``confidence`` (0 where it carries none); a ``noul`` answer whose figure —
    0 where it carries none — is a probability gives ``true_letter`` that
    figure and, over a two-letter offer, the other letter the rest. Which letter wins is
    :func:`~.letters.decide`'s, over the offered letters only.
    """
    if answer is None:
        return None
    if answer.get("type") == prompt_templates.CHOICE:
        probabilities = answer.get("probabilities")
        if isinstance(probabilities, dict):
            return {letter: float(p) for letter, p in probabilities.items() if _is_number(p)}
        choice, confidence = answer.get("choice"), answer.get("confidence")
        if isinstance(choice, str) and choice:
            return {choice: float(confidence) if _is_number(confidence) else 0.0}
    elif answer.get("type") == prompt_templates.NOUL:
        # Absent is 0: an encoder omitting empty fields drops the figure of exactly a confident false.
        figure = answer.get("noul", 0.0)
        if true_letter is not None and _is_number(figure) and 0 <= float(figure) <= 1:
            confidence = {true_letter: float(figure)}
            others = [letter for letter in offered if letter != true_letter]
            if len(others) == 1:
                confidence[others[0]] = 1 - float(figure)
            return confidence
    return None


def ask_without_tools(question: LetterQuestion, *, captures: Path | None = None) -> Reply:
    """The production :class:`~.letters.LetterReader`: ``question`` put to the environment's decision model.

    One decision call: the composed prompt as the state, and the kind's question
    (:func:`question_name`) keyed by the item's name. ``captures`` is bound by
    the stage that holds it (``functools.partial``): where each call's attempts
    land — a spool discarded after the call where it is ``None``. Returns the
    answer as ``confidence`` (:func:`answer_confidence`) and no text.

    Raises :class:`AskError` where the call is refused, or never completed on
    any of :data:`TRANSPORT_ATTEMPTS`; :class:`ValueError` where
    :func:`~kb_tools.inference.check_environment` refuses the environment.
    """
    subject = f"{question.kind} ask {question.item!r} of {question.group!r}"
    asked = prompt_templates.load_question(
        question_name(question.kind, question.offered), constants=LETTER_SLOTS, offered=question.offered
    )
    decision = inference.DecisionQuestion(
        key=question.item, type=asked.type, instructions=asked.instructions, criteria=asked.criteria
    )
    model = inference.check_environment(chat=False, decision=True).decision_model
    with _capture_path(captures, question) as capture_path:
        where = f". Capture: {capture_path}" if captures is not None else ""
        for _attempt in range(TRANSPORT_ATTEMPTS):
            reply = inference.call_decision(
                question.prompt, decision, model=model, timeout_seconds=SOCKET_TIMEOUT_SECONDS, capture=capture_path
            )
            if reply.outcome is inference.Outcome.TRANSPORT_FAILURE:
                continue
            if reply.outcome is inference.Outcome.REFUSED:
                raise AskError("inference-failed", f"{subject}: the server refused the call{where}")
            confidence = answer_confidence(
                reply.answers.get(question.item), true_letter=asked.true_letter, offered=question.offered
            )
            return Reply(
                text="", confidence=confidence, stats=_call_stats(inference.read_decision_capture(capture_path))
            )
    raise AskError(
        "inference-failed",
        f"{subject}: the call ended {inference.Outcome.TRANSPORT_FAILURE.value} and was re-issued identically to "
        f"no effect. No answer is assumed for a call that did not complete{where}",
    )
