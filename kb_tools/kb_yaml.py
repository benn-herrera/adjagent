"""The KB YAML dialect: the one reader and writer of every YAML byte in a KB.

The dialect is the subset kbase writes (block mappings and lists, plain and double-quoted scalars,
flow lists of scalars, `[]` and `{}`), and the writer is byte-equal to kbase's — yaml.v3 v3.0.5
under `SetIndent(2)` with kbase's string rule — for equal values of the kinds kbase's golden pairs
hold. A `float` with an integral value is the exception: it is written as Python spells it (`1.0`),
and whether kbase writes `1` instead is unpinned until kbase supplies a golden holding one.

Value model: `dict` (insertion order is key order), `list` (block style), `FlowList` (flow style),
`str`, `int`, `float`, `bool`, `None`, and `Number` (a number kept as its source text). The reader
returns `FlowList` for a flow list and `list` for a block one, so a round trip keeps the style.

Three products: a record document (`dump`/`parse`), frontmatter lines (`dump_field`,
`frontmatter`, `find_frontmatter`), and the index stream (`index_line`/`parse_index`), one
`--- <JSON object>` line per record. No file I/O.
"""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass


class FlowList(list):
    """A list written in flow style, `[a, b]`; the reader returns one for every flow list."""


class Number(str):
    """A number written as its own text, so `1e-05` or `2.50` survives a round trip unchanged."""


class KbYamlError(ValueError):
    """Text outside the dialect, naming the 1-based line and the construct refused."""

    def __init__(self, line: int, detail: str) -> None:
        super().__init__(f"line {line}: {detail}")
        self.line = line
        self.detail = detail


@dataclass(frozen=True)
class IndexLineError:
    """An index stream line that is not `--- ` and a JSON object; reported, not raised."""

    line: int
    detail: str


@dataclass(frozen=True)
class FrontmatterSpan:
    """Offsets of a document's frontmatter, whose opening fence is always at offset 0.

    `text[body_start:body_end]` is the YAML between the fences, the break before the closing
    fence excluded; `text[close_start:close_start + 3]` is the closing fence; `end` is the first
    offset after the closing fence's line break, where the document's body (up-link first) begins.
    """

    body_start: int
    body_end: int
    close_start: int
    end: int


_FENCE = "---"
_INDEX_MARKER = "--- "

# A string written plain: one no YAML 1.1 or 1.2 reader takes for anything but itself.
_PLAIN_SAFE_RE = re.compile(r"[A-Za-z][A-Za-z0-9_./-]*")
_YAML11_WORDS = frozenset({"y", "n", "yes", "no", "on", "off", "true", "false", "null"})

_INT_RE = re.compile(r"[-+]?[0-9]+")
_FLOAT_RE = re.compile(r"[-+]?(\.[0-9]+|[0-9]+(\.[0-9]*)?)([eE][-+]?[0-9]+)?")
_NULL_WORDS = frozenset({"null", "Null", "NULL", "~"})
_BOOL_WORDS = {"true": True, "True": True, "TRUE": True, "false": False, "False": False, "FALSE": False}
_KEY_LINE_RE = re.compile(r"[a-z][a-z0-9-]*:")

# yaml.v3 takes each of these as a line break.
_BREAKS = frozenset("\r\n\x85\u2028\u2029")
_BLANKS = " \t"
_SIMPLE_KEY_MAX_BYTES = 128

_ESCAPE_LETTERS = {
    0x00: "0",
    0x07: "a",
    0x08: "b",
    0x09: "t",
    0x0A: "n",
    0x0B: "v",
    0x0C: "f",
    0x0D: "r",
    0x1B: "e",
    0x22: '"',
    0x5C: "\\",
    0x85: "N",
    0xA0: "_",
    0x2028: "L",
    0x2029: "P",
}
_UNESCAPES = {letter: chr(code) for code, letter in _ESCAPE_LETTERS.items()} | {"/": "/", " ": " ", "\t": "\t"}
_HEX_ESCAPE_WIDTHS = {"x": 2, "u": 4, "U": 8}

