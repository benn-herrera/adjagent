"""gen_defs — one template → its rendered outputs."""

import re
from collections.abc import Callable, Mapping
from functools import cache
from pathlib import Path

from .banners import banner, frontmatter_of, sha256_text
from .chunks import ChunkSource
from .discovery import COMMAND_SURFACE, GlobMap, output_key, selected, split_outputs, template_targets
from .errors import InputError
from .frontmatter import (
    DISPATCH_FIELDS,
    NAME_FIELD,
    TOOLS_FIELD,
    AuthoredField,
    AuthoredLine,
    EntrySlots,
    FrontmatterRules,
    assemble,
    field_plan,
    split_authored,
    tool_slots,
)
from .markers import (
    CHUNK_ROUTE,
    DYNAMIC_NAMESPACE,
    FAMILY_NAMESPACE,
    HARNESS_NAMESPACE,
    DynamicMap,
    Expansion,
    Routes,
    TableSource,
    Verbatim,
    assert_no_residual_markers,
    expand,
)
from .model_tuning import (
    TIER_SENTINEL,
    TIER_TOKEN_PREFIX,
    TIERS,
    FamilySource,
    OverlayMap,
    OverlaySource,
    TierBinding,
    Tuning,
    as_resolver,
)
from .paths import rel

# An output's own model pin, read out of its RENDERED frontmatter: the value
# of a `model:` key, however it got there — an outputs-table parameter or a
# literal line. Quotes are optional in YAML and stripped here.
FRONTMATTER_PIN = re.compile(r"""^model:[ \t]*["']?([^"'\s#]+)["']?[ \t]*$""", re.MULTILINE)


def frontmatter_pin(text: str) -> str | None:
    """The output's own model pin: the `model:` value in its rendered
    frontmatter, or None when it declares none (the generated commands and the
    participant contract, today). Read from the rendered text because a pin may
    arrive as an outputs-table parameter rather than a literal line."""
    front = frontmatter_of(text)
    if front is None:
        return None
    match = FRONTMATTER_PIN.search(front)
    return match.group(1) if match else None


def output_tier(probe_text: str) -> str | None:
    """The output's own tier, read out of a DISCOVERY render's frontmatter pin.

    Three readings, and only the first is a tier: the sentinel the probe
    binding put there; a literal pin, which comes back as itself and declares
    no tier; and no pin site at all. Both of the last two return None here, and
    they part at assert_tiered: an output with no pin site is a property of its
    type and renders, while a literal pin resolves no tier and is refused.
    """
    pin = frontmatter_pin(probe_text)
    if pin is None or not pin.startswith(TIER_SENTINEL):
        return None
    tier = pin[len(TIER_SENTINEL) :]
    return tier if tier in TIERS else None


def routing_table(
    chunks: dict[str, dict],
    dynamic: Mapping[str, str | Verbatim],
    overlays: OverlayMap | None,
    harness: DynamicMap | None = None,
) -> Routes:
    """A render's routes: bare markers to the chunk table, `dyn` to
    `dynamic`, `fam` to `overlays`, and `hrn` to `harness` when one is loaded."""
    routes: dict = {
        CHUNK_ROUTE: ChunkSource(chunks),
        DYNAMIC_NAMESPACE: TableSource(dynamic, DYNAMIC_NAMESPACE, "invocation parameter"),
        FAMILY_NAMESPACE: FamilySource(overlays),
    }
    if harness is not None:
        routes[HARNESS_NAMESPACE] = TableSource(harness, HARNESS_NAMESPACE, "harness key")
    return routes


def render_output(
    body: str,
    binding: TierBinding,
    params: dict[str, str],
    resolve: Callable[[str | None], OverlayMap | None],
) -> tuple[str, str | None]:
    """Render one declared output; return (text, the tier it declared).
    The text of _expand_output's expansion."""
    name = params["name"]
    expansion, tier, _ = _expand_output(
        body, binding, params, resolve, frontmatter=binding.frontmatter, output=name, where=f"output '{name}'"
    )
    return expansion.text, tier


