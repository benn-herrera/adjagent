"""The renderer: every definition a render's plugin ships to its file text, its banner, the
files a harness renders beside them, and the writer. Holds no prose, knows no
individual definition, fills a body's placeholders in one pass and never rescans
what it filled, and writes the rendered definitions and harness files."""

from __future__ import annotations

import dataclasses
import functools
import re
from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from typing import cast

from devpro import __version__
from devpro.context import DEFAULT_FAMILY, Render, map_spec
from devpro.definition import Definition, SkillFile
from devpro.definitions import discover
from devpro.errors import InputError
from devpro.harness import AgentFields, FrontmatterForm, Harness, HarnessFile, ShippedDefinition, quoted
from devpro.loading import load
from devpro.plugin import Plugin
from devpro.vocabulary import (
    ALL,
    AgentsFileText,
    Anchor,
    HarnessText,
    Kind,
    OptionalHarnessText,
    PluginText,
    Tier,
    TuningText,
    hole,
    optional_reference,
    reference,
)

GENERATED_MARK = "!GENERATED! from "
GENERATED_NOTICE = (
    "do not edit here: request changes from the devpro project; local needs belong in your CONVENTIONS.md."
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


def definitions() -> tuple[tuple[str, Definition], ...]:
    """Every discovered definition but the agents file, which has no output path, as keyed_by_path gives
    it. The duplicate check runs over all of them, so a collision a definition outside a render's plugin
    takes part in is refused by every render rather than only by one that ships it."""
    return keyed_by_path(
        (module, tuple(defn for defn in entries if defn.kind is not Kind.AGENTS_FILE)) for module, entries in discover()
    )


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


def tuning_text(ctx: Render, *, tier: Tier | None) -> str:
    """`!TUNING! family=… tier=… member=… tier-map=…`, then ` alias=…` only when the alias map is set,
    then ` stock=…` (`none` when empty) and ` harness=…` last. A tiered definition renders its tier; one
    declaring no tier renders `tier=none member=none`."""
    member = "none" if tier is None else ctx.tier_map[tier]
    aliases = "" if ctx.alias_map is None else f" alias={map_spec(ctx.alias_map)}"
    return (
        f"!TUNING! family={ctx.family.name} tier={tier or 'none'} member={member}"
        f" tier-map={map_spec(ctx.tier_map)}{aliases}"
        f" stock={','.join(ctx.stock) or 'none'}"
        f" harness={ctx.harness.name}"
    )


def tuning_line(ctx: Render, *, tier: Tier | None) -> str:
    """`# ` and the tuning payload: the frontmatter and copied-file carrier's second line."""
    return f"# {tuning_text(ctx, tier=tier)}"


def _field_lines(defn: Definition, ctx: Render, *, form: FrontmatterForm) -> tuple[str, ...]:
    if defn.kind is Kind.AGENT:
        return form.agent(agent_fields(defn, ctx))
    if defn.kind is Kind.DOCUMENT:
        return form.document
    if defn.kind is Kind.SKILL:
        return (f"name: {defn.name}", f"description: {quoted(filled_description(defn, ctx))}")
    return ()


def _frontmatter(defn: Definition, ctx: Render, *, module: str, form: FrontmatterForm) -> str:
    """The opening fence, the two banner lines, the kind's field lines, the closing fence, then the
    blank line before the body, which a command omits."""
    fields = "".join(line + "\n" for line in _field_lines(defn, ctx, form=form))
    gap = "" if defn.kind is Kind.COMMAND else "\n"
    return f"---\n{generated_line(module)}\n{tuning_line(ctx, tier=defn.tier)}\n{fields}---\n{gap}"


def _comment_banner(ctx: Render, *, module: str, tier: Tier | None) -> str:
    """The two banner lines as HTML comments, then the blank line before the body: the carrier of a file
    holding no frontmatter."""
    return f"<!-- {generated_text(module)} -->\n<!-- {tuning_text(ctx, tier=tier)} -->\n\n"


@functools.cache
def _referents() -> dict[str, str]:
    """The reference hole of every discovered definition, the agents file included, mapped to its name;
    built once, so discovery runs once rather than on every fill."""
    return {reference(named.name): named.name for _, entries in discover() for named in entries}


@functools.cache
def _references(prefix: str, shipped: frozenset[str]) -> dict[str, str]:
    """For a render shipping the definitions `shipped`, the value of each reference hole it can fill: a
    plain or optional reference to a shipped definition is `prefix` and its name, and an optional
    reference to any other discovered definition is "". A plain reference to a definition not shipped
    has no value."""
    values: dict[str, str] = {}
    for name in _referents().values():
        if name in shipped:
            values[reference(name)] = values[optional_reference(name)] = prefix + name
        else:
            values[optional_reference(name)] = ""
    return values


def filled_text(body: str, defn: Definition, ctx: Render, *, where: str) -> str:
    """`body` with every placeholder filled in one pass: a harness text from ctx.bound_harness, the
    plugin's name from ctx.plugin, an anchor from ctx.overlay for the definition's tier ("" where the family
    fills none), the step-down model from ctx.step_down_model for every kind, a reference to a definition
    the render ships as ctx.bound_harness.reference_prefix and its name, and for the agents file alone its
    scope name and the package version. A paragraph that fills to nothing is dropped with its blank
    line, so an unfilled anchor standing as its own paragraph leaves no empty one. A paragraph whose
    source holds a tuning hole or an optional harness text that fills to "", or an optional reference
    to a definition the render does not ship, is dropped whole, whatever else it says. A plain reference to a definition the render does not ship is refused, naming `where` and the
    definition; so is a placeholder-shaped span naming no key. Filled text is not rescanned."""
    seated = dataclasses.replace(ctx, tier=defn.tier)
    shipped = frozenset(name for name in _referents().values() if ctx.plugin.ships(name))
    values = {hole(part): ctx.bound_harness.text(part) for part in (*HarnessText, *OptionalHarnessText)}
    values.update({hole(anchor): seated.overlay(anchor) for anchor in Anchor})
    values[hole(TuningText.STEP_DOWN_MODEL)] = ctx.step_down_model
    values[hole(PluginText.NAME)] = ctx.plugin.name
    references = _references(ctx.bound_harness.reference_prefix, shipped)
    values.update(references)
    if defn.kind is Kind.AGENTS_FILE:
        values[hole(AgentsFileText.SCOPE_NAME)] = ctx.scope
        values[hole(AgentsFileText.VERSION)] = __version__
    drops_whole = {hole(part) for part in (*TuningText, *OptionalHarnessText) if not values[hole(part)]}
    drops_whole.update(placeholder for placeholder, text in references.items() if not text)

    def value(match: re.Match[str]) -> str:
        if match[0] in values:
            return values[match[0]]
        if match[0] in _referents():
            raise InputError(f"{where}: references '{_referents()[match[0]]}', which this render does not ship")
        raise InputError(f"{where}: unknown placeholder {match[0]}")

    paragraphs = body.split("\n\n")
    filled = [PLACEHOLDER.sub(value, paragraph) for paragraph in paragraphs]
    return "\n\n".join(
        text
        for text, source in zip(filled, paragraphs)
        if (text or not source) and drops_whole.isdisjoint(PLACEHOLDER.findall(source))
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
    """The file text: the frontmatter, or the comment banner under a harness whose definition form is a
    registry, then the filled body and one final newline."""
    form = ctx.harness.definition_form
    if isinstance(form, FrontmatterForm):
        opening = _frontmatter(defn, ctx, module=module, form=form)
    else:
        opening = _comment_banner(ctx, module=module, tier=defn.tier)
    return f"{opening}{filled_body(defn, ctx)}\n"


def render_skill_file(defn: Definition, file: SkillFile, ctx: Render, *, module: str) -> str:
    """A skill's supporting file: the comment banner, the filled body, and one final newline. Nothing about
    how the file reads depends on the banner."""
    where = str(defn.file_output_path(file))
    return f"{_comment_banner(ctx, module=module, tier=defn.tier)}{filled_text(file.body, defn, ctx, where=where)}\n"


def rendered_definitions(ctx: Render) -> tuple[tuple[str, Definition], ...]:
    """The definitions `render_all` renders, as `definitions` gives them: those `ctx.plugin` ships: its
    plugin's members."""
    return tuple(entry for entry in definitions() if ctx.plugin.ships(entry[1].name))


def shipped_definitions(ctx: Render) -> tuple[ShippedDefinition, ...]:
    """Every definition `rendered_definitions` keeps, in the general form a harness-rendered file reads."""
    return tuple(
        ShippedDefinition(
            name=defn.name,
            reference=ctx.bound_harness.reference_prefix + defn.name,
            kind=defn.kind,
            path=str(defn.output_path),
            description=None if defn.description is None else filled_description(defn, ctx),
            agent=agent_fields(defn, ctx) if defn.kind is Kind.AGENT else None,
        )
        for _, defn in rendered_definitions(ctx)
    )


def harness_file_text(file: HarnessFile, ctx: Render) -> str:
    """`file`'s whole text for this render: built from the bound plugin's name and the definitions it
    ships."""
    return file.text(ctx.plugin.name, shipped_definitions(ctx))


def shipped_harness_files(ctx: Render) -> tuple[HarnessFile, ...]:
    """Every file `ctx.bound_harness` renders into the output root whose owner, where it names one, this
    render ships."""
    return tuple(file for file in ctx.bound_harness.harness_files if file.owner is None or ctx.plugin.ships(file.owner))


def harness_renders(ctx: Render) -> tuple[tuple[PurePosixPath, str], ...]:
    """(path, text) for every file `shipped_harness_files` names, sorted by path; empty for a harness that
    renders none."""
    return tuple(
        sorted((PurePosixPath(file.path), harness_file_text(file, ctx)) for file in shipped_harness_files(ctx))
    )


def render_all(ctx: Render) -> tuple[tuple[PurePosixPath, str], ...]:
    """(output path, text) for every file every definition `rendered_definitions` keeps produces — a
    definition's own output, then each of its supporting files — and then the files `ctx.harness`
    renders of its own, sorted by path."""
    rendered: list[tuple[PurePosixPath, str]] = []
    for module, defn in rendered_definitions(ctx):
        rendered.append((defn.output_path, render_definition(defn, ctx, module=module)))
        rendered += [
            (defn.file_output_path(file), render_skill_file(defn, file, ctx, module=module)) for file in defn.files
        ]
    rendered += harness_renders(ctx)
    return tuple(sorted(rendered))


def render_agents_file(harness: Harness, plugin: Plugin, *, scope: str) -> str:
    """The harness agents file as a fresh file holds it for `plugin`: the agents-file definition's body
    filled for `harness` bound to `plugin` and for `scope`, under the default family's own tiers,
    whatever the invocation's tuning and with no harness model-shape check, then one final newline."""
    [defn] = [defn for _, entries in discover() for defn in entries if defn.kind is Kind.AGENTS_FILE]
    family = load("devpro.families", "FAMILY")[DEFAULT_FAMILY]
    ctx = Render(harness=harness, plugin=plugin, family=family, tier_map=dict(family.tiers), scope=scope)
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
