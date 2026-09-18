"""The record toolkit a model-facing format is built from, and the one such format left here.

The driver parses formats, never prose. This module owns the toolkit every
format that arrives inside a model's returned text is assembled from, and the
one format of that kind the driver still reads for itself: the review
**VERDICT** line — the reviewer judges, the driver counts.

The toolkit's other consumer is :mod:`kb_tools.kb_claimgraph.ask`, which builds
both claim-graph inference asks out of it. **The toolkit is the substance of
this module and the VERDICT line is a tenant**; the two are together because a
format is what a toolkit is for, not because either needs the other.

**One data language, and it is JSON.** Between a block's two marker lines is one
JSON document and nothing else. A seat has strong priors for JSON and none for a
grammar described to it once per invocation, and a decode failure names a line
and a column it can act on where *"line 3 does not match the token grammar"* is a
puzzle.

**Nothing a seat composes or quotes travels inside that JSON.** Structure — an
id, a step name, an enum member, a reference — cannot carry a backslash, and
words can. A first live run stopped on ``Invalid \\escape`` because a seat quoted
an author who writes mathematics, and the two classes of sequence fail
differently: one that is not a JSON escape (``\\sigma``) fails loudly, and one
that is (``\\beta`` decodes to a backspace, and ``\\t``, ``\\r`` and ``\\f``
behave the same way) decodes to something else and fails later, silently.
Escaping at the seat only moves the burden up a level, because a tool call
carrying the text is itself JSON. So **prose travels in raw delimited blocks
beside the JSON**, whose content is taken verbatim between its delimiters: no
escape sequence exists anywhere in the transport, and a phrase stating
``$\\sigma$`` is a phrase stating ``$\\sigma$``.

That transport has two forms, and **only the second has a caller today**.
:class:`ProseBlocks` is the numbered form, where the JSON names a block by its
index; every site that resolved an index that way has retired, so what is left
of it is the refusal — a record declaring no prose key still refuses a prose
block, which is what makes an empty declaration a check rather than an omission.
:func:`extract_field_blocks` is the form that carries a closed, fixed set of
single-line fields and **drops the index**, because an index is a pointer a seat
maintains and a wrong pointer is undetectable. It is not a departure from the
data-language rule but an answer to the same two objections on their own terms:
a ``quote:`` / ``label:`` / ``title:`` form has priors as strong as JSON's, and
its failures name themselves — *"the block has no label: line"* is as actionable
as a decode error naming a line and a column. No field nests, quotes or
balances, so the grammar's only failure is a missing, repeated or misspelled
field name, and **that failure is local to one block**: a malformed block is
refused by itself and the blocks beside it are still read. JSON with positional
pairing was considered and rejected — it is the same pointer with the number
erased, and it converts a detectable mismatch into a silent one.

**Every vocabulary is closed and total** (:func:`check_keys`), in both
directions: a key left out is refused by name, and so is a key added. Typing is
what makes a refusal structural rather than a rule someone remembered to write —
a line of English inside a block is a decode failure wherever it sits. Each
object level additionally declares **which of its keys travel in which
transport**, and :func:`check_levels` proves the declarations partition the
level's key set — total and disjoint, on ``check_keys``' own terms — at import.
A declaration leaving one key unclassified would not be the closed thing the
rest of this module is.

The record toolkit below was once ``kb_survey.blocks``, shared because the
design document's coverage and DOMAINS blocks were read off disk by the survey
validator as well as returned to this module. Neither block exists any more —
the document tree is derived from the sources rather than authored, and the
driver's domain partition is walked off that tree.

Validation is **parse only** — block present, JSON parses, required keys
present, vocabulary respected. Never content quality; that is the reviewers'
job. A failure raises :class:`ParseError`, which ``call.py`` turns into one
re-ask and then exit 17.

Stdlib only.
"""

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import NamedTuple


class ParseError(ValueError):
    """A returned artifact does not carry its declared structure. Exit 17 after one re-ask."""


# --- the JSON record toolkit -------------------------------------------------
#
# Every refusal names the offending key or value, because the reader is a model
# whose next act is one re-ask.


