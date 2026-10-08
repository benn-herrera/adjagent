"""`Render`, the one parameter a section receives, and the two map flags that
build it. Composes no text and does no I/O."""

from collections.abc import Mapping
from dataclasses import dataclass

from adjagent.errors import InputError
from adjagent.family import Family
from adjagent.harness import Harness
from adjagent.loading import load
from adjagent.vocabulary import TIERS, Anchor, Tier

TierMap = Mapping[Tier, str]
MAP_ALL = "all"
INHERIT_MODEL = "inherit"
TIER_MAP_FLAG = "--model-tier-map"
ALIAS_MAP_FLAG = "--model-pin-tier-alias-map"


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
    """The one parameter a section receives: harness, family, the invocation's two maps, and the seat
    of the definition being rendered."""

    harness: Harness
    family: Family
    tier_map: TierMap  # effective tier -> member; total
    alias_map: TierMap | None = None  # tier -> alias; total when set
    seat: Tier | None = None  # the rendered definition's tier; render_definition binds it

    def __post_init__(self) -> None:
        """Refuse a non-total map, or a family member override no tier reaches (family tiers ∪ tier_map)."""
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

    def model(self, tier: Tier) -> str:
        """The tier's rendered model text: alias if the alias map is set, else member; "inherit" ->
        harness.inherit_text."""
        text = (self.tier_map if self.alias_map is None else self.alias_map)[tier]
        return self.harness.inherit_text if text == INHERIT_MODEL else text

    def overlay(self, anchor: Anchor) -> str:
        """The anchor's text: tier_map[seat]'s member override, else family-wide text, else "" (seat None:
        family-wide only)."""
        overlay = self.family.overlays.get(anchor)
        if overlay is None:
            return ""
        if self.seat is not None and self.tier_map[self.seat] in overlay.members:
            return overlay.members[self.tier_map[self.seat]]
        return overlay.text or ""

    @property
    def stock(self) -> tuple[Tier, ...]:
        """Tiers, in TIERS order, whose tier_map member has no member override anywhere in the family."""
        tuned = {member for overlay in self.family.overlays.values() for member in overlay.members}
        return tuple(tier for tier in TIERS if self.tier_map[tier] not in tuned)


def build_render(*, harness: str, family: str, tier_spec: str | None, alias_spec: str | None) -> Render:
    """The CLI's Render. Unknown harness/family names are refused, listing the names there are (a
    path-shaped --family included). Then every tier's model text is checked against
    harness.model_pattern, refusing with tier, value, supplier and model_shape."""
    harnesses = load("adjagent.harnesses", "HARNESS")
    if harness not in harnesses:
        raise InputError(f"unknown harness '{harness}' — harnesses are {', '.join(harnesses)}")
    families = load("adjagent.families", "FAMILY")
    if family not in families:
        raise InputError(f"--family '{family}' names no family — families are {', '.join(families)}")
    loaded = families[family]
    tier_map = dict(loaded.tiers) if tier_spec is None else parse_tier_map(tier_spec, flag=TIER_MAP_FLAG)
    alias_map = None if alias_spec is None else parse_tier_map(alias_spec, flag=ALIAS_MAP_FLAG)
    render = Render(harness=harnesses[harness], family=loaded, tier_map=tier_map, alias_map=alias_map)
    if alias_map is not None:
        supplier = ALIAS_MAP_FLAG
    elif tier_spec is not None:
        supplier = TIER_MAP_FLAG
    else:
        supplier = f"the family '{family}' tiers (--family)"
    for tier, text in (tier_map if alias_map is None else alias_map).items():
        if render.harness.model_pattern.fullmatch(text) is None:
            raise InputError(
                f"harness '{harness}' does not accept model '{text}' at tier {tier}, supplied by {supplier} — "
                f"a model for this harness is {render.harness.model_shape}"
            )
    return render
