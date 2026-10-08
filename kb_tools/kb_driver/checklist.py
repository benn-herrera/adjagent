"""The one parse of ``show-status``'s checklist block, and of a console it was relayed into.

``kb_pipeline`` writes the block (``checklist_lines``); the driver reads the
render back across a process boundary, through the ``kb_util show-status``
subprocess adapter (``ledger.show_status``). So the format travels as text and
is parsed here, once — a second regex over the same render is how two readings
of one format start to disagree.

The driver relays every status render it gets, and its relay card, to its
stdout, so a detached build's console log carries both: :func:`read_console`
lifts the newest whole status card and the relay card back out of it, with the
span of console text between them, for ``kb_util await-build``.

Stdlib only.
"""

import re
from dataclasses import dataclass
from itertools import accumulate

from .. import kb_pipeline
from . import baton, runlog

# The checklist block is the only thing in a render matching `^\[[x* ]\] `
# (kb_pipeline._print_report), which is what makes it liftable without knowing
# about the rest of the render. `[x]` is recorded; `[*]` and `[ ]` are not.
_CHECKLIST_RE = re.compile(r"^\[([x* ])\] (\S+)", re.MULTILINE)


def recorded_stages(render: str) -> frozenset[str]:
    """The recorded stage ids in a ``show-status`` render — a format, not prose."""
    markers = _CHECKLIST_RE.findall(render)
    # A render with no checklist at all would read as a build with nothing
    # recorded, which is a resumable position the walk would act on. That is
    # drift in the tool's output shape, not a pipeline outcome: exit 15.
    runlog.require(markers, "show-status printed no checklist block")
    return frozenset(stage for marker, stage in markers if marker == "x")


@dataclass(frozen=True)
class ConsoleTail:
    """What a console log holds whole: its newest status card and its relay card, as lines.

    Either is empty where the log holds none whole yet. ``span`` is the slice of the console text
    from the start of the newest card through the end of the relay card's closing line, or through
    the card's own end where there is no relay card; ``(0, 0)`` where there is no card.
    """

    card: tuple[str, ...] = ()
    relay: tuple[str, ...] = ()
    span: tuple[int, int] = (0, 0)


def _card_at(lines: list[str], start: int) -> tuple[str, ...]:
    """The status card opening at ``lines[start]``, or empty where it is not all there.

    A card is the status line, at most one note line, then one checklist line
    per stage (``kb_pipeline._print_report``).
    """
    first = start + 1
    if first < len(lines) and not _CHECKLIST_RE.match(lines[first]):
        first += 1
    block = lines[first : first + len(kb_pipeline.STAGES)]
    if len(block) < len(kb_pipeline.STAGES) or not all(_CHECKLIST_RE.match(line) for line in block):
        return ()
    return tuple(lines[start : first + len(block)])


def read_console(text: str) -> ConsoleTail:
    """The newest whole status card in ``text``, and the relay card, once it is whole.

    ``text`` may still be being written: a last line with no line ending is
    left out, a card short of its checklist is not yet a card, and a relay card
    whose closing rule has not arrived is not yet one either. A relay card closed
    before the newest card opens is not this card's relay and is left out.
    """
    lines = text.splitlines()
    line_ends = list(accumulate(len(raw) for raw in text.splitlines(keepends=True)))
    if lines and not text.endswith(("\n", "\r")):
        lines.pop()
        line_ends.pop()
    cards = [
        (index, _card_at(lines, index)) for index, line in enumerate(lines) if line.startswith(kb_pipeline.STATUS_PREFIX)
    ]
    whole = [(index, card) for index, card in cards if card]
    if not whole:
        return ConsoleTail()
    card_index, card = whole[-1]
    card_start = line_ends[card_index - 1] if card_index else 0
    span_end = line_ends[card_index + len(card) - 1]
    rules = [index for index, line in enumerate(lines) if line == baton.RULE_LINE]
    relay: tuple[str, ...] = ()
    if rules and len(rules) % 2 == 0 and rules[-1] > card_index:
        relay = tuple(lines[rules[-2] : rules[-1] + 1])
        span_end = line_ends[rules[-1]]
    return ConsoleTail(card=card, relay=relay, span=(card_start, span_end))