# Characters an index line carries escaped though JSON leaves them raw: a stream reader takes
# them as line breaks or refuses them as unprintable.
_INDEX_UNSAFE = {code: f"\\u{code:04x}" for code in [*range(0x7F, 0xA0), 0x2028, 0x2029, 0xFEFF, 0xFFFE, 0xFFFF]}


# ---------------------------------------------------------------------------------------------
# Writer


def dump(value: Mapping) -> str:
    """A record document: the mapping's block lines, no `---`, ending in one `\\n`."""
    if not isinstance(value, Mapping):
        raise TypeError(f"a record document is a mapping, not {type(value).__name__}")
    if not value:
        return "{}\n"
    return "\n".join(_block_lines(value, 0)) + "\n"


def dump_field(key: str, value: object) -> list[str]:
    """One top-level frontmatter key and its value as lines, no line breaks."""
    return _block_lines({key: value}, 0)


def frontmatter(lines: list[str]) -> str:
    """Field lines between the fences; the closing fence's line break is the document's."""
    return "\n".join([_FENCE, *lines, _FENCE])


def index_line(record: Mapping) -> str:
    """One index stream line: `--- `, the record as a JSON object, `\\n`."""
    if not isinstance(record, Mapping):
        raise TypeError(f"an index record is a mapping, not {type(record).__name__}")
    text = json.dumps(record, ensure_ascii=False, separators=(", ", ": "), allow_nan=False)
    return _INDEX_MARKER + text.translate(_INDEX_UNSAFE) + "\n"


def _block_lines(value: object, column: int) -> list[str]:
    """A non-empty mapping or block list starting at `column`.

    The first line carries no indentation, because the caller places it (after `- `, `: `, or its
    own indentation); every later line is indented absolutely.
    """
    pad = " " * column
    lines: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"a mapping key is a string, not {type(key).__name__}")
            key_text = _string(key)
            if len(key.encode("utf-8")) > _SIMPLE_KEY_MAX_BYTES or any(ch in _BREAKS for ch in key):
                lines.append(f"{pad}? {key_text}")
                lines.extend(_placed(f"{pad}: ", item, column + 2))
                continue
            inline = _inline(item)
            if inline is not None:
                lines.append(f"{pad}{key_text}: {inline}")
            else:
                lines.append(f"{pad}{key_text}:")
                lines.extend(_placed(" " * (column + 2), item, column + 2))
    else:
        for item in value:
            lines.extend(_placed(f"{pad}- ", item, column + 2))
    lines[0] = lines[0][column:]
    return lines


def _placed(prefix: str, value: object, column: int) -> list[str]:
    """`value` written after `prefix`, a nested block's first line on the prefix's line."""
    inline = _inline(value)
    if inline is not None:
        return [prefix + inline]
    nested = _block_lines(value, column)
    return [prefix + nested[0], *nested[1:]]


def _inline(value: object) -> str | None:
    """`value` as one line's text, or None for a non-empty mapping or block list."""
    if isinstance(value, FlowList):
        return "[" + ", ".join(_scalar(item) for item in value) + "]"
    if isinstance(value, (list, tuple)):
        return None if value else "[]"
    if isinstance(value, Mapping):
        return None if value else "{}"
    return _scalar(value)


def _scalar(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Number):
        if not _FLOAT_RE.fullmatch(value):
            raise ValueError(f"Number {str(value)!r} is not a number's text")
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise ValueError(f"{value!r} has no form in the dialect")
        return repr(value)
    if isinstance(value, str):
        return _string(value)
    raise TypeError(f"no dialect form for {type(value).__name__}")


