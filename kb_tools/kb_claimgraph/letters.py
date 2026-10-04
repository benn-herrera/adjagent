"""Letter asks: one decision per ask, answered with one letter from a closed set the build offers.

**The stage owns every decision; the reader owns only the call.** A
:class:`LetterReader` takes a :class:`LetterQuestion` — a composed prompt and
the letters it offers — and returns a :class:`Reply`: the text that came back,
and, from a reader that can give one, a probability per label. What the reply
*means* is :func:`decide`'s, the one re-ask and the default are
:func:`ask_group`'s, and the record is this module's. A reader raises
:class:`~.ask.AskError` where its call never completed, and that is the only
thing that stops a group: a reply that carries no offered letter is re-asked
once and then left without one, for the caller to give its stated default.

**What prompts say is not here.** :mod:`ask` composes every kind and hands each
item over as a :class:`LetterItem` whose ``compose`` turns "what came back last
time" (``None`` on a first ask) into the prompt. The re-ask is therefore the
first prompt with a correction after its question, sharing its whole prefix.

**A group shares a prefix, so its first ask runs alone.** The server prefills
and caches the group's context on that call, and the rest run with
:func:`reader_concurrency` asks in flight. Results are kept in item order
whatever order the calls finish in, so concurrency never changes what a caller
writes or the order its record lands in.
"""

import json
import logging
import os
import time
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from .report import ClaimGraphError

_log = logging.getLogger(__name__)

#: The environment variable naming how many asks of one group are in flight
#: once its first ask has completed. Read at the point of use; absent means
#: :data:`DEFAULT_READER_CONCURRENCY`.
READER_CONCURRENCY_ENV = "KB_READER_CONCURRENCY"
DEFAULT_READER_CONCURRENCY = 4


class Kind(StrEnum):
    """The letter asks: a paragraph of the node pass, an edge candidate of classification, an unmarked pair."""

    PARAGRAPH = "paragraph"
    CLASSIFY = "classify"
    UNMARKED = "unmarked"


@dataclass(frozen=True)
class LetterQuestion:
    """One ask as a reader receives it. ``group`` and ``item`` name it; ``prompt`` is all it says."""

    kind: Kind
    group: str
    item: str
    prompt: str
    offered: tuple[str, ...]


@dataclass(frozen=True)
class CallStats:
    """What a reader measured of its own call; ``None`` where the call did not report the figure."""

    duration_api_ms: int | None
    output_tokens: int | None
    thinking_blocks: int
    cache_read_input_tokens: int | None
    prompt_tokens: int | None


@dataclass(frozen=True)
class Reply:
    """What came back. ``confidence`` is a per-label distribution, from a reader that has one."""

    text: str
    confidence: Mapping[str, float] | None = None
    stats: CallStats | None = None


class LetterReader(Protocol):
    def __call__(self, question: LetterQuestion) -> Reply:
        """Put ``question`` to a model. Raises :class:`~.ask.AskError` where the call never completed."""


def decide(reply: Reply, offered: Sequence[str]) -> str | None:
    """The offered letter ``reply`` chose, or ``None`` where it chose none.

    Where the reader supplied ``confidence``, the argmax over the *offered*
    letters it scored, the first offered winning a tie; otherwise the strict
    parse: after stripping whitespace, exactly one character, and an offered
    one.
    """
    confidence = reply.confidence
    if confidence is not None:
        scored = [letter for letter in offered if letter in confidence]
        return max(scored, key=confidence.__getitem__) if scored else None
    text = reply.text.strip()
    return text if len(text) == 1 and text in offered else None


class AskOutcome(StrEnum):
    """How an item's letter was reached. ``defaulted`` carries no letter."""

    ANSWERED = "answered"
    REASKED = "re-asked"
    DEFAULTED = "defaulted"


@dataclass(frozen=True)
class LetterItem:
    """One item of a group: its name, its letters, and its prompt given what came back last time."""

    item: str
    offered: tuple[str, ...]
    compose: Callable[[str | None], str]


@dataclass(frozen=True)
class CallRecord:
    """One call: the prompt past the group's shared prefix, what came back, and what it cost."""

    tail: str
    reply: str
    confidence: Mapping[str, float] | None
    letter: str | None
    wall_seconds: float
    stats: CallStats | None


@dataclass(frozen=True)
class ItemRecord:
    item: str
    offered: tuple[str, ...]
    letter: str | None
    outcome: AskOutcome
    confidence: Mapping[str, float] | None
    calls: tuple[CallRecord, ...]


@dataclass(frozen=True)
class GroupRecord:
    """One group's asks: the prefix every prompt in it opens with, once, and every item in order."""

    kind: Kind
    group: str
    prefix: str
    items: tuple[ItemRecord, ...]


def reader_concurrency() -> int:
    """How many asks of a group run at once after its first. An operator's value, so it is checked."""
    raw = os.environ.get(READER_CONCURRENCY_ENV, str(DEFAULT_READER_CONCURRENCY))
    try:
        value = int(raw)
    except ValueError:
        value = 0
    if value < 1:
        raise ClaimGraphError(
            "reader-concurrency", f"{READER_CONCURRENCY_ENV}={raw!r}: the value is a whole number of asks, at least 1"
        )
    return value


@dataclass(frozen=True)
class _Call:
    prompt: str
    reply: Reply
    letter: str | None
    wall_seconds: float


def _call(reader: LetterReader, question: LetterQuestion) -> _Call:
    started = time.monotonic()
    reply = reader(question)
    wall = time.monotonic() - started
    return _Call(question.prompt, reply, decide(reply, question.offered), wall)


