"""
One template may render SEVERAL definitions. A template that opens with a
fenced TOML block declares them, along with the parameters that differ:

    +++
    [outputs.mad-participant-opus]
    model = "opus"
    color = "#6D28D9"

    [outputs.mad-participant-haiku]
    model = "haiku"
    color = "#5B21B6"
    +++
    ---
    name: @!arg.name!@
    model: @!arg.model!@
    ---
    <one body, rendered identically into every output>

Each declared key is readable in the body as @!arg.<key>!@, plus @!arg.name!@
bound to the output's own name. The fence is where those values are BOUND, so
its keys are bare; the prefix goes where one is CONSUMED (Marker syntax,
`markers` module docstring). Bodies are therefore identical by construction
rather than by maintenance discipline. A template with no such block renders a
single definition named after the template, at the template's mirrored path.
Chunks, variants, markers, wrapping, multi-output declarations, write safety
and backups apply identically to both template types.

Definition selection — --agent-glob and --command-glob:

A pattern is matched against an output's SURFACE-RELATIVE path with the .md
suffix dropped — go-coder, kb-start, mad/participant-contract — under fnmatch
semantics, in which `*` crosses `/`. A nested output is therefore addressable
both by its full key (mad/participant-contract) and by any pattern spanning
the separator (*participant-contract*), and a bare *-coder* selects the
top-level coders without reaching into a subdirectory only because none of
those outputs live in one.

Presence of either glob IMPLIES the surface(s) the run covers: --agent-glob
alone renders the agents surface only, filtered; --command-glob alone
the commands surface only; both, both surfaces, each filtered by its own
patterns; neither, every output, as always. --surfaces is therefore redundant
with a glob and combining them is an argparse error. Narrowing an install is
not an error but an impossibility: `install` declares neither the globs nor
--surfaces, so an install always delivers the whole product.

Selection filters PER OUTPUT, not per template: a glob matching one output of
a multi-output template renders exactly that one, and the template's other
outputs are left untouched on disk and reported as nothing at all.

A pattern matching zero outputs — any single "|"-segment, and therefore the
set — is a hard error naming the pattern and listing what the surface does
declare. A selection that silently selected nothing would report exactly like
a clean run. What was selected is stated in the run report, per surface:

    agents: 12 of 24 outputs selected by --agent-glob

Selection composes orthogonally with everything else: overlay anchors and tier
resolution, banners and tuning claims, and the write-safety table all apply to
the selected outputs exactly as they do to a full run.
"""

import fnmatch
import tomllib
from pathlib import Path

from .errors import InputError
from .paths import TEMPLATE_SUFFIX, TEMPLATES_DIR, rel

SURFACE_NAMES = ("agents", "commands")
COMMAND_SURFACE = "commands"
OUTPUTS_FENCE = "+++"
# Definition selection: the flag each surface is globbed with, and the
# separator joining several patterns into one flag value.
SURFACE_GLOB_FLAG = {"agents": "--agent-glob", "commands": "--command-glob"}
GLOB_SEPARATOR = "|"

# Surface -> the fnmatch patterns selecting that surface's outputs. A surface
# absent from the map is unfiltered, so None and {} both mean "everything".
GlobMap = dict[str, list[str]]


def surface_map(
    output_root: Path,
    *,
    templates_root: Path = TEMPLATES_DIR,
    surfaces: str = "both",
) -> dict[str, tuple[Path, Path]]:
    """Surface name -> (template source dir, output dir).

    A template's parent directory routes its output; a surface's template dir
    may be absent or empty. `output_root` is required and must already exist —
    this repository holds no rendered tree for it to default to — and its
    surface subdirectories are created at generation time as needed.
    `surfaces` filters to one surface, or "both".
    """
    if not output_root.is_dir():
        raise InputError(f"output root '{output_root}' is not an existing directory — every verb requires one")
    root = output_root
    names = SURFACE_NAMES if surfaces == "both" else (surfaces,)
    if not set(names) <= set(SURFACE_NAMES):
        raise InputError(f"unknown surface '{surfaces}'")
    return {name: (templates_root / name, root / name) for name in names}


def split_globs(spec: str) -> list[str]:
    """One --agent-glob/--command-glob value as its individual patterns."""
    return spec.split(GLOB_SEPARATOR)


def output_key(target: Path, surface_root: Path) -> str:
    """What a selection pattern matches: the output's path relative to its
    surface, without the .md suffix — go-coder, mad/participant-contract."""
    return target.relative_to(surface_root).with_suffix("").as_posix()


def selected(surface: str, key: str, globs: GlobMap | None) -> bool:
    """Does the selection cover this output? A surface with no patterns is
    covered entire. fnmatchcase, not fnmatch: matching must not depend on the
    host filesystem's case rules."""
    patterns = (globs or {}).get(surface)
    return patterns is None or any(fnmatch.fnmatchcase(key, pattern) for pattern in patterns)