def _string(text: str) -> str:
    if _PLAIN_SAFE_RE.fullmatch(text) and text.lower() not in _YAML11_WORDS:
        return text
    escape_all = text.startswith("\ufeff")
    out = ['"']
    for ch in text:
        if escape_all or not _printable(ch) or ch in _BREAKS or ch in '"\\':
            out.append(_escape(ord(ch)))
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _printable(ch: str) -> bool:
    """yaml.v3's printable set: a 4-byte UTF-8 character is not printable."""
    code = ord(ch)
    return (
        code == 0x0A or 0x20 <= code <= 0x7E or 0xA0 <= code <= 0xD7FF or (0xE000 <= code <= 0xFFFD and code != 0xFEFF)
    )


def _escape(code: int) -> str:
    if code in _ESCAPE_LETTERS:
        return "\\" + _ESCAPE_LETTERS[code]
    if code <= 0xFF:
        return f"\\x{code:02X}"
    if code <= 0xFFFF:
        return f"\\u{code:04X}"
    return f"\\U{code:08X}"


# ---------------------------------------------------------------------------------------------
# Frontmatter locator


def find_frontmatter(text: str) -> FrontmatterSpan | None:
    """A document's frontmatter: a `---` line opening the text through the next `---` line.

    Either fence line ends in `\\n` or `\\r\\n` (the closing one may end the text). None where the
    text opens with no fence line, never closes it, or fences a block whose first non-blank line
    opens no kebab-case key — a Markdown thematic break opening prose. A blank body counts.
    """
    body_start = _fence_line_end(text, 0)
    if body_start is None or (body_start == len(text) and not text.endswith("\n")):
        return None
    at = body_start
    while at < len(text):
        end = _fence_line_end(text, at)
        if end is not None:
            body_end = body_start
            if at > body_start:
                body_end = at - 1
                if body_end > body_start and text[body_end - 1] == "\r":
                    body_end -= 1
            if not _opens_with_key(text[body_start:body_end]):
                return None
            return FrontmatterSpan(body_start=body_start, body_end=body_end, close_start=at, end=end)
        newline = text.find("\n", at)
        if newline < 0:
            break
        at = newline + 1
    return None


def _fence_line_end(text: str, at: int) -> int | None:
    """Where the line after a fence line at `at` begins, or None where none is there."""
    if not text.startswith(_FENCE, at):
        return None
    after = at + len(_FENCE)
    if after == len(text):
        return after
    for terminator in ("\n", "\r\n"):
        if text.startswith(terminator, after):
            return after + len(terminator)
    return None


def _opens_with_key(body: str) -> bool:
    for line in body.split("\n"):
        if line.strip():
            return _KEY_LINE_RE.match(line) is not None
    return True


# ---------------------------------------------------------------------------------------------
# Index reader


def parse_index(text: str) -> tuple[list[dict], list[IndexLineError]]:
    """An index stream's records in order, and a problem for each line that is not one.

    A blank line is skipped; a bad line is reported beside the records rather than raised, so a
    verifier can name it and a query can drop it.
    """
    records: list[dict] = []
    problems: list[IndexLineError] = []
    for number, line in enumerate(text.split("\n"), start=1):
        if not line.strip():
            continue
        if not line.startswith(_INDEX_MARKER):
            problems.append(IndexLineError(number, "expected the document marker and a JSON object"))
            continue
        body = line[len(_INDEX_MARKER) :].strip()
        try:
            record = json.loads(body, parse_constant=refuse_json_constant)
        except ValueError as error:
            problems.append(IndexLineError(number, f"not a JSON object: {error}"))
            continue
        if not isinstance(record, dict):
            problems.append(IndexLineError(number, "expected the document marker and a JSON object"))
            continue
        records.append(record)
    return records, problems


def refuse_json_constant(name: str) -> object:
    """``json.loads``'s ``parse_constant``: ``NaN``, ``Infinity`` and ``-Infinity`` are not JSON, so a ValueError."""
    raise ValueError(f"{name} is not JSON")


# ---------------------------------------------------------------------------------------------
# Reader


