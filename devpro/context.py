"""`Render`, the one parameter a render receives, the plugin and the two map flags that
build it. Composes no text and does no I/O."""

from __future__ import annotations

import functools
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from devpro.definitions import discover
from devpro.errors import InputError
from devpro.family import Family
from devpro.harness import Harness
from devpro.loading import load
from devpro.plugin import Plugin
from devpro.vocabulary import TIERS, Anchor, Tier

TierMap = Mapping[Tier, str]
MAP_ALL = "all"
INHERIT_MODEL = "inherit"
TIER_MAP_FLAG = "--model-tier-map"
ALIAS_MAP_FLAG = "--model-pin-tier-alias-map"
DEFAULT_HARNESS = "claude"
DEFAULT_FAMILY = "claude"
DEFAULT_PLUGIN = "devpro"
STEP_DOWN_TIER: Tier = "medium"


def parse_tier_map(spec: str, *, flag: str) -> dict[Tier, str]:
    """One map flag's value as a total map in TIERS order: `t=v` for every tier, or `all=v` plus named
    exceptions in any order.

    There is no per-tier fallback to the family or to anything else. `all=V` names all five wherever
    it sits in the string and each named tier applies after it, so `all=haiku,high=opus` and
    `high=opus,all=haiku` both mean haiku everywhere but high. Values are not validated here: the
    harness's shape check runs on the rendered text (`build_render`).
    """
    named: dict[str, str] = {}
    for pair in spec.split(","):
        entry = pair.strip()
        key, sep, value = entry.partition("=")
        key, value = key.strip(), value.strip()
        if not sep or not key or not value or "=" in value:
            raise InputError(f"{flag}: '{entry}' is not a tier=value pair")
        if any(part.split() != [part] for part in (key, value)):
            raise InputError(f"{flag}: '{entry}' contains whitespace inside a tier or a value")
        if key != MAP_ALL and key not in TIERS:
            raise InputError(f"{flag}: '{entry}' names no tier — tiers are {', '.join(TIERS)}, or all.")
        if key in named:
            raise InputError(f"{flag}: duplicate key '{key}' — a map is 1:1.")
        named[key] = value
    merged = dict.fromkeys(TIERS, named[MAP_ALL]) if MAP_ALL in named else {}
    merged.update({tier: value for tier, value in named.items() if tier != MAP_ALL})
    missing = [tier for tier in TIERS if tier not in merged]
    if missing:
        raise InputError(
            f"{flag}: names no value for {', '.join(missing)} — a map names every tier "
            f"({flag}={','.join(f'{tier}=<value>' for tier in TIERS)}) or all of them at once "
            f"({flag}={MAP_ALL}=<value>)"
        )
    return {tier: merged[tier] for tier in TIERS}


def map_spec(mapping: TierMap) -> str:
    """`highest=…,high=…,medium=…,low=…,lowest=…`, always TIERS order."""
    return ",".join(f"{tier}={mapping[tier]}" for tier in TIERS)


@dataclass(frozen=True)
class Render:
    """The one parameter a render receives: harness, plugin, family, the invocation's two maps, and the
    tier of the definition being rendered. `harness` is the harness as given; `bound_harness` is it
    bound to the plugin, for every value a `{plugin}` template fills."""

    harness: Harness
    plugin: Plugin
    family: Family
    tier_map: TierMap  # effective tier -> member; total
    alias_map: TierMap | None = None  # tier -> alias; total when set
    tier: Tier | None = None  # render_definition binds it
    scope: str = ""  # the agents file's scope name; render_agents_file binds it

    def __post_init__(self) -> None:
        """Refuse a non-total map, or a family member override no tier reaches (family tiers ∪
        tier_map)."""
        for mapping in (self.tier_map, self.alias_map):
            if mapping is not None and set(mapping) != set(TIERS):
                raise InputError(f"a tier map must name exactly {', '.join(TIERS)}")
        reachable = set(self.family.tiers.values()) | set(self.tier_map.values())
        declared = {member for overlay in self.family.overlays.values() for member in overlay.members}
        unreachable = sorted(declared - reachable)
        if unreachable:
            raise InputError(
                f"family '{self.family.name}' overrides member(s) no tier reaches: {', '.join(unreachable)} — "
                f"reachable members are {', '.join(sorted(reachable))}"
            )

    @functools.cached_property
    def bound_harness(self) -> Harness:
        """The harness bound to this render's plugin (`Harness.bound`)."""
        return self.harness.bound(self.plugin.name)

    def ships(self, name: str) -> bool:
        """Whether this render ships the definition `name`: in the plugin, and not one the harness omits."""
        return self.plugin.ships(name) and name not in self.harness.omits

    def model(self, tier: Tier) -> str:
        """The tier's rendered model text: alias if the alias map is set, else member; "inherit" and the
        harness's inherit synonyms render harness.inherit_text."""
        text = (self.tier_map if self.alias_map is None else self.alias_map)[tier]
        if text == INHERIT_MODEL or text in self.harness.inherit_synonyms:
            return self.harness.inherit_text
        return text

    def overlay(self, anchor: Anchor) -> str:
        """The anchor's text: tier_map[tier]'s member override, else family-wide text, else "" (tier None:
        family-wide only)."""
        overlay = self.family.overlays.get(anchor)
        if overlay is None:
            return ""
        if self.tier is not None and self.tier_map[self.tier] in overlay.members:
            return overlay.members[self.tier_map[self.tier]]
        return overlay.text or ""

    @property
    def step_down_model(self) -> str:
        """The STEP_DOWN_TIER's rendered model, or "" where that tier renders the harness's inherit text
        and so pins nothing to step down to."""
        model = self.model(STEP_DOWN_TIER)
        return "" if model == self.harness.inherit_text else model

    @property
    def stock(self) -> tuple[Tier, ...]:
        """Tiers, in TIERS order, whose tier_map member has no member override anywhere in the family."""
        tuned = {member for overlay in self.family.overlays.values() for member in overlay.members}
        return tuple(tier for tier in TIERS if self.tier_map[tier] not in tuned)


