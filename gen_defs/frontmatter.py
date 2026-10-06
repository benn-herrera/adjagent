"""
Per-harness agent frontmatter: how a harness file says each output field is
rendered for that harness.

A template's frontmatter is the one authored source, written in Claude Code's
field names. Each harness file (`harness` module docstring) declares, under two
structural tables, what every output field becomes:

    [harness.agent-frontmatter]
    description = "@!dyn.authored-value!@"            # sugar for { text = "..." }
    mode        = { text = "subagent", injected = true }
    name        = false                               # elided

    [harness.tools]
    read = "Read"                                     # or a non-empty list
    glob = ["glob", "list"]

An entry's key is the OUTPUT field name. Its value is a string, a table holding
a string `text` and optionally a bool `injected` (default false), or `false`,
the only spelling of elision. A table without `text` — `{}` included — an
unknown key in an entry table, a non-string `text` and a non-bool `injected`
are each refused at load.

[harness.tools] is the harness's tool vocabulary: each key is one of our own
harness-neutral tool names (strict kebab, IDENTIFIER), each value that
harness's spelling of it, a string or a non-empty list of strings. A harness
may name tools no template uses.

An entry's `text` is expanded by the render exactly as a chunk's is, with five
more invocation parameters bound while it is — and only then, so a template or
chunk body spelling one is an unknown invocation parameter:

    @!dyn.authored-value!@          the template's raw value for the same
                                    field, as authored text, so it expands
                                    further; empty when the field is not
                                    authored
    @!dyn.output-stem!@             the output's name, verbatim
    @!dyn.tools!@                   the authored `tools` list mapped through
                                    [harness.tools], authored order, any list
                                    flattened, joined with ", "
    @!dyn.tools-as-permission!@     one `<key>: allow|deny` line per governed
                                    key — the image of [harness.tools], in
                                    order of first appearance — `allow` where
                                    an authored name maps to it
    @!dyn.undispatchable-marker!@   `true` where the template authors none of
                                    the dispatch keys (name, description,
                                    model); empty otherwise

The two tools slots share one parse of the expanded authored `tools` value:
split on `,`, each item stripped; an empty item, a flow list (`[...`) and a
name [harness.tools] does not hold are refused. Both are empty when `tools` is
not authored. They are computed on first read, so the vocabulary binds a
harness through the entries that read it.

Semantics. An entry without `injected` applies only where the template authors
its field; an injected entry is emitted whatever the template authors, and one
for a field the template also authors is refused. Every authored field needs an
entry — `false` included — or the render is refused naming the template, the
output, the field and the harness file. An entry whose expanded text is empty
is elided. Authored fields come first, in authored order, then injected
entries in the table's order. Single-line text renders `<field>: <text>`; text
holding a newline renders `<field>:` with each of its lines indented two
spaces below it, so a slot yielding a mapping yields it unindented.

The authored frontmatter grammar is closed: `key: value` lines with exactly one
space after the colon, `#` comment lines and blank lines — the last two
re-emitted unchanged, in place — between an opening `---` line and a closing
one. A continuation, a `- item`, a value opening with YAML structure (a block
scalar, a flow collection, an anchor, alias, tag, directive or comment, a
reserved indicator; STRUCTURED_VALUE_OPENERS) rather than a marker, a duplicate
key and an opening `---` that never closes are refused on every harness:
nothing here parses YAML.
"""

import re
from collections.abc import Callable, Iterator, Mapping
from typing import NamedTuple

from .errors import InputError
from .markers import IDENTIFIER, MARKER, Expansion, Verbatim, VerbatimSpan