def parse(text: str) -> object:
    """A record document or a frontmatter body read to values; an empty one is `{}`.

    Raises KbYamlError naming the line for anything outside the dialect.
    """
    lines = _Lines(text)
    if lines.at_end():
        return {}
    first = lines.peek()
    value = _parse_block(lines, first.indent)
    if not lines.at_end():
        extra = lines.peek()
        raise KbYamlError(extra.number, "unexpected indentation")
    return value


@dataclass
class _Line:
    number: int
    indent: int
    content: str


class _Lines:
    """The text's significant lines: blank lines and whole-line comments skipped."""

    def __init__(self, text: str) -> None:
        self._lines: list[_Line] = []
        seen_content = False
        for number, raw in enumerate(text.split("\n"), start=1):
            line = raw[:-1] if raw.endswith("\r") else raw
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            for ch in line:
                if ch in _BREAKS:
                    raise KbYamlError(number, f"a line break (U+{ord(ch):04X}) inside a line")
            indent = len(line) - len(line.lstrip(" "))
            if line[indent : indent + 1] == "\t":
                raise KbYamlError(number, "a tab in indentation")
            if _is_document_marker(line):
                if line == _FENCE and not seen_content:
                    seen_content = True
                    continue
                raise KbYamlError(number, "a document marker inside a document")
            seen_content = True
            self._lines.append(_Line(number, indent, line[indent:].rstrip(_BLANKS)))
        self._at = 0

    def at_end(self) -> bool:
        return self._at >= len(self._lines)

    def peek(self) -> _Line:
        return self._lines[self._at]

    def take(self) -> _Line:
        line = self._lines[self._at]
        self._at += 1
        return line

    def reopen(self, line: _Line) -> None:
        """Push back the remainder of a line, opened at its own column (`- k: v`, `: k: v`)."""
        self._at -= 1
        self._lines[self._at] = line


def _is_document_marker(line: str) -> bool:
    return any(_opens_with(line, mark) for mark in ("---", "..."))


def _is_list_item(content: str) -> bool:
    return _opens_with(content, "-")


def _is_complex_key(content: str) -> bool:
    return _opens_with(content, "?")


def _parse_block(lines: _Lines, indent: int) -> object:
    content = lines.peek().content
    if _is_list_item(content):
        return _parse_list(lines, indent)
    return _parse_mapping(lines, indent)


def _parse_mapping(lines: _Lines, indent: int) -> dict:
    result: dict = {}
    while not lines.at_end() and lines.peek().indent == indent:
        line = lines.take()
        if _is_complex_key(line.content):
            key = _parse_key_scalar(line.content[1:].lstrip(_BLANKS), line.number)
            if lines.at_end() or lines.peek().indent != indent or not _opens_with(lines.peek().content, ":"):
                raise KbYamlError(line.number, "a `? key` not followed by `: value` at its indent")
            value_line = lines.take()
            value = _parse_opened(lines, value_line, indent)
        else:
            key, rest = _split_key(line)
            value = _parse_value(lines, line, rest, indent)
        if key in result:
            raise KbYamlError(line.number, f"duplicate key {key!r}")
        result[key] = value
    if not lines.at_end() and lines.peek().indent > indent:
        raise KbYamlError(lines.peek().number, "unexpected indentation")
    return result


def _parse_list(lines: _Lines, indent: int) -> list:
    result: list = []
    while not lines.at_end() and lines.peek().indent == indent and _is_list_item(lines.peek().content):
        result.append(_parse_opened(lines, lines.take(), indent))
    if not lines.at_end() and lines.peek().indent > indent:
        raise KbYamlError(lines.peek().number, "unexpected indentation")
    return result


def _opens_with(content: str, indicator: str) -> bool:
    """`content` is `indicator` alone, or `indicator` and then a blank."""
    return content == indicator or (content.startswith(indicator) and content[len(indicator)] in _BLANKS)


