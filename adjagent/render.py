"""The renderer: every discovered definition to its file text, its banner, the
files a harness renders beside them, and the writer. Holds no prose, knows no
individual definition, fills a body's placeholders in one pass and never rescans
what it filled, and writes the rendered definitions and harness files."""

from __future__ import annotations

import dataclasses
import functools
import re
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath
from typing import cast

from adjagent import __version__
from adjagent.context import DEFAULT_FAMILY, Render, map_spec
from adjagent.definition import Definition, SkillFile
from adjagent.definitions import discover
from adjagent.errors import InputError
from adjagent.harness import AgentFields, Harness, quoted
from adjagent.loading import load
from adjagent.vocabulary import (
    ALL,
    AgentsFileText,
    Anchor,
    HarnessText,
    Kind,
    OptionalHarnessText,
    Tier,
    TuningText,
    hole,
    reference,
)

GENERATED_MARK = "!GENERATED! from "
GENERATED_NOTICE = (
    "do not edit here: request changes from the adjagent project; local needs belong in your CONVENTIONS.md."
)
PLACEHOLDER = re.compile(r"@![a-z0-9.-]+!@")


def keyed_by_path(
    discovered: Iterable[tuple[str, tuple[Definition, ...]]],
) -> tuple[tuple[str, Definition], ...]:
    """(defining module's dotted name, Definition) for every entry, sorted by output path; any path a
    definition produces — its own output or a supporting file's — produced twice is refused, naming both
    modules."""
    entries = [(module, defn) for module, group in discovered for defn in group]
    shown: dict[PurePosixPath, str] = {}
    for module, defn in entries:
        for path in defn.output_paths:
            if path in shown:
                raise InputError(f"output '{path}' is produced by both {shown[path]} and {module}")
            shown[path] = module
    return tuple(sorted(entries, key=lambda entry: entry[1].output_path))


def definitions(*, include: Callable[[Definition], bool] | None = None) -> tuple[tuple[str, Definition], ...]:
    """Every discovered definition but the agents file, which has no output path, as keyed_by_path gives
    it; `include` keeps only the definitions it accepts, the definition whole — a skill is one decision,
    never one per path. The duplicate check runs before `include`, so a collision an excluded definition
    takes part in is refused by every run rather than only by one that renders it."""
    everything = keyed_by_path(
        (module, tuple(defn for defn in entries if defn.kind is not Kind.AGENTS_FILE)) for module, entries in discover()
    )
    return tuple(entry for entry in everything if include is None or include(entry[1]))


def agent_fields(defn: Definition, ctx: Render) -> AgentFields:
    """Map an agent through ctx.harness: description filled as `filled_description` fills it; model via
    ctx.model(defn.tier); tools to spellings (None for ALL); governed as the de-duplicated image of
    ctx.harness.tools in table order."""
    table = ctx.harness.tools
    return AgentFields(
        name=defn.name,
        description=filled_description(defn, ctx),
        model=ctx.model(defn.tier),
        color=defn.color,
        tools=None if defn.tools is ALL else tuple(spelling for tool in defn.tools for spelling in table[tool]),
        governed=tuple(dict.fromkeys(spelling for spellings in table.values() for spelling in spellings)),
    )


def generated_text(module: str) -> str:
    """`!GENERATED! from <module path> — ` + GENERATED_NOTICE: the banner's payload, which each carrier
    surrounds its own way. The module path is repository-relative, built out of the dotted module name and
    never out of __file__."""
    return f"{GENERATED_MARK}{'/'.join(module.split('.'))}.py — {GENERATED_NOTICE}"


def generated_line(module: str) -> str:
    """`# ` and the generated payload: the frontmatter and copied-file carrier's first line."""
    return f"# {generated_text(module)}"


def tuning_text(ctx: Render, *, seat: Tier | None) -> str:
    """`!TUNING! family=… seat=… member=… tier=…`, then ` alias=…` only when the alias map is set,
    then ` stock=…` (`none` when empty) and ` harness=…` last. A tiered definition renders its seat; one
    declaring no tier renders `seat=none member=none`."""
    member = "none" if seat is None else ctx.tier_map[seat]
    aliases = "" if ctx.alias_map is None else f" alias={map_spec(ctx.alias_map)}"
    return (
        f"!TUNING! family={ctx.family.name} seat={seat or 'none'} member={member}"
        f" tier={map_spec(ctx.tier_map)}{aliases}"
        f" stock={','.join(ctx.stock) or 'none'}"
        f" harness={ctx.harness.name}"
    )