def _expand_output(
    body: str,
    binding: TierBinding,
    params: dict[str, str],
    resolve: Callable[[str | None], OverlayMap | None],
    *,
    frontmatter: FrontmatterRules | None,
    output: str,
    where: str,
) -> tuple[Expansion, str | None, str | None]:
    """Expand one declared output; return (its expansion, the tier it
    declared, the pin its authored frontmatter spells).

    Two passes, both over the raw body. Pass A renders under `binding.probe`,
    whose tier tokens carry a marker-free sentinel, so reading the pin out of
    that render's frontmatter yields the output's own tier — an outputs-table
    `model` parameter and a literal frontmatter line are the same thing here,
    exactly as they are to frontmatter_pin. Pass B renders under `binding.real`
    and the overlay set the tier resolves.

    Pass B is UNCONDITIONAL. Skipping it when the overlay set is unchanged — the
    optimization this replaced — would ship pass A's sentinel text into a
    system prompt wherever a tier token sits in a body or chunk. Pass A's
    output is never written, never hashed, and never returned — only the pin
    it reads, which is the authored spelling whatever the harness renders.

    Pass A renders the authored frontmatter as written. Under `frontmatter`,
    pass B renders it through the harness's entries (`frontmatter` module
    docstring) instead, so a harness that elides or rewrites `model` can cost
    an output neither its tier nor assert_tiered's view of a literal pin.
    """
    probe = expand(body, routing_table(binding.chunks, binding.probe, resolve(None), binding.harness), args=params)
    tier = output_tier(probe.text)
    overlays = resolve(tier)
    split = None if frontmatter is None else split_authored(body, where=where)
    if split is None:
        real = expand(body, routing_table(binding.chunks, binding.real, overlays, binding.harness), args=params)
    else:
        authored, rest = split
        real = _expand_frontmatter_output(
            authored, rest, binding, params, overlays, frontmatter=frontmatter, output=output, where=where
        )
    return real, tier, frontmatter_pin(probe.text)


def _expand_frontmatter_output(
    authored: list[AuthoredLine],
    rest: str,
    binding: TierBinding,
    params: dict[str, str],
    overlays: OverlayMap | None,
    *,
    frontmatter: FrontmatterRules,
    output: str,
    where: str,
) -> Expansion:
    """Pass B of an output whose authored frontmatter renders through its
    harness's entries: each emitted entry's text expanded under pass B's routes
    with the five entry slots joined to the invocation parameters, then the
    rest of the body as usual. An authored `name` must render the output's own
    name, which is what lets a harness elide it."""
    routes = routing_table(binding.chunks, binding.real, overlays, binding.harness)
    fields = {line.key: line.value for line in authored if isinstance(line, AuthoredField)}

    def expanded_field(field: str) -> str | None:
        return expand(fields[field], routes, args=params).text if field in fields else None

    name = expanded_field(NAME_FIELD)
    if name is not None and name != output:
        raise InputError(f"{where}: authors name '{name}', which is not its output name '{output}'")
    tools = cache(lambda: tool_slots(expanded_field(TOOLS_FIELD), frontmatter, where=where))
    undispatchable = not set(fields) & set(DISPATCH_FIELDS)
    items: list[str | tuple[str, Expansion]] = []
    for item in field_plan(authored, frontmatter, where=where):
        if isinstance(item, str):
            items.append(item)
            continue
        field, entry = item
        slots = EntrySlots(
            binding.real,
            authored_value=fields.get(field, ""),
            output=output,
            undispatchable=undispatchable,
            tools=tools,
        )
        items.append(
            (field, expand(entry.text, routing_table(binding.chunks, slots, overlays, binding.harness), args=params))
        )
    return assemble(items, expand(rest, routes, args=params))