def _parse_opened(lines: _Lines, line: _Line, indent: int) -> object:
    """The node after a one-character indicator (`-` or `:`) and its blanks on `line`."""
    rest = line.content[1:].lstrip(_BLANKS)
    if not rest:
        return _parse_nested(lines, line, indent)
    column = line.indent + len(line.content) - len(rest)
    if _is_list_item(rest) or _is_complex_key(rest) or _opens_mapping(rest, line.number):
        lines.reopen(_Line(line.number, column, rest))
        return _parse_block(lines, column)
    value = _parse_inline(rest, line.number)
    _refuse_continuation(lines, indent)
    return value


def _parse_value(lines: _Lines, line: _Line, rest: str, indent: int) -> object:
    """A mapping value: inline after the key, or a block on the following lines."""
    if not rest:
        if not lines.at_end() and lines.peek().indent == indent and _is_list_item(lines.peek().content):
            return _parse_list(lines, indent)
        return _parse_nested(lines, line, indent)
    value = _parse_inline(rest, line.number)
    _refuse_continuation(lines, indent)
    return value


def _parse_nested(lines: _Lines, line: _Line, indent: int) -> object:
    if lines.at_end() or lines.peek().indent <= indent:
        return None
    return _parse_block(lines, lines.peek().indent)


def _refuse_continuation(lines: _Lines, indent: int) -> None:
    if not lines.at_end() and lines.peek().indent > indent:
        raise KbYamlError(lines.peek().number, "a scalar continued onto a second line")


def _opens_mapping(content: str, number: int) -> bool:
    """Whether `content`, on line `number`, is a `key: …` line rather than a scalar."""
    if content.startswith('"'):
        _, end = _read_double_quoted(content, number)
        return content[end : end + 1] == ":" and _separates(content, end)
    return _plain_key_end(content) is not None


def _split_key(line: _Line) -> tuple[str, str]:
    content = line.content
    if content.startswith('"'):
        key, end = _read_double_quoted(content, line.number)
        if content[end : end + 1] != ":" or not _separates(content, end):
            raise KbYamlError(line.number, "expected `key: value`")
        return key, content[end + 1 :].lstrip(_BLANKS)
    end = _plain_key_end(content)
    if end is None:
        raise KbYamlError(line.number, "expected `key: value`")
    key = content[:end].rstrip(_BLANKS)
    _check_plain(key, line.number)
    return key, content[end + 1 :].lstrip(_BLANKS)


def _plain_key_end(content: str) -> int | None:
    for at, ch in enumerate(content):
        if ch == ":" and _separates(content, at):
            return at
    return None


def _separates(content: str, at: int) -> bool:
    """Whether the `:` at `at` is a value indicator: followed by a blank or the line's end."""
    return at + 1 == len(content) or content[at + 1] in _BLANKS


def _parse_key_scalar(text: str, number: int) -> str:
    if text.startswith('"'):
        key, end = _read_double_quoted(text, number)
        if text[end:]:
            raise KbYamlError(number, "text after a quoted scalar")
        return key
    _check_plain(text, number)
    return text


def _parse_inline(text: str, number: int) -> object:
    """A value written on its key's or item's line: a scalar, a flow list, or `{}`."""
    if text.startswith("["):
        return _parse_flow_list(text, number)
    if text.startswith("{"):
        if text[1:].rstrip(_BLANKS) != "}":
            raise KbYamlError(number, "a non-empty flow mapping")
        return {}
    if text.startswith('"'):
        value, end = _read_double_quoted(text, number)
        if text[end:]:
            raise KbYamlError(number, "text after a quoted scalar")
        return value
    _check_plain(text, number)
    return _typed(text, number)