def extract_blocks(text: str, *, open_marker: str, close_marker: str, label: str) -> tuple[str, ...]:
    """The body of every ``open_marker`` … ``close_marker`` block in ``text``, in order.

    Markers are matched as whole stripped lines, so a block can be named inside
    prose without opening one. Zero blocks is a legal answer here; whether it is
    a legal answer *there* is the caller's question.

    **A line ends at ``\\n`` and nowhere else.** ``str.splitlines`` also
    breaks on U+2028, U+2029, form feed, vertical tab and the file/group/record
    separators — none of them a line break in the grammar this module declares, every
    one of them emittable inside a model's returned text. Splitting there turns one
    physical line into two accepted ones, which is how a marker line acquires an
    invisible tail. A trailing ``\\r`` is stripped so a CRLF document reads exactly
    as it did.

    **An unclosed block is the one failure that is not local to its block.** It
    swallows every line after it, so the blocks behind it cannot be read at all
    and there is nothing to report them against.
    """
    bodies: list[str] = []
    current: list[str] | None = None
    for raw_line in text.split("\n"):
        line = raw_line.rstrip("\r")
        stripped = line.strip()
        if current is None:
            if stripped == open_marker:
                current = []
        elif stripped == close_marker:
            bodies.append("\n".join(current))
            current = None
        else:
            current.append(line)

    if current is not None:
        raise ParseError(f"{label}: a {open_marker!r} block was never closed with {close_marker!r}")
    return tuple(bodies)


def extract_block(text: str, *, open_marker: str, close_marker: str, label: str) -> str:
    """The body of the **one** ``open_marker`` … ``close_marker`` block in ``text``."""
    bodies = extract_blocks(text, open_marker=open_marker, close_marker=close_marker, label=label)
    if not bodies:
        raise ParseError(f"{label}: no {open_marker!r} block in the returned text")
    if len(bodies) > 1:
        raise ParseError(f"{label}: {len(bodies)} {open_marker!r} blocks; exactly one is required")
    return bodies[0]


def parse_json_block(text: str, *, open_marker: str, close_marker: str, label: str) -> object:
    """The one block's body, decoded. A decode failure carries its own line and column."""
    body = extract_block(text, open_marker=open_marker, close_marker=close_marker, label=label)
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise ParseError(f"{label}: the block is not valid JSON: {exc}") from exc


def check_keys(record: Mapping[str, object], keys: Sequence[str], *, label: str) -> None:
    """The vocabulary is closed and total: a key missing is refused, and so is a key added.

    An added key is not noise to drop. It is a seat that emitted something
    nobody asked for, which impugns what it put in the keys that *were* asked
    for — and discarding it silently throws away the one signal that the rest of
    the return may be unsound.
    """
    missing = [key for key in keys if key not in record]
    if missing:
        raise ParseError(f"{label}: missing required key(s): {', '.join(missing)}")
    unknown = [key for key in record if key not in keys]
    if unknown:
        raise ParseError(
            f"{label}: unknown key(s): {', '.join(unknown)}; the vocabulary is closed and total, "
            f"and takes exactly: {', '.join(keys)}"
        )


def string_array(value: object, *, label: str) -> tuple[str, ...]:
    """``value`` as a JSON array of strings, or a refusal naming what arrived instead."""
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ParseError(f"{label}: must be an array of strings, got {type(value).__name__}")
    return tuple(value)


def string_field(record: Mapping[str, object], key: str, *, label: str) -> str:
    """One non-empty string field.

    For keys carrying **structure** only — an id, a step name, an enum member, a
    reference. A key carrying words the seat composed travels in a raw delimited
    block instead, and the level's declaration is what says which is which.
    """
    value = record[key]
    if not isinstance(value, str) or not value.strip():
        raise ParseError(f"{label}: {key} must be a non-empty string, got {value!r}")
    return value


# --- the prose blocks beside the JSON ----------------------------------------


class ProseBlocks:
    """The numbered raw delimited blocks a returned record may carry its own words in.

    One block per value, opened by ``<<<<NAME> <n>`` and closed by ``<NAME> <n>``
    on lines of their own, with the JSON referring to it by that number. **The
    content between the delimiters would be taken verbatim** — not decoded, not
    unescaped, not stripped — which is the whole point of the form: there is no
    escape grammar in this transport for a seat to get wrong, and no sequence
    that means something other than itself.

    **No surviving record declares a prose key**, so the resolution half of that
    form has no caller and what is left is the refusal. Every block a record
    carries is therefore one no key names, which is not noise to drop: it is
    words the seat composed and nothing reads, refused on the same argument
    :func:`check_keys` makes about an invented key. A record that starts
    declaring a prose key again owes this class the reader that resolves one.
    """

    def __init__(self, blocks: Mapping[int, str], *, name: str, label: str) -> None:
        self._blocks = dict(blocks)
        self._name = name
        self._label = label

    def check_exhausted(self) -> None:
        """Every block returned has a key that names it, and no key names one."""
        orphans = sorted(self._blocks)
        if orphans:
            raise ParseError(
                f"{self._label}: {self._name} block(s) {', '.join(str(index) for index in orphans)} are named "
                f"by no key; a block nothing refers to is prose the answer composed and nothing reads"
            )


