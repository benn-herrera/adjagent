"""This package's asks: what is asked, how it is asked, and the reader that asks it.

**Every claim-graph ask is a letter ask**: one decision, answered with one
letter from a closed set (:mod:`letters`). Three kinds. A **paragraph** ask puts
one paragraph of a leaf to the reader — does it state a result — with the leaf as
:mod:`label` renders it for context; its group is the leaf. A **classify** ask
puts one edge candidate — is the source *supported by* it, *in support of* it,
or does it merely *mention* it — with the source claim and the passages its
references sit in for context; its group is the source claim. An **unmarked**
ask puts one shortlisted pair — does the source claim's text point at the
candidate's result with no cross-reference — with the source's leaf and its
statement for context; its group is the source claim.

**One letter-to-meaning table per kind** (:class:`ParagraphLetter`,
:class:`ClassifyLetter`, :class:`UnmarkedLetter`). A question offering fewer meanings withholds their
letters and never relabels the rest, so a letter means one thing in every ask
of its kind. The letters reach a template only as composer constants
(:data:`LETTER_SLOTS`): a template spelling one would be a second definition of
the string the parse holds the reader to.

**The group's context comes first and the question last.** Every slot of an
item (:data:`ITEM_SLOTS`) sits in a template's final section, after every slot
of its group, so every ask of a group opens with the same bytes and a server
can serve that prefix from cache. A re-ask is the same prompt with a correction
after the question — ``letter-correction``, carrying what came back, cut to
:data:`RETURNED_MAX_CHARS` — so it shares the whole prefix too. No prompt is
written here: each is a template under ``kb_driver/prompt-templates/``, and
this module hands the composer values and the names of the alternatives it
chose.

**The reader is a system prompt and one tool-less chat call.**
:func:`ask_without_tools` is the production :class:`~.letters.LetterReader`:
the :data:`READER_SYSTEM` fragment as the system prompt, through
:func:`kb_tools.inference.call_chat` on the environment's model, so an answer
rests on the prompt and nothing a model chose to look at. Its capture is read
by :func:`kb_tools.inference.read_capture` into :class:`~.letters.CallStats`.
A call that did not reach ``[DONE]`` is re-issued identically up to
:data:`TRANSPORT_ATTEMPTS`, and so is one the server answered without
processing a token; a call that never completes raises :class:`AskError`,
which is the one thing that stops a stage — no answer arrived, and defaulting
every remaining item would hide a dead model behind what looks like a finished
run.
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

#: The slot a re-ask's correction fills, after the question.
CORRECTION_SLOT = "correction"

#: How long one blocking socket operation of a call — the connect, or a read of
#: its stream — may wait. The outer edge of "something is wrong", not an
#: expectation; nothing bounds the call as a whole.
SOCKET_TIMEOUT_SECONDS = 600.0

#: The fragment that is a claim-graph ask's whole system prompt.
READER_SYSTEM = "reader-system"


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
    """The unmarked ask's letters: does the source claim's text point at the candidate's result."""

    POINTS = kb_pipeline.UNMARKED_POINTS_LETTER
    DOES_NOT = "B"


#: The letters as the letter templates and their fragments name them.
LETTER_SLOTS: Mapping[str, str] = MappingProxyType(
    {
        "letter-claim": ParagraphLetter.CLAIM,
        "letter-not-a-claim": ParagraphLetter.NOT_A_CLAIM,
        "letter-supported-by": ClassifyLetter.SUPPORTED_BY,
        "letter-in-support-of": ClassifyLetter.IN_SUPPORT_OF,
        "letter-mention": ClassifyLetter.MENTION,
        "letter-points": UnmarkedLetter.POINTS,
        "letter-does-not-point": UnmarkedLetter.DOES_NOT,
    }
)

LETTER_TEMPLATES: Mapping[Kind, str] = MappingProxyType(
    {Kind.PARAGRAPH: "paragraph.tmpl.md", Kind.CLASSIFY: "classify.tmpl.md", Kind.UNMARKED: "unmarked.tmpl.md"}
)

#: Each kind's per-item slots, as a template spells them. Everything before the
#: first of them is the group's and identical across the group's asks.
ITEM_SLOTS: Mapping[Kind, tuple[str, ...]] = MappingProxyType(
    {
        Kind.PARAGRAPH: ("dyn.paragraph", "dyn.paragraph-text", "correction"),
        Kind.CLASSIFY: (
            "dyn.candidate-line",
            "dyn.candidate-text",
            "dyn.candidate-passages",
            "classify-options",
            "correction",
        ),
        Kind.UNMARKED: ("dyn.candidate-line", "dyn.candidate-text", "correction"),
    }
)

LETTER_CORRECTION = "letter-correction"
CLASSIFY_OPTIONS_SLOT = "classify-options"

#: The closing question a classify ask carries, by the letters it offers. Every
#: offered set holds *supported by* and *mention*; *in support of* is the one a
#: candidate may be refused.
CLASSIFY_OPTIONS: Mapping[frozenset[ClassifyLetter], str] = MappingProxyType(
    {
        frozenset(ClassifyLetter): "classify-options-three",
        frozenset({ClassifyLetter.SUPPORTED_BY, ClassifyLetter.MENTION}): "classify-options-two",
    }
)

