"""
Marker syntax, and the one expander that substitutes it.

A MARKER'S NAMESPACE NAMES THE SOURCE ITS VALUE COMES FROM, and a marker
without one is a chunk. Five spellings, no precedence between them: the
expander routes on the prefix alone, so a chunk and an argument sharing a name
are two different markers rather than a collision some rule has to arbitrate.

    @!name ...!@          a chunk call — the grammar of its arguments is the
                          chunk source's (`chunks` module docstring)
    @!arg.key!@           the value the enclosing chunk call bound for `key`
    @!dyn.tier-high!@ …   an invocation parameter (Tier tokens, `model_tuning`
                          module docstring)
    @!fam.gap-aversion!@  model-tuning overlay anchor (Model tuning,
                          `model_tuning` module docstring)
    @!hrn.agents-file!@   a value from the loaded harness file (`agents_file`
                          module docstring)

THE PREFIX GOES WHERE A VALUE IS CONSUMED, NEVER WHERE IT IS BOUND. A chunk
marker's `key="value"` argument, a [chunks.<name>.defaults] key, and an
[outputs.<name>] fence key all stay bare: position already says what they are.
It is the marker READING one, inside a body, that carries `arg.`, because
nothing there would otherwise say where the value comes from.

ROUTING. A caller expands text with `expand(text, routes, args=...)`. `routes`
maps a routing key to a source: CHUNK_ROUTE for a bare marker, and a registered
namespace for a prefixed one. `arg` is never in the table — the expander binds
it, lexically (below). A prefix not in NAMESPACES names no source and is an
error; a registered one the render does not route is an error naming what is
routed. `chk` is only a routing key, never a prefix: `@!chk.x!@` names no
source. Adding a source is the source itself, its prefix in NAMESPACES, and an
entry in the routing table of each render that offers it — `expand` does not
change.

SOURCES ARE PURE LOOKUPS. A source takes a name (a chunk source also takes the
call's arguments) and returns a value or raises. It never scans text and never
expands, so it holds no reference to the expander. Missing-key behaviour is the
source's own: TableSource and ArgSource raise; the family source returns "".

THREE VALUE KINDS. A source returns one of:

    str           authored text — spliced in and rescanned in the enclosing
                  span, so a marker inside it expands
    Verbatim      operator text — spliced in as a final segment, never
                  rescanned, never residual-checked, and a hard boundary no
                  scan reads across
    Span          a chunk call — expanded as its own nested span with `arg`
                  bound to Span.args and every other route inherited; when it
                  has nothing left to substitute, Span.finish (if any) is
                  applied and the result spliced in. A finish over verbatim
                  text is refused: it would merge final text back into
                  authored text

`arg` IS LEXICAL. Inside a chunk body, @!arg.x!@ is that chunk call's `x`; an
authored value spliced into a span reads that span's arguments. The top-level
span binds the `args` the caller passes. A call's argument values are authored
text of the span the call sits in, so they expand there before they are bound,
which is how a body forwards its own argument: @!inner key="@!arg.key!@"!@.

DEPTH COUNTS NESTING. A span entered at depth d runs pass k at depth d+k, and a
Span found in a pass at depth p is entered at p+1. Finding a marker at a depth
above MAX_EXPANSION_DEPTH is the cycle error.

A marker name, a namespace, a family anchor key, and an argument key are one
identifier class — IDENTIFIER below — built once and shared by every regex site
so they cannot spell it differently and drift apart. The `.` joining a
namespace to a name is deliberately outside that class: it is the whole of what
keeps a namespace from ever being read as a name. A malformed name fails
loudly: `@!write-op-!@` raises "unknown chunk 'write-op-'", naming the exact
string. A malformed argument key, or a malformed namespaced marker
(`@!fam.Gap!@`, `@!fam.a.b!@`), does not parse as a marker at all and ships as
literal text, which the residual-marker guard below refuses at generation
rather than letting it work by accident.
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from .errors import InputError
from .paths import rel

MAX_EXPANSION_DEPTH = 10
# The namespace vocabulary: a marker's prefix names the SOURCE its value comes
# from. CHUNK_ROUTE is the routing key a bare marker takes and is deliberately
# not a namespace, so no second spelling of a chunk marker exists.
ARG_NAMESPACE = "arg"
DYNAMIC_NAMESPACE = "dyn"
FAMILY_NAMESPACE = "fam"
HARNESS_NAMESPACE = "hrn"
NAMESPACES = (ARG_NAMESPACE, DYNAMIC_NAMESPACE, FAMILY_NAMESPACE, HARNESS_NAMESPACE)
CHUNK_ROUTE = "chk"
# The one identifier class shared by marker names, namespace prefixes, family
# anchor keys, and chunk-argument keys: strict kebab-case — a letter-led
# segment, optionally followed by more letter/digit segments joined by single
# hyphens. No leading digit or hyphen, no trailing or doubled hyphen, no
# underscore. Tight rather than merely typo-proof because these templates are
# increasingly authored by models: a trailing or doubled hyphen is exactly what
# a generator emits without noticing.
IDENTIFIER = r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*"

# One marker, whole: an optional namespace prefix, the name, and the quoted
# arguments a bare (chunk) marker may carry. The prefix is matched as an
# IDENTIFIER rather than as an alternation of the registered names so that an
# unregistered one reaches the router and is refused by name, instead of
# failing to parse as a marker at all.
MARKER = re.compile(rf'@!(?:({IDENTIFIER})\.)?({IDENTIFIER})((?:\s+{IDENTIFIER}="[^"]*")*)\s*!@')
ARG = re.compile(rf'({IDENTIFIER})="([^"]*)"')


@dataclass(frozen=True)
class Verbatim:
    """Operator-supplied text: final, never rescanned or residual-checked."""

    text: str


@dataclass(frozen=True)
class Span:
    """A chunk call: `body` expanded as its own span with `arg` bound to
    `args`, then `finish` applied to the result."""

    body: str
    args: Mapping[str, str]
    finish: Callable[[str], str] | None = None


Value = str | Verbatim | Span
# Routing key -> source. A namespaced source is called with the marker's name;
# the CHUNK_ROUTE source with the name and the call's arguments.
Routes = Mapping[str, Callable[..., Value]]
# Invocation-parameter name -> its value: what a TableSource resolves from.
DynamicMap = dict[str, str | Verbatim]


@dataclass(frozen=True)
class TableSource:
    """A strict lookup: a name the table does not hold is an error naming
    what it does hold. `noun` is what one key is called in that error."""

    table: Mapping[str, str | Verbatim]
    namespace: str
    noun: str

    def __call__(self, name: str) -> str | Verbatim:
        if name not in self.table:
            known = ", ".join(sorted(self.table)) or "(none)"
            raise InputError(f"unknown {self.noun} '{name}' — @!{self.namespace}.…!@ names {known}")
        return self.table[name]


@dataclass(frozen=True)
class ArgSource:
    """The arguments one span's call site bound."""

    args: Mapping[str, str]

    def __call__(self, name: str) -> str:
        if name not in self.args:
            raise InputError(
                f"no argument '{name}' is bound here — @!{ARG_NAMESPACE}.{name}!@ reads a value the "
                f"call site passes or [chunks.<name>.defaults] supplies"
            )
        return self.args[name]