def extract_prose_blocks(text: str, *, name: str, label: str) -> ProseBlocks:
    """Every ``name`` block in ``text``, by its number.

    Markers are matched as whole stripped lines and a line ends at ``\\n`` and
    nowhere else, on :func:`extract_block`'s terms and for its reasons.
    """
    opening = re.compile(rf"^<<<{re.escape(name)}[ \t]+(\d+)$")
    closing = re.compile(rf"^{re.escape(name)}[ \t]+(\d+)$")
    blocks: dict[int, str] = {}
    number: int | None = None
    body: list[str] = []

    for raw_line in text.split("\n"):
        line = raw_line.rstrip("\r")
        stripped = line.strip()
        if number is None:
            opened = opening.match(stripped)
            if opened is not None:
                number, body = int(opened.group(1)), []
            continue
        closed = closing.match(stripped)
        if closed is None:
            body.append(line)
            continue
        if int(closed.group(1)) != number:
            raise ParseError(
                f"{label}: the {name} block opened as {number} is closed as {closed.group(1)}; a block's "
                f"two markers carry one number"
            )
        if number in blocks:
            raise ParseError(f"{label}: two {name} blocks are numbered {number}; a number names one block")
        blocks[number] = "\n".join(body)
        number = None

    if number is not None:
        raise ParseError(f"{label}: the {name} block numbered {number} was never closed")
    return ProseBlocks(blocks, name=name, label=label)


# --- the raw block carrying a closed, fixed set of single-line fields --------


#: One field line: a slot-shaped name, a colon, and the rest of the line. The
#: value runs to the end of the line and is taken as it stands — no quoting, no
#: continuation, no escape — so the only thing that can be malformed here is the
#: name in front of the colon.
_FIELD_LINE = re.compile(r"^([a-z][a-z0-9]*(?:-[a-z0-9]+)*):[ \t]?(.*)$")


class FieldBlocks(NamedTuple):
    """What :func:`extract_field_blocks` read, and what it refused, side by side.

    The two travel together because neither is the answer on its own: blocks
    with no refusals is a clean read, refusals with no blocks is an answer that
    named nothing, and a mixture is the ordinary partial case this class exists
    to make expressible.
    """

    blocks: tuple[Mapping[str, str], ...] = ()
    refusals: tuple[str, ...] = ()


def _field_block(body: str, *, keys: Sequence[str], label: str) -> Mapping[str, str]:
    """One block's fields, against a vocabulary closed and total on :func:`check_keys`' terms."""
    fields: dict[str, str] = {}
    for line in body.split("\n"):
        if not line.strip():
            continue
        match = _FIELD_LINE.match(line.strip())
        if match is None:
            raise ParseError(
                f"{label}: {line.strip()[:60]!r} is not a field line. Every line of this block is "
                f"'<field>: <value>' on one line, and takes exactly: {', '.join(keys)}"
            )
        key, value = match.group(1), match.group(2).strip()
        if key not in keys:
            raise ParseError(
                f"{label}: unknown field {key!r}; the vocabulary is closed and total, and takes exactly: "
                f"{', '.join(keys)}"
            )
        if key in fields:
            raise ParseError(f"{label}: two {key!r} lines; each field is written once")
        if not value:
            raise ParseError(f"{label}: {key!r} carries no value")
        fields[key] = value
    missing = [key for key in keys if key not in fields]
    if missing:
        raise ParseError(f"{label}: missing required field(s): {', '.join(missing)}")
    return fields