def assert_tiered(pin: str | None, tier: str | None, *, path: Path, name: str) -> None:
    """Refuse an output whose pin site resolved no tier; `pin` is the one its
    authored frontmatter spells, read from the discovery render.

    A pin site declares its tier with one of the five tier tokens, and every
    pin site does: the alternative — a literal pin — renders exactly the bytes
    the token would have, so it costs the definition its model scope and
    nothing else, which is a loss no diff of the output can show. Refusing here
    is what keeps that from being how a new template arrives.

    An output with NO pin site is untouched by this. It carries no `model:` key
    at all, which is a property of its type, not a failed resolution.
    """
    if tier is not None or pin is None:
        return
    tokens = ", ".join(f"@!{DYNAMIC_NAMESPACE}.{TIER_TOKEN_PREFIX}{seat}!@" for seat in TIERS)
    raise InputError(
        f"{rel(path)}: output '{name}' pins 'model: {pin}' literally, which "
        f"resolves no tier — declare the tier with one of {tokens}, whose "
        f"rendered text the tier map supplies"
    )


def render_template(
    path: Path,
    binding: TierBinding,
    out_dir: Path,
    *,
    surface: str,
    overlays: OverlaySource,
    tuning: Tuning,
) -> list[tuple[Path, str]]:
    """Render every definition a template declares, banner stamped into each.

    `out_dir` is the template's path mirrored into its surface (see
    template_targets); `surface` names that surface. The banner always lands in
    frontmatter: agent templates must open with a frontmatter block; command
    templates may open with one (banner injected identically) or with bare
    prompt text (a minimal banner-only frontmatter block is emitted above it).
    The banner is stamped last, since it carries the hash of what follows it.

    This is where an output's pin site is held to declaring a tier
    (assert_tiered) and where a rendered body is held to carrying no leftover
    marker syntax (assert_no_residual_markers), because this is the first
    point that knows both the render and the name of the output it came from.
    """
    outputs, body = split_outputs(path)
    resolve = as_resolver(overlays)
    rendered = []
    for name, params in sorted(outputs.items()):
        expansion, tier, pin = _expand_output(
            body,
            binding,
            params,
            resolve,
            frontmatter=None if surface == COMMAND_SURFACE else binding.frontmatter,
            output=name,
            where=f"{rel(path)}: output '{name}'",
        )
        text = expansion.text
        assert_tiered(pin, tier, path=path, name=name)
        assert_no_residual_markers(expansion, path=path, name=name)
        if text.startswith("---\n"):
            # YAML comments: valid frontmatter, dropped by every parser, and
            # outside the body that becomes the prompt.
            rest = text[4:]
        elif surface == COMMAND_SURFACE:
            rest = "---\n" + text
        else:
            raise InputError(f"{rel(path)}: agent template must open with YAML frontmatter")
        stamp = banner(path, body_hash=sha256_text(rest), tuning=tuning, seat=tier)
        rendered.append((out_dir / f"{name}.md", "---\n" + stamp + "\n" + rest))
    return rendered


def all_renders(
    binding: TierBinding,
    smap: dict[str, tuple[Path, Path]],
    *,
    overlays: OverlaySource,
    globs: GlobMap | None = None,
    tuning: Tuning,
) -> list[tuple[Path, str]]:
    """Every (target, rendered text) pair across every template, sorted — the
    ones `globs` selects, when a selection is in force.

    `tuning` is required rather than defaulted: every render runs under a
    triple, so a None one has no reading — it would reach banner() as a
    provenance claim with nothing to claim.
    """
    pairs = []
    for surface, template, out_dir in template_targets(smap, globs):
        surface_root = smap[surface][1]
        pairs.extend(
            pair
            for pair in render_template(template, binding, out_dir, surface=surface, overlays=overlays, tuning=tuning)
            if selected(surface, output_key(pair[0], surface_root), globs)
        )
    return sorted(pairs, key=lambda pair: rel(pair[0]))