#: How much of an unreadable reply a re-ask shows back to the reader.
RETURNED_MAX_CHARS = 400


def _letter_prompt(
    kind: Kind, slots: Mapping[str, str], returned: str | None, *, alternatives: Mapping[str, str] | None = None
) -> str:
    """One letter ask of ``kind`` over ``slots``: a first ask's correction empty, a re-ask's carrying the reply cut short."""
    if returned is None:
        correction: dict[str, str] = {}
        chosen: str | None = None
    else:
        correction, chosen = {"returned": returned.strip()[:RETURNED_MAX_CHARS]}, LETTER_CORRECTION
    return prompt_templates.render(
        LETTER_TEMPLATES[kind],
        slots={**slots, **correction},
        constants=LETTER_SLOTS,
        alternatives={**(alternatives or {}), CORRECTION_SLOT: chosen},
    )


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


def _paragraph_prompt(group: ParagraphGroup, item: ParagraphItem, returned: str | None) -> str:
    return _letter_prompt(
        Kind.PARAGRAPH,
        {
            "document": group.document,
            "body": group.body.rstrip("\n"),
            "paragraph": item.paragraph,
            "paragraph-text": item.text.rstrip("\n"),
        },
        returned,
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


def _classify_prompt(
    group: ClassifyGroup,
    item: ClassifyItem,
    returned: str | None,
    *,
    numbers: Mapping[str, int],
    offered: tuple[ClassifyLetter, ...],
) -> str:
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
        returned,
        alternatives={CLASSIFY_OPTIONS_SLOT: CLASSIFY_OPTIONS[frozenset(offered)]},
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
        compose = partial(_classify_prompt, group, item, numbers=numbers, offered=offered)
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


def _unmarked_prompt(group: UnmarkedGroup, item: UnmarkedItem, returned: str | None) -> str:
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
        returned,
    )


def unmarked_asks(group: UnmarkedGroup, items: Sequence[UnmarkedItem]) -> tuple[LetterItem, ...]:
    """One source claim's unmarked asks, each named by its target's id and offered both letters."""
    offered = tuple(UnmarkedLetter)
    return tuple(LetterItem(item.target.id, offered, partial(_unmarked_prompt, group, item)) for item in items)


#: Characters a capture's file name keeps from the ask it is named after.
_FILE_NAME_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")
_FILE_STEM_MAX_CHARS = 150


@contextmanager
def _capture_path(captures: Path | None, question: LetterQuestion) -> Iterator[Path]:
    """Where one question's stream is captured: under ``captures``, or in a spool that does not outlive the call.

    Named by the ask and its prompt's digest, so a first ask and its re-ask land
    apart, and emptied first, so a resumed run asking again counts one call.
    """
    digest = sha256(question.prompt.encode("utf-8")).hexdigest()[:12]
    stem = _FILE_NAME_UNSAFE.sub("_", f"{question.kind}-{question.group}-{question.item}")[:_FILE_STEM_MAX_CHARS]
    name = f"{stem}-{digest}.capture.jsonl"
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


def _served_nothing(stats: CallStats) -> bool:
    """Whether the server reports neither reading the prompt nor writing a token.

    The stream reaches ``[DONE]`` and hands on whatever text came back as the
    reply. A server aborting a request (out of memory, say) answers that way,
    with its error message as the text; a call that ran reports the prompt it
    read. Counts the stream does not carry decide nothing.
    """
    return stats.prompt_tokens == 0 and stats.output_tokens == 0


def ask_without_tools(question: LetterQuestion, *, captures: Path | None = None) -> Reply:
    """The production :class:`~.letters.LetterReader`: ``question`` put to the environment's model with no tools.

    ``captures`` is bound by the stage that holds it (``functools.partial``):
    where each call's stream lands — a spool discarded after the call where it
    is ``None``. Returns no ``confidence``.

    Raises :class:`AskError` where the call never completed, or the server
    served it without reading the prompt, on every one of
    :data:`TRANSPORT_ATTEMPTS`; :class:`ValueError` where
    :func:`~kb_tools.inference.call_chat` refuses the environment.
    """
    subject = f"{question.kind} ask {question.item!r} of {question.group!r}"
    system_prompt = prompt_templates.render(prompt_templates.FRAGMENTS[READER_SYSTEM], slots={})
    with _capture_path(captures, question) as capture_path:
        for _attempt in range(TRANSPORT_ATTEMPTS):
            text, outcome = inference.call_chat(
                system_prompt=system_prompt,
                prompt=question.prompt,
                timeout_seconds=SOCKET_TIMEOUT_SECONDS,
                capture_path=capture_path,
            )
            if not outcome.ok:
                ended = outcome.value
                continue
            stats = _call_stats(inference.read_capture(capture_path))
            if not _served_nothing(stats):
                return Reply(text=text, stats=stats)
            ended = "with no token read or written"
    raise AskError(
        "inference-failed",
        f"{subject}: the call ended {ended} and was re-issued identically to no effect. "
        f"No answer is assumed for a call that did not complete"
        + (f". Capture: {capture_path}" if captures is not None else ""),
    )