def extract_field_blocks(text: str, *, name: str, keys: Sequence[str], label: str) -> FieldBlocks:
    """Every ``name`` block in ``text``, each read as a closed, fixed set of single-line fields.

    **The live prose transport.** A block opens ``<<<NAME`` and closes ``NAME``
    on lines of their own and carries no number: nothing here refers to a block,
    so there is no pointer to keep consistent. Each value is taken verbatim to
    the end of its line, on :class:`ProseBlocks`' terms and for its reasons.

    **A malformed block is refused by itself.** Its refusal is returned rather
    than raised, and the blocks beside it are still read — which is the whole
    difference between this class and the JSON one: a slip in one record costs
    that record, not the answer.
    """
    blocks: list[Mapping[str, str]] = []
    refusals: list[str] = []
    bodies = extract_blocks(text, open_marker=f"<<<{name}", close_marker=name, label=label)
    for position, body in enumerate(bodies, start=1):
        try:
            blocks.append(_field_block(body, keys=keys, label=f"{label}: {name} block {position} of {len(bodies)}"))
        except ParseError as refusal:
            refusals.append(str(refusal))
    return FieldBlocks(tuple(blocks), tuple(refusals))


def field_block(fields: Mapping[str, str], *, name: str) -> str:
    """One field block as a seat returns it — composed rather than typed.

    Wherever a caller needs to *state* a block — a check's fixture, a replay
    corpus — it composes one here rather than hand-typing the format: a caller
    that typed it would be making of itself the byte-fidelity demand this
    transport exists so that nobody makes of a model, and a hand-typed block
    would be a second statement of the format that drifts.
    """
    return "\n".join([f"<<<{name}", *(f"{key}: {value}" for key, value in fields.items()), name]) + "\n"


def parse_record(
    text: str,
    *,
    open_marker: str,
    close_marker: str,
    prose_name: str,
    label: str,
) -> tuple[object, ProseBlocks]:
    """The one JSON block decoded, and the prose blocks standing beside it.

    Both halves in one call, so a site cannot read the structure and forget that
    the words arrived separately — and so a site declaring **no** prose keys
    still refuses a prose block, which is what makes the empty declaration a
    check rather than an omission.
    """
    payload = parse_json_block(text, open_marker=open_marker, close_marker=close_marker, label=label)
    return payload, extract_prose_blocks(text, name=prose_name, label=label)


# --- how each object level's keys are classified ------------------------------


class Level(NamedTuple):
    """One object level of a model-facing record, and which transport each of its keys travels in.

    ``keys`` is what :func:`check_keys` refuses against. ``json``, ``prose`` and
    ``fields`` are the three independent statements of the classification — one
    per transport class this module owns — and :func:`check_levels` is what
    proves they partition ``keys`` rather than a reader remembering that they
    do. Each defaults to empty so that a level naming a transport it does not
    use says so by leaving it out; a level naming *none* of them is refused,
    because then nothing is classified.
    """

    label: str
    keys: tuple[str, ...]
    json: tuple[str, ...] = ()
    prose: tuple[str, ...] = ()
    fields: tuple[str, ...] = ()


def check_levels(levels: Iterable[Level]) -> None:
    """Each level's three transport declarations partition its vocabulary. Total, and disjoint."""
    for level in levels:
        declared = [*level.json, *level.prose, *level.fields]
        overlap = sorted({key for key in declared if declared.count(key) > 1})
        unclassified = sorted(set(level.keys) - set(declared))
        stray = sorted(set(declared) - set(level.keys))
        if overlap or unclassified or stray:
            raise ParseError(
                f"{level.label}: the key vocabulary and the transport declarations do not partition it — "
                f"{overlap} classified twice, {unclassified} classified no way, {stray} classified "
                f"but outside the vocabulary"
            )


# --- the review verdict -----------------------------------------------------

VERDICT_PREFIX = "VERDICT:"
_VERDICT_RE = re.compile(r"^VERDICT: critical=(\d+) warning=(\d+) note=(\d+)$")


@dataclass(frozen=True)
class Verdict:
    """The counts a reviewer declares. The reviewer judges; the driver counts."""

    critical: int
    warning: int
    note: int


def parse_verdict(text: str) -> Verdict:
    """Parse the final ``VERDICT:`` line. A malformed one is an error, not an absence."""
    candidates = [line.strip() for line in text.splitlines() if line.strip().startswith(VERDICT_PREFIX)]
    if not candidates:
        raise ParseError("verdict: no line beginning 'VERDICT:' in the returned text")
    match = _VERDICT_RE.match(candidates[-1])
    if match is None:
        raise ParseError(f"verdict: {candidates[-1]!r} does not match 'VERDICT: critical=<n> warning=<n> note=<n>'")
    critical, warning, note = (int(group) for group in match.groups())
    return Verdict(critical=critical, warning=warning, note=note)