def _parse_flow_list(text: str, number: int) -> FlowList:
    if not text.endswith("]"):
        raise KbYamlError(number, "a flow list not closed on its line")
    inner = text[1:-1].strip(_BLANKS)
    items = FlowList()
    if not inner:
        return items
    at = 0
    while True:
        while at < len(inner) and inner[at] in _BLANKS:
            at += 1
        if at < len(inner) and inner[at] in "[{":
            raise KbYamlError(number, "a flow list holding a non-scalar")
        if at < len(inner) and inner[at] == '"':
            value, at = _read_double_quoted(inner, number, start=at)
            while at < len(inner) and inner[at] in _BLANKS:
                at += 1
            if at < len(inner) and inner[at] != ",":
                raise KbYamlError(number, "text after a quoted scalar")
            items.append(value)
        else:
            comma = inner.find(",", at)
            end = len(inner) if comma < 0 else comma
            item = inner[at:end].rstrip(_BLANKS)
            if not item:
                raise KbYamlError(number, "an empty flow list item")
            if any(ch in item for ch in "[]{}"):
                raise KbYamlError(number, "a flow list holding a non-scalar")
            _check_plain(item, number)
            items.append(_typed(item, number))
            at = end
        if at >= len(inner):
            return items
        at += 1


def _check_plain(text: str, number: int) -> None:
    """Refuse a plain scalar outside the dialect, naming the construct it would be."""
    first = text[:1]
    refused_openers = {
        "&": "an anchor (&)",
        "*": "an alias (*)",
        "!": "a tag (!)",
        "|": "a block scalar (|)",
        ">": "a block scalar (>)",
        "'": "a single-quoted scalar",
    }
    if first in refused_openers:
        raise KbYamlError(number, refused_openers[first])
    if not text:
        raise KbYamlError(number, "an empty plain scalar")
    if first in ',[]{}#"%@`' or (first in "-?:" and (len(text) == 1 or text[1] in _BLANKS)):
        raise KbYamlError(number, f"a plain scalar opening with {first!r}")
    for at, ch in enumerate(text):
        if ch == ":" and _separates(text, at):
            raise KbYamlError(number, "a plain scalar holding ': '")
        if ch == "#" and text[at - 1] in _BLANKS:
            raise KbYamlError(number, "a plain scalar holding ' #'")


def _typed(text: str, number: int) -> object:
    if text in _NULL_WORDS:
        return None
    if text in _BOOL_WORDS:
        return _BOOL_WORDS[text]
    unsigned = text[1:] if text[:1] in "+-" else text
    if re.fullmatch(r"\.(inf|nan)", unsigned, re.IGNORECASE):
        raise KbYamlError(number, f"a non-finite number {text!r}")
    if re.fullmatch(r"0[0-9]+|0[xXoObB].*", unsigned):
        raise KbYamlError(number, f"a hex, octal or binary number {text!r}")
    if "_" in unsigned and _FLOAT_RE.fullmatch(text.replace("_", "")):
        raise KbYamlError(number, f"a number with underscores {text!r}")
    if _INT_RE.fullmatch(text):
        return int(text)
    if _FLOAT_RE.fullmatch(text):
        return float(text)
    return text


def _read_double_quoted(text: str, number: int, start: int = 0) -> tuple[str, int]:
    """The double-quoted scalar opening at `start`, and the offset just past its closing quote."""
    out: list[str] = []
    at = start + 1
    while at < len(text):
        ch = text[at]
        if ch == '"':
            return "".join(out), at + 1
        if ch != "\\":
            out.append(ch)
            at += 1
            continue
        if at + 1 >= len(text):
            raise KbYamlError(number, "a scalar continued onto a second line")
        letter = text[at + 1]
        if letter in _UNESCAPES:
            out.append(_UNESCAPES[letter])
            at += 2
            continue
        width = _HEX_ESCAPE_WIDTHS.get(letter)
        digits = text[at + 2 : at + 2 + width] if width else ""
        if not width or len(digits) != width or not all(d in "0123456789abcdefABCDEF" for d in digits):
            raise KbYamlError(number, f"an unknown escape \\{letter}")
        code = int(digits, 16)
        if code > 0x10FFFF or 0xD800 <= code <= 0xDFFF:
            raise KbYamlError(number, f"an escape naming no character \\{letter}{digits}")
        out.append(chr(code))
        at += 2 + width
    raise KbYamlError(number, "a scalar continued onto a second line")