@dataclass(frozen=True)
class VerbatimSpan:
    """Where one Verbatim value landed in the expanded text, and the marker
    that produced it. Recorded even when empty."""

    offset: int
    text: str
    marker: str

    @property
    def end(self) -> int:
        return self.offset + len(self.text)


@dataclass(frozen=True)
class Expansion:
    """Expanded text, and every verbatim span in it, in order."""

    text: str
    verbatim: tuple[VerbatimSpan, ...]


@dataclass(frozen=True)
class _Final:
    """A verbatim segment inside an expansion in progress."""

    text: str
    marker: str


_Segment = str | _Final


def assert_namespace(namespace: str, name: str, *, where: str) -> None:
    """Refuse a marker whose namespace names no source. `where` labels the
    text the marker was read from."""
    if namespace not in NAMESPACES:
        raise InputError(
            f"{where}: @!{namespace}.{name}!@ names no source — namespaces are "
            f"{', '.join(NAMESPACES)}, and a marker with none is a chunk"
        )


def anchors_in(text: str, *, namespace: str, where: str) -> set[str]:
    """Every marker of `namespace` that `text` declares, by full spelling
    (`fam.<key>`), with every namespaced marker's namespace validated as it is
    read, collected or not.

    The sweep is what catches a typo'd namespace in a chunk body a render never
    expands: the expander only sees what it reaches.
    """
    found = set()
    for match in MARKER.finditer(text):
        prefix, name = match.group(1), match.group(2)
        if prefix is None:
            continue
        assert_namespace(prefix, name, where=where)
        if prefix == namespace:
            found.add(f"{prefix}.{name}")
    return found


def collect_anchors(chunks: dict[str, dict], template_paths: list[Path], *, namespace: str) -> set[str]:
    """Every marker of `namespace` authored anywhere — template bodies and
    chunk bodies (text, variants, and defaults values) alike."""
    found: set[str] = set()
    for path in template_paths:
        found |= anchors_in(path.read_text(encoding="utf-8"), namespace=namespace, where=rel(path))
    for name, chunk in chunks.items():
        for value in (
            chunk.get("text", ""),
            *chunk.get("variants", {}).values(),
            *chunk.get("defaults", {}).values(),
        ):
            found |= anchors_in(value, namespace=namespace, where=f"chunk '{name}'")
    return found


def expand(text: str, routes: Routes, *, args: Mapping[str, str]) -> Expansion:
    """Expand every marker in `text`, each from the source its routing key
    names, with the top-level span's `arg` bound to `args`."""
    out: list[str] = []
    spans = []
    offset = 0
    for segment in _expand_span(text, routes, ArgSource(args), depth=0):
        if isinstance(segment, _Final):
            spans.append(VerbatimSpan(offset, segment.text, segment.marker))
            segment = segment.text
        out.append(segment)
        offset += len(segment)
    return Expansion("".join(out), tuple(spans))