# Two of the [harness.<key>] tables that are structure rather than `hrn.`
# values; the `harness` module lists all of them.
FRONTMATTER_TABLE_KEY = "agent-frontmatter"
TOOLS_TABLE_KEY = "tools"
# A frontmatter field name, as an entry keys it.
FIELD_NAME = r"[A-Za-z][A-Za-z0-9_-]*"
ENTRY_TEXT = "text"
ENTRY_INJECTED = "injected"
FENCE_LINE = "---"
# One authored frontmatter line: exactly one space after the colon, and a value.
AUTHORED_FIELD = re.compile(rf"({FIELD_NAME}): (\S.*)")
# A value opening with one of these is YAML structure — a flow collection, a
# block scalar, an anchor, alias, tag, directive or comment, or a reserved
# indicator — not a flat scalar; a value opening with a marker is not refused.
STRUCTURED_VALUE_OPENERS = "[]{},|>&*!%#@`"
# These open structure only when a blank or the line's end follows.
BLANK_LED_INDICATORS = "-?:"
INDENT = "  "
NAME_FIELD = "name"
TOOLS_FIELD = "tools"
# SPEC.md's dispatch keys: a definition authoring none of them is undispatchable.
DISPATCH_FIELDS = ("name", "description", "model")
AUTHORED_VALUE_SLOT = "authored-value"
OUTPUT_STEM_SLOT = "output-stem"
TOOLS_SLOT = "tools"
PERMISSION_SLOT = "tools-as-permission"
UNDISPATCHABLE_SLOT = "undispatchable-marker"
TOOL_SLOTS = (TOOLS_SLOT, PERMISSION_SLOT)


class FrontmatterEntry(NamedTuple):
    """One field's rendering rule: the slot text expanded to give its value,
    and whether it is emitted whether or not the template authors the field."""

    text: str
    injected: bool


class FrontmatterRules(NamedTuple):
    """One harness's [harness.agent-frontmatter] and [harness.tools] tables.

    `entries` maps an output field to its rule, or to None where the harness
    elides it. `tools` maps a vocabulary name to the harness's spellings.
    `source` is the harness file, as a refusal names it.
    """

    entries: dict[str, FrontmatterEntry | None]
    tools: dict[str, tuple[str, ...]]
    source: str


def load_frontmatter_rules(entries: object, tools: object, *, source: str) -> FrontmatterRules:
    """Validate a harness file's two structural tables; an absent table is
    passed as an empty one."""
    return FrontmatterRules(
        entries=_load_entries(entries, where=f"{source}: [harness.{FRONTMATTER_TABLE_KEY}]"),
        tools=_load_tools(tools, where=f"{source}: [harness.{TOOLS_TABLE_KEY}]"),
        source=source,
    )


def _load_entries(table: object, *, where: str) -> dict[str, FrontmatterEntry | None]:
    if not isinstance(table, dict):
        raise InputError(f"{where}: must be a table of field entries")
    entries: dict[str, FrontmatterEntry | None] = {}
    for field, value in table.items():
        at = f"{where} {field}"
        if re.fullmatch(FIELD_NAME, field) is None:
            raise InputError(f"{at}: '{field}' is not a frontmatter field name — it must match {FIELD_NAME}")
        if value is False:
            entries[field] = None
            continue
        if isinstance(value, str):
            value = {ENTRY_TEXT: value}
        if not isinstance(value, dict):
            raise InputError(f"{at}: an entry is a string, a {{ {ENTRY_TEXT}, {ENTRY_INJECTED} }} table, or false")
        unknown = sorted(set(value) - {ENTRY_TEXT, ENTRY_INJECTED})
        if unknown:
            raise InputError(f"{at}: unknown key(s) {unknown} — an entry table holds {ENTRY_TEXT} and {ENTRY_INJECTED}")
        if ENTRY_TEXT not in value:
            raise InputError(f"{at}: an entry table needs a '{ENTRY_TEXT}' — false is the one spelling of elision")
        if not isinstance(value[ENTRY_TEXT], str):
            raise InputError(f"{at}: '{ENTRY_TEXT}' must be a string")
        injected = value.get(ENTRY_INJECTED, False)
        if not isinstance(injected, bool):
            raise InputError(f"{at}: '{ENTRY_INJECTED}' must be true or false")
        entries[field] = FrontmatterEntry(value[ENTRY_TEXT], injected)
    return entries