def output_keys(smap: dict[str, tuple[Path, Path]]) -> dict[str, list[str]]:
    """Surface -> every output key its templates declare, sorted. The set a
    selection is validated and accounted against, without rendering anything."""
    keys: dict[str, list[str]] = {surface: [] for surface in smap}
    for surface, template, out_dir in template_targets(smap):
        surface_root = smap[surface][1]
        keys[surface].extend(output_key(out_dir / f"{name}.md", surface_root) for name in split_outputs(template)[0])
    return {surface: sorted(found) for surface, found in keys.items()}


def validate_selection(keys: dict[str, list[str]], globs: GlobMap) -> None:
    """A pattern matching no output is a hard error naming it and listing what
    its surface declares. Every "|"-segment is held to this individually, so a
    typo inside an alternation cannot hide behind a sibling that matches — and
    a selection that selected nothing can never report like a clean run."""
    for surface, patterns in globs.items():
        available = keys.get(surface, [])
        for pattern in patterns:
            if not any(fnmatch.fnmatchcase(key, pattern) for key in available):
                raise InputError(
                    f"{SURFACE_GLOB_FLAG[surface]} pattern '{pattern}' matches none of "
                    f"the {len(available)} {surface} output(s): " + (", ".join(available) or "(none)")
                )


def report_selection(keys: dict[str, list[str]], globs: GlobMap) -> None:
    """State what each globbed surface selected, out of what it declares."""
    print()
    for surface, patterns in sorted(globs.items()):
        available = keys.get(surface, [])
        chosen = sum(1 for key in available if selected(surface, key, globs))
        print(f"{surface}: {chosen} of {len(available)} outputs selected by {SURFACE_GLOB_FLAG[surface]}")


def read_fence(path: Path) -> tuple[dict | None, str]:
    """A template's opening `+++` TOML fence, parsed, and the body below it.

    The fence is None for a template that opens without one, whose body is
    then the whole file. The one fence parser: surface templates read their
    [outputs.*] declarations through split_outputs, and the agents-file render
    reads its [[outputs._resolve]] entries (`agents_file` module docstring).
    """
    text = path.read_text(encoding="utf-8")
    if not text.startswith(OUTPUTS_FENCE + "\n"):
        return None, text
    closing = text.find(f"\n{OUTPUTS_FENCE}\n", len(OUTPUTS_FENCE))
    if closing == -1:
        raise InputError(f"{rel(path)}: unterminated {OUTPUTS_FENCE} outputs block")
    return tomllib.loads(text[len(OUTPUTS_FENCE) + 1 : closing]), text[closing + len(OUTPUTS_FENCE) + 2 :]


def split_outputs(path: Path) -> tuple[dict[str, dict[str, str]], str]:
    """Split a template into its output declarations and its body.

    A template may open with a fenced TOML block declaring the definitions it
    renders and the parameters that differ between them:

        +++
        [outputs.mad-participant-opus]
        model = "opus"
        +++
        ---
        name: @!arg.name!@
        model: @!arg.model!@
        ...

    The fence BINDS, so its keys are bare; the body READS them as
    @!arg.<key>!@, plus @!arg.name!@ bound to the output's own name. A template
    with no block renders one definition named
    after the template. A declared output that is not a table — a fence
    metakey such as `_resolve`, which only the agents-file render reads — is
    refused.
    """
    fence, body = read_fence(path)
    if fence is None:
        stem = path.name[: -len(TEMPLATE_SUFFIX)]
        return {stem: {"name": stem}}, body
    declared = fence.get("outputs", {})
    if not declared:
        raise InputError(f"{rel(path)}: outputs block declares no [outputs.*]")
    for name, params in declared.items():
        if not isinstance(params, dict):
            raise InputError(
                f"{rel(path)}: outputs.{name} is not a table — a surface template declares [outputs.<name>] tables only"
            )
    outputs = {name: {"name": name, **params} for name, params in declared.items()}
    return outputs, body


def template_targets(
    smap: dict[str, tuple[Path, Path]],
    globs: GlobMap | None = None,
) -> list[tuple[str, Path, Path]]:
    """(surface name, template path, output directory) for every template.

    Discovery recurses through each surface's template tree (an absent tree is
    tolerated), and a template's relative subpath is mirrored into its surface:
    templates/agents/mad/participant-contract.tmpl.md has output directory
    agents/mad/. Placement is declared by the filesystem and nothing else.

    `globs` drops a template none of whose declared outputs are selected; a
    partially selected one stays, and its unselected outputs are filtered out
    per output where they are rendered.
    """
    found: list[tuple[str, Path, Path]] = []
    for name, (template_dir, out_dir) in smap.items():
        if not template_dir.is_dir():
            continue
        for template in template_dir.rglob(f"*{TEMPLATE_SUFFIX}"):
            subpath = template.parent.relative_to(template_dir)
            mirrored = out_dir / subpath
            if globs and not any(
                selected(name, output_key(mirrored / f"{output}.md", out_dir), globs)
                for output in split_outputs(template)[0]
            ):
                continue
            found.append((name, template, mirrored))
    return sorted(found, key=lambda target: rel(target[1]))


def templates(smap: dict[str, tuple[Path, Path]]) -> list[Path]:
    """Every template in every surface's template tree, discovered recursively."""
    return [template for _, template, _ in template_targets(smap)]
