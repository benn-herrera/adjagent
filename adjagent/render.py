"""The renderer: every discovered definition to its file text, its banner, and
the writer. Holds no prose, knows no individual definition, fills a body's
placeholders in one pass and never rescans what it filled, and is the only
module that writes files."""

import dataclasses
import re
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

from adjagent.context import Render, map_spec
from adjagent.definition import Definition
from adjagent.definitions import discover
from adjagent.errors import InputError
from adjagent.harness import AgentFields
from adjagent.vocabulary import ALL, Anchor, HarnessText, Kind, Tier, hole

GENERATED_NOTICE = (
    "do not edit here: request changes from the adjagent project; local needs belong in your CONVENTIONS.md."
)
_PLACEHOLDER = re.compile(r"@![a-z0-9.-]+!@")


def keyed_by_path(
    discovered: Iterable[tuple[str, tuple[Definition, ...]]],
) -> tuple[tuple[str, Definition], ...]:
    """(defining module's dotted name, Definition) for every entry, sorted by output path; an output
    path produced twice is refused, naming both modules."""
    produced: dict[PurePosixPath, tuple[str, Definition]] = {}
    for module, entries in discovered:
        for defn in entries:
            path = defn.output_path
            if path in produced:
                raise InputError(f"output '{path}' is produced by both {produced[path][0]} and {module}")
            produced[path] = (module, defn)
    return tuple(produced[path] for path in sorted(produced))


def definitions() -> tuple[tuple[str, Definition], ...]:
    """Every discovered definition, as keyed_by_path gives it."""
    return keyed_by_path(discover())


def agent_fields(defn: Definition, ctx: Render) -> AgentFields:
    """Map an agent through ctx.harness: model via ctx.model(defn.tier); tools to spellings (None for
    ALL); governed as the de-duplicated image of ctx.harness.tools in table order."""
    table = ctx.harness.tools
    return AgentFields(
        name=defn.name,
        description=defn.description,
        model=ctx.model(defn.tier),
        color=defn.color,
        tools=None if defn.tools is ALL else tuple(spelling for tool in defn.tools for spelling in table[tool]),
        governed=tuple(dict.fromkeys(spelling for spellings in table.values() for spelling in spellings)),
    )


def generated_line(module: str) -> str:
    """`# !GENERATED! from <module path> — ` + GENERATED_NOTICE, one line. The module path is
    repository-relative, built out of the dotted module name and never out of __file__."""
    return f"# !GENERATED! from {'/'.join(module.split('.'))}.py — {GENERATED_NOTICE}"


def tuning_line(ctx: Render, *, seat: Tier | None) -> str:
    """`# !TUNING! family=… seat=… member=… tier=…`, then ` alias=…` only when the alias map is set,
    then ` stock=…` (`none` when empty) and ` harness=…` last. No seat renders `seat=none member=none`."""
    member = "none" if seat is None else ctx.tier_map[seat]
    aliases = "" if ctx.alias_map is None else f" alias={map_spec(ctx.alias_map)}"
    return (
        f"# !TUNING! family={ctx.family.name} seat={seat or 'none'} member={member}"
        f" tier={map_spec(ctx.tier_map)}{aliases}"
        f" stock={','.join(ctx.stock) or 'none'}"
        f" harness={ctx.harness.name}"
    )


def _field_lines(defn: Definition, ctx: Render) -> tuple[str, ...]:
    if defn.kind is Kind.AGENT:
        return ctx.harness.frontmatter(agent_fields(defn, ctx))
    if defn.kind is Kind.DOCUMENT:
        return ctx.harness.document_frontmatter
    return ()


def _frontmatter(defn: Definition, ctx: Render, *, module: str) -> str:
    """The opening fence, the two banner lines, the kind's field lines, the closing fence, then the
    blank line before the body, which a command omits."""
    fields = "".join(line + "\n" for line in _field_lines(defn, ctx))
    gap = "" if defn.kind is Kind.COMMAND else "\n"
    return f"---\n{generated_line(module)}\n{tuning_line(ctx, seat=defn.tier)}\n{fields}---\n{gap}"


def filled_body(defn: Definition, ctx: Render) -> str:
    """The body with every placeholder filled in one pass: a harness text from ctx.harness, an anchor
    from ctx.overlay for the definition's seat ("" where the family fills none). A paragraph that fills
    to nothing is dropped with its blank line, so an unfilled anchor standing as its own paragraph
    leaves no empty one. A placeholder-shaped span naming no key is refused, naming the definition and
    the span. Filled text is not rescanned."""
    seated = dataclasses.replace(ctx, seat=defn.tier)
    values = {hole(part): ctx.harness.text(part) for part in HarnessText}
    values.update({hole(anchor): seated.overlay(anchor) for anchor in Anchor})

    def value(match: re.Match[str]) -> str:
        if match[0] not in values:
            raise InputError(f"definition '{defn.name}': unknown placeholder {match[0]}")
        return values[match[0]]

    paragraphs = defn.body.split("\n\n")
    filled = [_PLACEHOLDER.sub(value, paragraph) for paragraph in paragraphs]
    return "\n\n".join(text for text, source in zip(filled, paragraphs) if text or not source)


def render_definition(defn: Definition, ctx: Render, *, module: str) -> str:
    """The file text: the frontmatter, the filled body, and one final newline."""
    return f"{_frontmatter(defn, ctx, module=module)}{filled_body(defn, ctx)}\n"


def render_all(ctx: Render) -> tuple[tuple[PurePosixPath, str], ...]:
    """(output path, text) for every definition, sorted by path."""
    return tuple((defn.output_path, render_definition(defn, ctx, module=module)) for module, defn in definitions())


def write_renders(out: Path, renders: Iterable[tuple[PurePosixPath, str]]) -> list[Path]:
    """Write each text under `out` (an existing directory, else InputError) as utf-8 with no newline
    translation, creating parents and overwriting; return the paths written."""
    if not out.is_dir():
        raise InputError(f"output root '{out}' is not an existing directory")
    written = []
    for relative, text in renders:
        target = out.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="")
        written.append(target)
    return written