def tuning_line(ctx: Render, *, seat: Tier | None) -> str:
    """`# ` and the tuning payload: the frontmatter and copied-file carrier's second line."""
    return f"# {tuning_text(ctx, seat=seat)}"


def _field_lines(defn: Definition, ctx: Render) -> tuple[str, ...]:
    if defn.kind is Kind.AGENT:
        return ctx.harness.frontmatter(agent_fields(defn, ctx))
    if defn.kind is Kind.DOCUMENT:
        return ctx.harness.document_frontmatter
    if defn.kind is Kind.SKILL:
        return (f"name: {defn.name}", f"description: {quoted(filled_description(defn, ctx))}")
    return ()


def _frontmatter(defn: Definition, ctx: Render, *, module: str) -> str:
    """The opening fence, the two banner lines, the kind's field lines, the closing fence, then the
    blank line before the body, which a command omits."""
    fields = "".join(line + "\n" for line in _field_lines(defn, ctx))
    gap = "" if defn.kind is Kind.COMMAND else "\n"
    return f"---\n{generated_line(module)}\n{tuning_line(ctx, seat=defn.tier)}\n{fields}---\n{gap}"


@functools.cache
def _references(prefix: str) -> dict[str, str]:
    """The reference hole of every discovered definition, the agents file included, mapped to `prefix`
    and its name; built once per prefix, so discovery runs once rather than on every fill."""
    return {reference(named.name): prefix + named.name for _, entries in discover() for named in entries}


def filled_text(body: str, defn: Definition, ctx: Render, *, where: str) -> str:
    """`body` with every placeholder filled in one pass: a harness text from ctx.harness, an anchor
    from ctx.overlay for the definition's seat ("" where the family fills none), the step-down model
    from ctx.step_down_model for every kind, a reference to any discovered definition, the agents
    file included, as ctx.harness.reference_prefix and its name, and for the agents file alone its
    scope name and the package version. A paragraph that fills to nothing is dropped with its blank line, so an unfilled
    anchor or an optional harness text the harness supplies nothing for, standing as its own
    paragraph, leaves no empty one. A paragraph whose source holds a tuning hole that fills to "" is dropped whole,
    whatever else it says. A placeholder-shaped span naming no key is refused, naming `where`.
    Filled text is not rescanned."""
    seated = dataclasses.replace(ctx, seat=defn.tier)
    values = {hole(part): ctx.harness.text(part) for part in (*HarnessText, *OptionalHarnessText)}
    values.update({hole(anchor): seated.overlay(anchor) for anchor in Anchor})
    values[hole(TuningText.STEP_DOWN_MODEL)] = ctx.step_down_model
    values.update(_references(ctx.harness.reference_prefix))
    if defn.kind is Kind.AGENTS_FILE:
        values[hole(AgentsFileText.SCOPE_NAME)] = ctx.scope
        values[hole(AgentsFileText.VERSION)] = __version__
    unfilled_tuning = {hole(part) for part in TuningText if not values[hole(part)]}

    def value(match: re.Match[str]) -> str:
        if match[0] not in values:
            raise InputError(f"{where}: unknown placeholder {match[0]}")
        return values[match[0]]

    paragraphs = body.split("\n\n")
    filled = [PLACEHOLDER.sub(value, paragraph) for paragraph in paragraphs]
    return "\n\n".join(
        text
        for text, source in zip(filled, paragraphs)
        if (text or not source) and unfilled_tuning.isdisjoint(PLACEHOLDER.findall(source))
    )


def filled_body(defn: Definition, ctx: Render) -> str:
    """The definition's own body, filled as `filled_text` fills it and named as the definition it belongs
    to."""
    return filled_text(defn.body, defn, ctx, where=f"definition '{defn.name}'")


