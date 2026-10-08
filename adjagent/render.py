"""The renderer: every discovered definition to its file text, its banner, and
the writer. Holds no prose, knows no individual definition, never searches text
it has composed, and is the only module that writes files."""

from collections.abc import Iterable
from pathlib import Path, PurePosixPath

from adjagent.context import Render, map_spec
from adjagent.definition import ALL, Definition, Tier
from adjagent.definitions import discover
from adjagent.errors import InputError
from adjagent.harness import AgentFields

GENERATED_NOTICE = (
    "do not edit here: request changes from the adjagent project; local needs belong in your CONVENTIONS.md."
)


def definitions(ctx: Render) -> tuple[tuple[str, Definition], ...]:
    """(defining module's dotted name, Definition) for every output of every discovered function,
    sorted by name; a name produced twice is refused, naming both modules."""
    produced: dict[str, tuple[str, Definition]] = {}
    for function in discover():
        result = function(ctx)
        for defn in result if isinstance(result, tuple) else (result,):
            if defn.name in produced:
                raise InputError(
                    f"definition '{defn.name}' is produced by both {produced[defn.name][0]} and {function.__module__}"
                )
            produced[defn.name] = (function.__module__, defn)
    return tuple(produced[name] for name in sorted(produced))


def agent_fields(defn: Definition, ctx: Render) -> AgentFields:
    """Map defn through ctx.harness: model via ctx.model(defn.tier); tools to spellings (None for
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


def tuning_line(ctx: Render, *, seat: Tier) -> str:
    """`# !TUNING! family=… seat=… member=… tier=…`, then ` alias=…` only when the alias map is set,
    then ` stock=…` (`none` when empty) and ` harness=…` last."""
    aliases = "" if ctx.alias_map is None else f" alias={map_spec(ctx.alias_map)}"
    return (
        f"# !TUNING! family={ctx.family.name} seat={seat} member={ctx.tier_map[seat]}"
        f" tier={map_spec(ctx.tier_map)}{aliases}"
        f" stock={','.join(ctx.stock) or 'none'}"
        f" harness={ctx.harness.name}"
    )


def render_definition(defn: Definition, ctx: Render, *, module: str) -> str:
    """The file text: the opening fence, the two banner lines, the harness's field lines, the closing
    fence, one blank line, the sections joined by a blank line, and one final newline."""
    fields = "".join(line + "\n" for line in ctx.harness.frontmatter(agent_fields(defn, ctx)))
    return (
        f"---\n{generated_line(module)}\n{tuning_line(ctx, seat=defn.tier)}\n{fields}---\n\n"
        + "\n\n".join(defn.sections)
        + "\n"
    )


def render_all(ctx: Render) -> tuple[tuple[PurePosixPath, str], ...]:
    """(PurePosixPath("agents", f"{name}.md"), text) for every definition, sorted by path."""
    rendered = (
        (PurePosixPath("agents", f"{defn.name}.md"), render_definition(defn, ctx, module=module))
        for module, defn in definitions(ctx)
    )
    return tuple(sorted(rendered, key=lambda item: item[0]))


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