def _expand_span(text: str, routes: Routes, arg: ArgSource, *, depth: int) -> list[_Segment]:
    """One span to a fixed point: each pass substitutes every marker found in
    its authored segments, and the span is done when a pass finds none."""
    segments: list[_Segment] = [text]
    while True:
        out: list[_Segment] = []
        found = False
        for segment in segments:
            if isinstance(segment, _Final):
                out.append(segment)
                continue
            position = 0
            for match in MARKER.finditer(segment):
                if depth > MAX_EXPANSION_DEPTH:
                    raise InputError("marker expansion exceeded maximum depth (cycle?)")
                found = True
                out.append(segment[position : match.start()])
                out.extend(_substitute(match, routes, arg, depth=depth))
                position = match.end()
            out.append(segment[position:])
        segments = _merged(out)
        if not found:
            return segments
        depth += 1


def _substitute(match: re.Match[str], routes: Routes, arg: ArgSource, *, depth: int) -> list[_Segment]:
    namespace, name, arg_text = match.groups()
    call_args = dict(ARG.findall(arg_text))
    if namespace is None:
        bound = {
            key: _expand_argument(text, routes, arg, depth=depth, marker=match.group(0))
            for key, text in call_args.items()
        }
        value = routes[CHUNK_ROUTE](name, bound)
    else:
        marker = f"@!{namespace}.{name}!@"
        assert_namespace(namespace, name, where=marker)
        if call_args:
            raise InputError(f"{marker} takes no arguments — only a chunk marker does")
        source = arg if namespace == ARG_NAMESPACE else routes.get(namespace)
        if source is None:
            routed = ", ".join([ARG_NAMESPACE, *sorted(key for key in routes if key in NAMESPACES)])
            raise InputError(
                f"{marker}: '{namespace}' is a registered namespace this render does not route — routed here: {routed}"
            )
        value = source(name)
    if isinstance(value, Verbatim):
        return [_Final(value.text, match.group(0))]
    if isinstance(value, Span):
        inner = _expand_span(value.body, routes, ArgSource(value.args), depth=depth + 1)
        if value.finish is None:
            return inner
        if any(isinstance(segment, _Final) for segment in inner):
            raise InputError(f"{match.group(0)}: wrap= cannot apply to text holding a verbatim value")
        return [value.finish("".join(inner))]
    return [value]


def _expand_argument(text: str, routes: Routes, arg: ArgSource, *, depth: int, marker: str) -> str:
    """One argument value expanded in the span its call sits in. Bound, it
    becomes authored text of the callee, which verbatim text must never do."""
    segments = _expand_span(text, routes, arg, depth=depth + 1)
    if any(isinstance(segment, _Final) for segment in segments):
        raise InputError(f"{marker}: an argument value cannot hold a verbatim value")
    return "".join(segments)


def _merged(segments: list[_Segment]) -> list[_Segment]:
    """Adjacent authored segments joined — so a rescan reads them as one — and
    empty authored ones dropped. Verbatim segments stay, empty or not."""
    merged: list[_Segment] = []
    for segment in segments:
        if isinstance(segment, _Final):
            merged.append(segment)
        elif segment:
            if merged and isinstance(merged[-1], str):
                merged[-1] += segment
            else:
                merged.append(segment)
    return merged


# Lookahead, so overlapping delimiters (`@!@`) are each found.
RESIDUAL_MARKER = re.compile(r"(?=@!|!@)")


def assert_no_residual_markers(expansion: Expansion, *, path: Path, name: str) -> None:
    """Refuse a rendered output that still carries a literal marker delimiter
    — '@!' or '!@' — with both characters outside every verbatim span.

    The expander only ever consumes a span matching MARKER. A marker mistyped
    past that syntax (wrong case, an underscore, a stray character) is
    ordinary text that happens to spell "@!...!@", passes through untouched,
    and would ship into what becomes an agent's system prompt with no error to
    say so. A name inside valid syntax but unknown to its source is already
    caught by the source; what reaches here is a marker no regex recognized as
    an attempt in the first place. Naming the line spares a maintainer a grep.
    """
    covered = [(span.offset, span.end) for span in expansion.verbatim]
    offset = 0
    for lineno, line in enumerate(expansion.text.splitlines(keepends=True), start=1):
        for match in RESIDUAL_MARKER.finditer(line):
            first = offset + match.start()
            if any(start <= index < end for index in (first, first + 1) for start, end in covered):
                continue
            raise InputError(
                f"{rel(path)}: output '{name}' renders a literal marker delimiter at line {lineno}: {line.strip()!r} "
                f"— a marker mistyped past MARKER's syntax, or literal text that needs escaping; "
                f"rendered output must hold no marker syntax at all"
            )
        offset += len(line)