def _load_tools(table: object, *, where: str) -> dict[str, tuple[str, ...]]:
    if not isinstance(table, dict):
        raise InputError(f"{where}: must be a table of tool names")
    tools: dict[str, tuple[str, ...]] = {}
    for name, value in table.items():
        at = f"{where} {name}"
        if re.fullmatch(IDENTIFIER, name) is None:
            raise InputError(f"{at}: '{name}' is not a tool name — it must match {IDENTIFIER}")
        spellings = [value] if isinstance(value, str) else value
        if not isinstance(spellings, list) or not spellings or not all(isinstance(s, str) and s for s in spellings):
            raise InputError(f"{at}: must be a non-empty string or a non-empty list of them")
        tools[name] = tuple(spellings)
    return tools


class AuthoredField(NamedTuple):
    """One authored `key: value` line, its value raw."""

    key: str
    value: str


# A parsed authored line: a field, or a comment or blank line kept as it is.
AuthoredLine = AuthoredField | str


def is_fence_line(line: str) -> bool:
    """Whether `line` opens or closes a frontmatter block: `---`, surrounding whitespace ignored.

    The one fence test for authored templates and rendered or installed definitions alike.
    """
    return line.strip() == FENCE_LINE


def split_authored(body: str, *, where: str) -> tuple[list[AuthoredLine], str] | None:
    """A body's authored frontmatter, parsed, and the body from the closing
    `---` line on; None for a body that opens with no frontmatter block. An
    opening `---` line with no closing one is refused."""
    lines = body.split("\n")
    if not is_fence_line(lines[0]):
        return None
    close = next((at for at, line in enumerate(lines[1:], start=1) if is_fence_line(line)), None)
    if close is None:
        raise InputError(f"{where}: frontmatter opens with '{FENCE_LINE}' and never closes")
    parsed: list[AuthoredLine] = []
    seen: set[str] = set()
    for line in lines[1:close]:
        if not line.strip() or line.startswith("#"):
            parsed.append(line)
            continue
        match = AUTHORED_FIELD.fullmatch(line)
        if match is None or not _is_flat_value(match.group(2)):
            raise InputError(
                f"{where}: frontmatter line {line!r} is not a flat 'key: value' line — authored frontmatter holds "
                "single-line fields (one space after the colon), comments and blank lines only"
            )
        key, value = match.groups()
        if key in seen:
            raise InputError(f"{where}: frontmatter authors '{key}' twice")
        seen.add(key)
        parsed.append(AuthoredField(key, value))
    return parsed, "\n".join(lines[close:])


def _is_flat_value(value: str) -> bool:
    """Whether a raw authored value (non-empty, opening on a non-blank) is a flat scalar."""
    if MARKER.match(value):
        return True
    first = value[0]
    if first in STRUCTURED_VALUE_OPENERS:
        return False
    return not (first in BLANK_LED_INDICATORS and (len(value) == 1 or value[1] in " \t"))


def field_plan(
    authored: list[AuthoredLine], rules: FrontmatterRules, *, where: str
) -> list[str | tuple[str, FrontmatterEntry]]:
    """What one output's frontmatter emits, in order: comment and blank lines
    as they are, and each field with the entry rendering it — authored fields
    first, then the injected entries. Elided fields are dropped."""
    authored_fields = {line.key for line in authored if isinstance(line, AuthoredField)}
    plan: list[str | tuple[str, FrontmatterEntry]] = []
    for line in authored:
        if isinstance(line, str):
            plan.append(line)
            continue
        if line.key not in rules.entries:
            raise InputError(
                f"{where}: authors '{line.key}', for which {rules.source} [harness.{FRONTMATTER_TABLE_KEY}] has no "
                "entry — every authored field needs one, false to elide it"
            )
        entry = rules.entries[line.key]
        if entry is not None and entry.injected:
            raise InputError(
                f"{where}: authors '{line.key}', which {rules.source} [harness.{FRONTMATTER_TABLE_KEY}] injects — "
                "an injected field is never authored"
            )
        if entry is not None:
            plan.append((line.key, entry))
    plan += [
        (field, entry)
        for field, entry in rules.entries.items()
        if entry is not None and entry.injected and field not in authored_fields
    ]
    return plan