def filled_description(defn: Definition, ctx: Render) -> str:
    """The definition's description, filled as `filled_text` fills a body and named as the definition's
    description; only an agent's and a skill's are rendered, and each has one."""
    return filled_text(cast(str, defn.description), defn, ctx, where=f"definition '{defn.name}' description")


def render_definition(defn: Definition, ctx: Render, *, module: str) -> str:
    """The file text: the frontmatter, the filled body, and one final newline."""
    return f"{_frontmatter(defn, ctx, module=module)}{filled_body(defn, ctx)}\n"


def render_skill_file(defn: Definition, file: SkillFile, ctx: Render, *, module: str) -> str:
    """A skill's supporting file: the two banner lines as HTML comments, the blank line after them, the
    filled body, and one final newline. Nothing about how the file reads depends on the banner."""
    where = str(defn.file_output_path(file))
    return (
        f"<!-- {generated_text(module)} -->\n"
        f"<!-- {tuning_text(ctx, seat=defn.tier)} -->\n"
        f"\n{filled_text(file.body, defn, ctx, where=where)}\n"
    )


def harness_renders(ctx: Render) -> tuple[tuple[PurePosixPath, str], ...]:
    """(path, text) for every file `ctx.harness` renders into the output root, sorted by path; empty for
    a harness that renders none."""
    return tuple(sorted((PurePosixPath(file.path), file.text()) for file in ctx.harness.rendered_files))


def rendered_definitions(
    ctx: Render, *, include: Callable[[Definition], bool] | None = None
) -> tuple[tuple[str, Definition], ...]:
    """The definitions `render_all` renders, as `definitions` gives them: `include` composed with
    `ctx.harness.omits`, so a name the harness renders nothing for is dropped whatever the caller's
    filter says."""
    return definitions(include=lambda defn: defn.name not in ctx.harness.omits and (include is None or include(defn)))


def render_all(
    ctx: Render, *, include: Callable[[Definition], bool] | None = None
) -> tuple[tuple[PurePosixPath, str], ...]:
    """(output path, text) for every file every definition `rendered_definitions` keeps produces — a
    definition's own output, then each of its supporting files — and then the files `ctx.harness`
    renders of its own, sorted by path."""
    rendered: list[tuple[PurePosixPath, str]] = []
    for module, defn in rendered_definitions(ctx, include=include):
        rendered.append((defn.output_path, render_definition(defn, ctx, module=module)))
        rendered += [
            (defn.file_output_path(file), render_skill_file(defn, file, ctx, module=module)) for file in defn.files
        ]
    rendered += harness_renders(ctx)
    return tuple(sorted(rendered))


def render_agents_file(harness: Harness, *, scope: str) -> str:
    """The harness agents file as a fresh file holds it: the agents-file definition's body filled for
    `harness` and `scope` under the default family's own tiers, whatever the invocation's tuning and
    with no harness model-shape check, then one final newline."""
    [defn] = [defn for _, entries in discover() for defn in entries if defn.kind is Kind.AGENTS_FILE]
    family = load("adjagent.families", "FAMILY")[DEFAULT_FAMILY]
    ctx = Render(harness=harness, family=family, tier_map=dict(family.tiers), scope=scope)
    return filled_body(defn, ctx) + "\n"


def write_text_verbatim(path: Path, text: str) -> None:
    """Write `text` to `path` as utf-8 with no newline translation."""
    with path.open("w", encoding="utf-8", newline="") as stream:
        stream.write(text)


def appended_paragraph(text: str, paragraph: str) -> str:
    """`text` unchanged, then `paragraph` after one blank line, ending with a newline."""
    if not text:
        return f"{paragraph}\n"
    if text.endswith("\n\n"):
        return f"{text}{paragraph}\n"
    if text.endswith("\n"):
        return f"{text}\n{paragraph}\n"
    return f"{text}\n\n{paragraph}\n"


def write_renders(out: Path, renders: Iterable[tuple[PurePosixPath, str]]) -> list[Path]:
    """Write each text under `out` (an existing directory, else InputError) as utf-8 with no newline
    translation, creating parents and overwriting; return the paths written."""
    if not out.is_dir():
        raise InputError(f"output root '{out}' is not an existing directory")
    written = []
    for relative, text in renders:
        target = out.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        write_text_verbatim(target, text)
        written.append(target)
    return written