def harnesses() -> dict[str, Harness]:
    """Every harness this installation knows, by name, in name order."""
    return cast(dict[str, Harness], load("devpro.harnesses", "HARNESS"))


def harness_named(name: str) -> Harness:
    """The harness `name` loads as; an unknown name is refused, listing the names there are."""
    known = harnesses()
    if name not in known:
        raise InputError(f"unknown harness '{name}' — harnesses are {', '.join(known)}")
    return known[name]


def plugins() -> dict[str, Plugin]:
    """Every plugin this installation knows, by name, in name order."""
    return cast(dict[str, Plugin], load("devpro.plugins", "PLUGIN"))


def plugin_named(name: str) -> Plugin:
    """The plugin `name` loads as. An unknown name is refused, listing the names there are, and so is any
    plugin stating a definition name discovery does not find, naming the plugin and the names: a misspelt
    member would otherwise drop out of its plugin unnoticed."""
    known = plugins()
    discovered = {defn.name for _, entries in discover() for defn in entries}
    for plugin in known.values():
        undiscovered = sorted(plugin.named - discovered)
        if undiscovered:
            raise InputError(f"plugin '{plugin.name}' names no discovered definition: {', '.join(undiscovered)}")
    if name not in known:
        raise InputError(f"unknown plugin '{name}' — plugins are {', '.join(known)}")
    return known[name]


def _bare_tier_spec_expanded(harness: Harness, spec: str) -> str:
    """`spec`, or `all=<spec>` where the harness reads a bare value as the whole map — a non-empty value
    holding neither `=` nor `,`, so `default` but not `default,high=omlx/X`."""
    if not harness.bare_tier_spec_is_all or "=" in spec or "," in spec or not spec.strip():
        return spec
    return f"{MAP_ALL}={spec}"


def build_render(*, harness: str, plugin: str, family: str, tier_spec: str | None, alias_spec: str | None) -> Render:
    """The CLI's Render. Unknown harness/plugin/family names are refused,
    listing the names there are (a path-shaped --family included), and so is a plugin naming an
    undiscovered definition (`plugin_named`). A tier spec that names no tier becomes all=<spec> where the
    harness reads a bare value as the whole map. Then every tier's model text is checked against
    harness.model_pattern, refusing with tier, value, supplier and model_shape. With no tier spec given,
    the harness's `default_tier_spec` stands in for one."""
    loaded_harness = harness_named(harness)
    loaded_plugin = plugin_named(plugin)
    families = load("devpro.families", "FAMILY")
    if family not in families:
        raise InputError(f"--family '{family}' names no family — families are {', '.join(families)}")
    loaded = families[family]
    spec = loaded_harness.default_tier_spec if tier_spec is None else tier_spec
    if spec is None:
        tier_map = dict(loaded.tiers)
    else:
        tier_map = parse_tier_map(_bare_tier_spec_expanded(loaded_harness, spec), flag=TIER_MAP_FLAG)
    alias_map = None if alias_spec is None else parse_tier_map(alias_spec, flag=ALIAS_MAP_FLAG)
    render = Render(harness=loaded_harness, plugin=loaded_plugin, family=loaded, tier_map=tier_map, alias_map=alias_map)
    if alias_map is not None:
        supplier = ALIAS_MAP_FLAG
    elif tier_spec is not None:
        supplier = TIER_MAP_FLAG
    elif spec is not None:
        supplier = f"the harness '{harness}' default tier spec"
    else:
        supplier = f"the family '{family}' tiers (--family)"
    for tier, text in (tier_map if alias_map is None else alias_map).items():
        if render.harness.model_pattern.fullmatch(text) is None:
            raise InputError(
                f"harness '{harness}' does not accept model '{text}' at tier {tier}, supplied by {supplier} — "
                f"a model for this harness is {render.harness.model_shape}"
            )
    return render