def tool_slots(value: str | None, rules: FrontmatterRules, *, where: str) -> dict[str, str]:
    """Both tools slots from one parse of the expanded authored `tools` value
    (None when not authored) and one lookup through [harness.tools]."""
    if value is None:
        return dict.fromkeys(TOOL_SLOTS, "")
    if value.startswith("["):
        raise InputError(f"{where}: tools '{value}' is a flow list — author a comma-separated list of tool names")
    mapped: list[str] = []
    for name in (item.strip() for item in value.split(",")):
        if not name:
            raise InputError(f"{where}: tools '{value}' holds an empty item")
        if name not in rules.tools:
            raise InputError(
                f"{where}: authors tool '{name}', which {rules.source} [harness.{TOOLS_TABLE_KEY}] does not name — "
                f"tools are authored in that table's names: {', '.join(rules.tools)}"
            )
        mapped += rules.tools[name]
    governed = dict.fromkeys(spelling for spellings in rules.tools.values() for spelling in spellings)
    return {
        TOOLS_SLOT: ", ".join(mapped),
        PERMISSION_SLOT: "\n".join(f"{key}: {'allow' if key in mapped else 'deny'}" for key in governed),
    }


class EntrySlots(Mapping[str, str | Verbatim]):
    """The invocation parameters one entry's text expands under: `base` plus
    the five slots, the two tools slots read through `tools` on first use."""

    def __init__(
        self,
        base: Mapping[str, str | Verbatim],
        *,
        authored_value: str,
        output: str,
        undispatchable: bool,
        tools: Callable[[], dict[str, str]],
    ) -> None:
        self._base = base
        self._fixed: dict[str, str | Verbatim] = {
            AUTHORED_VALUE_SLOT: authored_value,
            OUTPUT_STEM_SLOT: Verbatim(output),
            UNDISPATCHABLE_SLOT: "true" if undispatchable else "",
        }
        self._tools = tools

    def __getitem__(self, key: str) -> str | Verbatim:
        if key in self._fixed:
            return self._fixed[key]
        if key in TOOL_SLOTS:
            return self._tools()[key]
        return self._base[key]

    def __iter__(self) -> Iterator[str]:
        return iter([*self._base, *self._fixed, *TOOL_SLOTS])

    def __len__(self) -> int:
        return len(self._base) + len(self._fixed) + len(TOOL_SLOTS)


def assemble(items: list[str | tuple[str, Expansion]], rest: Expansion) -> Expansion:
    """The output: an opening `---` line, each item a line — a comment or blank
    line as it is, a field from its expanded text, elided when that is empty —
    and `rest`, the body from the closing `---` line on. Verbatim spans keep
    their place in the joined text."""
    parts = [Expansion(FENCE_LINE + "\n", ())]
    for item in items:
        if isinstance(item, str):
            parts.append(Expansion(item + "\n", ()))
        elif item[1].text:
            parts.append(_field_lines(*item))
    parts.append(rest)
    text, spans = "", []
    for part in parts:
        spans += [VerbatimSpan(len(text) + span.offset, span.text, span.marker) for span in part.verbatim]
        text += part.text
    return Expansion(text, tuple(spans))


def _field_lines(field: str, value: Expansion) -> Expansion:
    """`<field>: <text>`, or `<field>:` over the text's lines indented."""
    multiline = "\n" in value.text
    head = f"{field}:\n{INDENT}" if multiline else f"{field}: "

    def shifted(offset: int) -> int:
        return len(head) + offset + len(INDENT) * value.text.count("\n", 0, offset)

    return Expansion(
        head + value.text.replace("\n", "\n" + INDENT) + "\n",
        tuple(
            VerbatimSpan(shifted(span.offset), span.text.replace("\n", "\n" + INDENT), span.marker)
            for span in value.verbatim
        ),
    )