def _resolve(reader: LetterReader, *, kind: Kind, group: str, entry: LetterItem) -> tuple[_Call, ...]:
    """An item's calls: the first ask, and the one re-ask where it carried no offered letter."""

    def question(returned: str | None) -> LetterQuestion:
        return LetterQuestion(kind, group, entry.item, entry.compose(returned), entry.offered)

    first = _call(reader, question(None))
    if first.letter is not None:
        return (first,)
    return (first, _call(reader, question(first.reply.text)))


def _shared_prefix(prompts: Sequence[str]) -> str:
    """The longest run of whole lines every prompt opens with."""
    common = os.path.commonprefix(list(prompts))
    return common[: common.rfind("\n") + 1]


def _item_record(entry: LetterItem, calls: tuple[_Call, ...], *, prefix: str) -> ItemRecord:
    last = calls[-1]
    if last.letter is None:
        outcome = AskOutcome.DEFAULTED
    else:
        outcome = AskOutcome.ANSWERED if len(calls) == 1 else AskOutcome.REASKED
    return ItemRecord(
        item=entry.item,
        offered=entry.offered,
        letter=last.letter,
        outcome=outcome,
        confidence=last.reply.confidence,
        calls=tuple(
            CallRecord(
                tail=call.prompt[len(prefix) :],
                reply=call.reply.text,
                confidence=call.reply.confidence,
                letter=call.letter,
                wall_seconds=call.wall_seconds,
                stats=call.reply.stats,
            )
            for call in calls
        ),
    )


def group_record_path(directory: Path, *, kind: Kind, group: str) -> Path:
    """Where a group's ask record lands under ``directory``."""
    return directory / f"{kind}-{group.replace('/', '_')}.json"


def ask_group(
    *,
    kind: Kind,
    group: str,
    items: Sequence[LetterItem],
    reader: LetterReader,
    record_dir: Path | None = None,
) -> GroupRecord:
    """Ask every item of one group and return its record, items in the order given.

    The first item is resolved alone, then the rest with
    :func:`reader_concurrency` in flight. An :class:`~.ask.AskError` from any
    call propagates once the calls already in flight have returned, and no
    record is written for the group. Where ``record_dir`` is given the record
    lands there as JSON once every item has its outcome.
    """
    if not items:
        return GroupRecord(kind, group, "", ())
    resolved = [_resolve(reader, kind=kind, group=group, entry=items[0])]
    with ThreadPoolExecutor(max_workers=reader_concurrency()) as pool:
        resolved += pool.map(lambda entry: _resolve(reader, kind=kind, group=group, entry=entry), items[1:])
    prefix = _shared_prefix([call.prompt for calls in resolved for call in calls])
    record = GroupRecord(
        kind=kind,
        group=group,
        prefix=prefix,
        items=tuple(_item_record(entry, calls, prefix=prefix) for entry, calls in zip(items, resolved, strict=True)),
    )
    if record_dir is not None:
        record_dir.mkdir(parents=True, exist_ok=True)
        path = group_record_path(record_dir, kind=kind, group=group)
        path.write_text(json.dumps(asdict(record), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    defaulted = sum(item.outcome is AskOutcome.DEFAULTED for item in record.items)
    if defaulted:
        _log.warning("%s group %s: %d of %d item(s) defaulted", kind, group, defaulted, len(record.items))
    return record


@dataclass(frozen=True)
class AskTotals:
    """What a stage's letter asks cost and how they ended, summed for its report.

    ``warm_*`` covers every call but the first of each group — the calls a
    cached prefix can serve — so their ratio is the cache share. ``unmeasured``
    counts calls whose reader reported no :class:`CallStats`, which every sum
    beside it then leaves out.
    """

    items: int
    answered: int
    reasked: int
    defaulted: int
    calls: int
    unmeasured: int
    thinking_blocks: int
    output_tokens: int
    wall_seconds: float
    api_seconds: float
    warm_prompt_tokens: int
    warm_cache_read_tokens: int

    @classmethod
    def of(cls, records: Sequence[GroupRecord]) -> "AskTotals":
        groups = [[call for item in record.items for call in item.calls] for record in records]
        outcomes = [item.outcome for record in records for item in record.items]
        calls = [call for group in groups for call in group]
        warm = [call for group in groups for call in group[1:]]
        measured = [call.stats for call in calls if call.stats is not None]
        warm_stats = [call.stats for call in warm if call.stats is not None]
        return cls(
            items=len(outcomes),
            answered=outcomes.count(AskOutcome.ANSWERED),
            reasked=outcomes.count(AskOutcome.REASKED),
            defaulted=outcomes.count(AskOutcome.DEFAULTED),
            calls=len(calls),
            unmeasured=len(calls) - len(measured),
            thinking_blocks=sum(stats.thinking_blocks for stats in measured),
            output_tokens=sum(stats.output_tokens or 0 for stats in measured),
            wall_seconds=sum(call.wall_seconds for call in calls),
            api_seconds=sum(stats.duration_api_ms or 0 for stats in measured) / 1000,
            warm_prompt_tokens=sum(stats.prompt_tokens or 0 for stats in warm_stats),
            warm_cache_read_tokens=sum(stats.cache_read_input_tokens or 0 for stats in warm_stats),
        )

    def detail(self) -> str:
        """The totals as one report detail, every figure present so a zero reads as zero."""
        per_call = self.wall_seconds / self.calls if self.calls else 0.0
        return (
            f"items={self.items} answered={self.answered} re-asked={self.reasked} defaulted={self.defaulted} "
            f"calls={self.calls} unmeasured={self.unmeasured} thinking-blocks={self.thinking_blocks} "
            f"output-tokens={self.output_tokens} seconds-per-call={per_call:.2f} "
            f"wall-seconds={self.wall_seconds:.1f} api-seconds={self.api_seconds:.1f} "
            f"warm-cache-read={self.warm_cache_read_tokens}/{self.warm_prompt_tokens}"
        )
