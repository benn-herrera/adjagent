"""
Tier tokens and the two maps:

A definition declares its capability TIER at its pin site, as one of five
markers in the `dyn.` namespace — the invocation's own parameters:

    model: @!dyn.tier-highest!@ | @!dyn.tier-high!@ | @!dyn.tier-medium!@ |
           @!dyn.tier-low!@     | @!dyn.tier-lowest!@

They are bound at load time to `pin_map[<tier>]`, in a dynamic table that
reaches every span through the routing table, so they expand wherever a marker
does — template bodies, chunk bodies, variants, defaults, and overlay text
alike. A pin is operator-suppliable text (--model-pin-map), so it is bound
verbatim: spliced in as itself and never expanded. Nothing is
reserved against the chunk table for them: a [chunks.tier-low] table is an
ordinary chunk, reachable as the bare @!tier-low!@, because the namespace is
what separates the two.

Two independent maps, each TOTAL over the five tiers on every render:

    tier map   tier -> FAMILY MEMBER. Declared by the family file's required
               [tiers] table; --model-tier-map masks the tiers it names. It
               selects whose [family.*.models.<member>] overrides a definition
               is tuned against, and never reaches rendered text.
    pin map    tier -> RENDERED PIN TEXT, always a claude-legal model name.
               Defaults to DEFAULT_PIN_MAP below; --model-pin-map masks the
               tiers it names. It is the SOLE source of the @!dyn.tier-*!@
               tokens.

The two are independent on purpose: what a definition is TUNED for and what it
DISPATCHES on are separately chosen, so their divergence is disclosed rather
than prevented. A tier-map value is NOT validated against the family's overlay
tables — naming a member the family declares no override for is the legal
STOCK state below, never an error. A pin-map value is not validated at all:
nothing in this repository owns the set of legal claude aliases, so the report
echo and the banner are the whole safety story there. That is an accepted risk,
stated so it does not get "fixed" into a gate.

Merge semantics, identical for both flags: start from the defaults; `all=V`
overwrites all five; then each named tier is applied. So `all=haiku,high=opus`
is haiku everywhere but high, whichever order the two appear in, and a named
tier masks ONLY itself — unnamed tiers keep their default. A key that is
neither one of the five tiers nor `all`, a duplicate key, and a malformed pair
are each hard errors. Both merged maps are total by construction: a tier
holding no member, or no pin, is unrepresentable rather than an error branch.

Per-output tier discovery renders a template's body TWICE. The first pass binds
the tier tokens to a marker-free sentinel (`tier:high`), so reading the pin out
of that render's frontmatter yields the output's own tier; the second renders
for real, under the overlay set that tier resolves. The second pass is
UNCONDITIONAL — a tier token in a body or a chunk would otherwise ship sentinel
text into a system prompt. An output with no pin site at all (the participant
contract, the generated commands) declares no tier and takes family-wide
overlay text only.

A pin site that resolves NO tier — a literal `model: opus` where a token
belongs — is a hard error naming the output and its pin. It is the one failure
the render path cannot afford to tolerate quietly: a literal pin renders the
same bytes as the token that replaced it and silently loses the definition's
model scope, so a template landing with one would be tuned against nothing and
nothing would say so.

Model tuning — overlay anchors and family files:

    @!fam.<key>!@

is a marker usable in template bodies and chunk bodies: text layered over base
text, present or absent depending on which source file is loaded. `fam` is an
prefix naming the source that fills the anchor — FamilySource below, over a
family file's [family.<key>] tables, routed to every span through the routing
table. An unfilled anchor is that source's rule: it returns "". A marker
whose namespace is not registered is a hard error wherever it is read: an
anchor no loaded source fills renders as NOTHING by design, so a typo'd
namespace has no other way to announce itself.

With a loaded family file carrying no entry for an anchor, it expands to
nothing at all — a base render is byte-identical whether or not the anchor
exists. A family file (templates/family/<family>.toml) declares its tier map
and fills `fam.*` anchors:

    [tiers]
    highest = "fable"                     # all five tiers, or the file does
    high    = "opus"                      # not load — see below
    medium  = "sonnet"
    low     = "haiku"
    lowest  = "haiku"

    [family.<key>]
    text = "..."                          # fills fam.<key> family-wide

    [family.<key>.models.<member>]
    text = "..."                          # overrides the family text for that
                                          # family member

The table's key IS the anchor key: [family.gap-aversion] fills
@!fam.gap-aversion!@. The table name stays `family` — it is where the text is
AUTHORED, and SPEC.md names it — while `fam` is the namespace a template
CONSUMES it through.

Resolution, not accumulation: AT MOST ONE overlay renders per anchor — the
model scope wins over the family scope.

Family selection — what one --family NAME means:

    1. path-shaped   — contains a path separator or ends in .toml: taken as a
                       path to a family file, unresolved and unvalidated here
                       (load_family owns the existence error).
    2. family name   — <NAME>.toml under templates/family/.

Anything else is an error listing the available families. A bare MODEL name is
not a family name, and there is no third resolution step behind it.

The [tiers] table is REQUIRED and TOTAL. A family file that omits it, drops a
tier, or names a key outside the five fails to LOAD rather than falling back to
a partial map, to another family's members, or to the pin map: there is no
fallback anywhere in this resolution, and the default FAMILY is a selection,
not a fallback value. A family file may still carry zero [family.*] tables — a
family name is reservable before an observed failure motivates an entry — but
it needs its five-line [tiers] table to do so.

Two render states, plus one config error:

    Tuned    the tier's member has [family.<key>.models.<member>] tables: model
             scope wins over family-wide scope, per anchor. Named once per run,
             in the run's one notice about member scope.
    Stock    the tier's member has ZERO such tables anywhere in the family.
             Legal and unreported — silence is the stock state — and recorded
             in the banner's `stock=` field. A member with a table for one
             anchor and not another is NOT stock — that anchor simply falls
             back to family-wide text.
    (error)  [tiers] absent, incomplete, or carrying an unknown key.

A member named by a [family.*.models.<member>] table that no tier reaches — in
neither the family's own [tiers] nor the effective tier map — is a hard error:
the table could never render, which is exactly the class
validate_family_anchors already rejects for anchor names. Checking the UNION is
what lets a table be authored for a member reachable only via
--model-tier-map without failing a default run.

Family scope is unchanged by any of that: a loaded family file's family-wide
text fills its anchors render-wide, for outputs with a tier and outputs with no
pin site alike. Only MODEL-scoped entries require a tier. The banner records
the invocation's whole triple and its harness, and a render is a deterministic
function of those and the templates, so a re-render under them reproduces the
same bytes exactly.

A filled anchor renders its family text VERBATIM in place — no lead-in, no
wrapper, no marker of its own around it, so a family file can restore a passage
of contract prose as readily as it can add a corrective note; an author wanting
a lead-in writes one into their text. Neither the family nor the member name
appears in rendered output — the family file is the provenance record. The
filled text is itself marker-expanded, so a typo'd chunk reference inside it
fails loudly. A family-file entry naming an anchor that exists in no template
or chunk is a hard error, and a family declaring anchors reports which of them
were filled and from which scope (family vs model). NO name is reserved
anywhere in this: the namespace is what separates an anchor from a chunk, so
`overlay` and `tier-low` are ordinary chunk names now.

Structural invariant: a family file can never replace, suppress, or modify
BASE text — it can only fill anchors that base templates and chunks
deliberately expose. Anchors are authored on demand, when an observed failure
motivates one; they are never pre-sprinkled speculatively. See
templates/family/README.md and README.md ("Variants and platform
compatibility") for the provenance discipline.
"""

import re
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from .errors import InputError
from .markers import FAMILY_NAMESPACE, IDENTIFIER, DynamicMap, Verbatim
from .paths import FAMILY_DIR, FAMILY_SUFFIX, rel

# A family file's anchor key, held to the same class as the marker half that
# consumes it: [family.<key>] fills @!fam.<key>!@.
ANCHOR_KEY = re.compile(IDENTIFIER)

# The five capability tiers, in canonical order — the order every serialization
# of either map uses, so a banner claim is deterministic and reads
# highest-to-lowest rather than alphabetically.
TIERS = ("highest", "high", "medium", "low", "lowest")
DEFAULT_FAMILY = "claude"
# The harness a surface render resolves @!hrn.<key>!@ from when none is named.
DEFAULT_HARNESS = "claude"
# The family file's two top-level tables — its overlay entries and its tier
# table — and the literal a map flag spells "every tier". [family.<key>] is the
# authoring spelling; fam.<key> is the marker that consumes it.
FAMILY_TABLE = "family"
TIERS_TABLE = "tiers"
MAP_ALL = "all"
# The five dynamic names a tier token is spelled with: @!dyn.tier-<tier>!@.
# A chunk named tier-anything is unaffected — the namespace is what separates
# them, so nothing here is reserved against the chunk table.
TIER_TOKEN_PREFIX = "tier-"
# What the discovery pass binds the tier tokens to. Marker-free and
# whitespace-free, so FRONTMATTER_PIN reads `model: tier:high` unchanged.
TIER_SENTINEL = "tier:"
# Tier -> rendered pin text. This default lives here and is changed only by
# --model-pin-map; no family owns it, and it is always claude-legal names.
# Deliberately NOT injective — low and lowest both ship haiku — which is why a
# definition's own tier is recorded in its banner rather than derived.
DEFAULT_PIN_MAP = {"highest": "fable", "high": "opus", "medium": "sonnet", "low": "haiku", "lowest": "haiku"}
# Tier -> family member, or tier -> rendered pin text. Total over TIERS in
# every instance the render path ever sees (see effective_map).
TierMap = dict[str, str]
# Marker spelling (fam.<key>) -> (overlay text, the scope it resolved from:
# "family"/"model").
OverlayMap = dict[str, tuple[str, str]]
# What the render path accepts for `overlays`: a per-tier resolver (tier ->
# map), or a plain map applied render-wide, or nothing at all.
OverlaySource = OverlayMap | Callable[[str | None], OverlayMap | None] | None


class TierBinding(NamedTuple):
    """The tables one render needs, built from ONE load_chunks().

    `chunks` is what a bare marker resolves from. `real` and `probe` are the
    two dynamic tables the @!dyn.…!@ namespace resolves from, differing in
    exactly the five tier entries: `real` binds them to the effective pin map's
    text — what ships — and `probe` to a marker-free sentinel the discovery
    pass reads an output's own tier back out of. `harness` is the loaded
    harness file @!hrn.…!@ resolves from, or None for a render that routes no
    `hrn`. Threaded as one parameter so no call site can pair a stale table
    with a fresh one.
    """

    chunks: dict[str, dict]
    real: DynamicMap
    probe: DynamicMap
    harness: DynamicMap | None = None


def tier_binding(chunks: dict[str, dict], *, pin_map: TierMap, harness: DynamicMap | None = None) -> TierBinding:
    """Bind the five tier tokens as dynamic parameters, twice over.

    A dynamic table rather than the chunk table or an argument: the tokens are
    the invocation's parameters, not shared text and not arguments anything
    bound at a call site, and the table reaches every span through the routing
    table — so a token expands in template bodies, chunk bodies, variants,
    defaults, and overlay text alike. A real pin is Verbatim, being operator
    text; the probe sentinel is authored.
    """
    return TierBinding(
        chunks=chunks,
        real={f"{TIER_TOKEN_PREFIX}{tier}": Verbatim(pin_map[tier]) for tier in TIERS},
        probe={f"{TIER_TOKEN_PREFIX}{tier}": f"{TIER_SENTINEL}{tier}" for tier in TIERS},
        harness=harness,
    )


class Family(NamedTuple):
    """A loaded family file: its overlay entries, and the tier map it declares.

    `entries` is keyed by the MARKER SPELLING its table fills — fam.<key>, for
    a [family.<key>] table — so it compares directly against the anchors
    templates and chunks author, and a second overlay source's entries key
    into the same map without collision.
    """

    entries: dict[str, dict]
    tiers: TierMap


def load_family(path: Path) -> Family:
    """Load and validate a model-family file.

    Schema: a required [tiers] table naming the member that staffs each of the
    five tiers, plus [family.<key>] tables, each with a family-wide `text`
    and/or [family.<key>.models.<member>] per-member override tables carrying
    `text`. The table's key is the anchor it fills: [family.<key>] fills
    @!fam.<key>!@. A family file only fills anchors — it has no vocabulary for
    replacing, suppressing, or modifying base text.

    [tiers] is required and TOTAL. A missing table, a missing tier, or a key
    outside the five is a hard error rather than a fallback to a partial map,
    to another family's members, or to the pin map: there is no fallback
    anywhere in this resolution. A family may still declare zero [family.*]
    tables — a name is reservable before an observed failure motivates an entry
    — but it needs its five-line [tiers] table to do so.
    """
    if not path.is_file():
        raise InputError(f"model-family file '{path}' does not exist")
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise InputError(f"{rel(path)}: invalid TOML — {exc}") from exc
    stray = set(data) - {FAMILY_TABLE, TIERS_TABLE}
    if stray:
        raise InputError(
            f"{rel(path)}: unknown top-level table(s) {sorted(stray)} — a "
            f"family file holds only [{TIERS_TABLE}] and [{FAMILY_TABLE}.<key>] tables"
        )
    tiers = load_tiers(data, path)
    entries: dict[str, dict] = {}
    for key, entry in data.get(FAMILY_TABLE, {}).items():
        anchor = f"{FAMILY_NAMESPACE}.{key}"
        where = f"{rel(path)}: [{FAMILY_TABLE}.{key}]"
        if ANCHOR_KEY.fullmatch(key) is None:
            raise InputError(f"{where}: '{key}' is not an anchor key — it must match {IDENTIFIER}")
        if not isinstance(entry, dict) or set(entry) - {"text", "models"}:
            raise InputError(f"{where}: only 'text' and 'models' allowed")
        if "text" in entry:
            if not isinstance(entry["text"], str):
                raise InputError(f"{where}: text must be a string")
            entry["text"] = entry["text"].strip("\n")
        models = entry.get("models", {})
        for model, override in models.items():
            mwhere = f"{where}.models.{model}"
            if not isinstance(override, dict) or set(override) != {"text"} or not isinstance(override["text"], str):
                raise InputError(f'{mwhere}: exactly one key, text = "..."')
            override["text"] = override["text"].strip("\n")
        if "text" not in entry and not models:
            raise InputError(f"{where}: fills nothing (no text, no models)")
        entries[anchor] = entry
    return Family(entries=entries, tiers=tiers)


def load_tiers(data: dict, path: Path) -> TierMap:
    """Validate and return a family file's required [tiers] table."""
    where = f"{rel(path)}: [{TIERS_TABLE}]"
    listed = ", ".join(TIERS)
    if TIERS_TABLE not in data:
        raise InputError(
            f"{rel(path)}: no [{TIERS_TABLE}] table — every family file names "
            f"the member staffing each of {listed}. There is no fallback: an "
            f"incomplete family file does not load."
        )
    tiers = data[TIERS_TABLE]
    if not isinstance(tiers, dict) or set(tiers) != set(TIERS):
        raise InputError(
            f"{where}: keys must be exactly {listed} — found "
            + (", ".join(sorted(tiers)) if isinstance(tiers, dict) and tiers else "(none)")
        )
    for tier, member in tiers.items():
        if not isinstance(member, str) or member.split() != [member]:
            raise InputError(f"{where}: {tier} must be a non-empty member name with no whitespace")
    # Duplicate members across tiers are legal: two tiers staffed by one member
    # is a statement about that family's ladder, not a defect.
    return {tier: tiers[tier] for tier in TIERS}


def resolve_family(name: str, family_dir: Path = FAMILY_DIR) -> Path:
    """Resolve --family NAME to a family file.

    Two steps, and no third: path-shaped (a separator, or a .toml suffix) is
    taken as given, and load_family owns the existence error; otherwise
    <NAME>.toml under `family_dir`. A bare MODEL name is not a family name —
    the tier map names members now, so there is nothing for a model SPEC to
    have meant.
    """
    if "/" in name or "\\" in name or name.endswith(FAMILY_SUFFIX):
        return Path(name)
    family = family_dir / f"{name}{FAMILY_SUFFIX}"
    if family.is_file():
        return family
    available = ", ".join(sorted(path.stem for path in family_dir.glob(f"*{FAMILY_SUFFIX}"))) or "(none)"
    raise InputError(
        f"--family '{name}' names no family file: no {rel(family)}. Bare "
        f"model names are not family names — pass a family (available: "
        f"{available}) or a family-file path."
    )


def validate_family_anchors(entries: dict[str, dict], known: set[str]) -> None:
    """A family-file entry naming an anchor no template or chunk authors is a
    hard error — the file would silently fill nothing."""
    unknown = sorted(set(entries) - known)
    if unknown:
        raise InputError("family file names anchor(s) that exist in no template or chunk: " + ", ".join(unknown))


def validate_family_members(family: Family, tier_map: TierMap, path: Path) -> None:
    """A member no tier reaches is a hard error — the mirror of
    validate_family_anchors, for the other half of an overlay table's address.

    With [tiers] values and [family.*.models.<member>] keys as two independent
    strings, a mis-spelled member never fires and its tier reports as an
    ordinary Stock one: an entry that can never render, silently. Reachability
    is judged against the UNION of the family's own [tiers] and the EFFECTIVE
    tier map, so a table authored for a member reachable only through
    --model-tier-map does not fail a default run.
    """
    reachable = set(family.tiers.values()) | set(tier_map.values())
    declared = {member for entry in family.entries.values() for member in entry.get("models", {})}
    unreachable = sorted(declared - reachable)
    if unreachable:
        raise InputError(
            f"{rel(path)}: [{FAMILY_TABLE}.*.models.*] names member(s) no tier reaches: "
            + ", ".join(unreachable)
            + " — reachable members are "
            + ", ".join(sorted(reachable))
            + ". Such a table can never render; fix the spelling, or map a tier to it."
        )


def model_scope(entries: dict[str, dict], member: str) -> OverlayMap:
    """Only the model-scope overlays `member` matches in `entries`.

    The per-tier half of resolution, on its own: a tier pulls the family file's
    override for its own member and nothing else — never the file's family-wide
    text, which family_scope owns.
    """
    return {
        anchor: (entry["models"][member]["text"], "model")
        for anchor, entry in entries.items()
        if member in entry.get("models", {})
    }


def family_scope(entries: dict[str, dict]) -> OverlayMap:
    """Only the family-wide overlays in `entries` — what a loaded family fills
    render-wide, for outputs with a tier and outputs with no pin site alike."""
    return {anchor: (entry["text"], "family") for anchor, entry in entries.items() if "text" in entry}


def stock_tiers(entries: dict[str, dict], tier_map: TierMap) -> tuple[str, ...]:
    """The tiers whose mapped member declares ZERO [family.*.models.<member>]
    tables anywhere in the family — the legal Stock state.

    Zero, not "some anchors missing": a member with a table for one anchor and
    not another is per-anchor fallback to family-wide text, which
    resolve_overlays already handles, and is not stock.
    """
    declared = {member for entry in entries.values() for member in entry.get("models", {})}
    return tuple(tier for tier in TIERS if tier_map[tier] not in declared)


def resolve_overlays(entries: dict[str, dict], member: str | None) -> OverlayMap:
    """Resolve a loaded family file to anchor -> (text, scope).

    Resolution, not accumulation: at most one overlay per anchor, the model
    scope ("model") winning over the family scope ("family"). An entry with
    only member overrides, none matching, resolves to nothing.
    """
    return {**family_scope(entries), **(model_scope(entries, member) if member is not None else {})}


@dataclass(frozen=True)
class FamilySource:
    """The `fam` source over one output's resolved overlays: an anchor's
    text, or "" for an anchor no overlay fills (None fills none)."""

    overlays: OverlayMap | None

    def __call__(self, key: str) -> str:
        entry = (self.overlays or {}).get(f"{FAMILY_NAMESPACE}.{key}")
        return "" if entry is None else entry[0]


def tier_resolver(entries: dict[str, dict], tier_map: TierMap) -> Callable[[str | None], OverlayMap]:
    """Build the per-output resolver: the output's own TIER -> its overlays.

    The tier map is total, so there is no missing-member branch to write. A
    tier of None means the output has no pin site — a property of its type, not
    a failed resolution — and takes family-wide text only: only MODEL-scoped
    entries require a tier.
    """

    def resolve(tier: str | None) -> OverlayMap:
        return resolve_overlays(entries, None if tier is None else tier_map[tier])

    return resolve


def as_resolver(overlays: OverlaySource) -> Callable[[str | None], OverlayMap | None]:
    """Normalize a render call's `overlays` argument to a per-tier resolver.

    A resolver passes through; a plain map (or None) is render-wide — every
    output resolves to it, tiered or not.
    """
    return overlays if callable(overlays) else lambda tier: overlays


@dataclass(frozen=True)
class Tuning:
    """The effective (family, tier map, pin map) triple one render runs under,
    and the harness whose values fill its @!hrn.<key>!@ markers.

    Both maps are post-merge and total. `stock` is derived from the family and
    the tier map together (stock_tiers) and `is_default` says the whole triple
    is the default one, under the default harness — claude with neither map
    changed BY VALUE, so `--family claude` and a no-op override are the default
    triple too. Only
    `is_default` is provenance rather than substance, and it exists for one
    caller: an install's summary line, where a default render is the non-event
    report-by-exception is built around.
    """

    family: Path
    tier_map: TierMap
    pin_map: TierMap
    harness: str = DEFAULT_HARNESS
    stock: tuple[str, ...] = ()
    is_default: bool = False


def effective_map(defaults: TierMap, spec: str | None, *, flag: str) -> TierMap:
    """Merge one map flag's `tier=value` pairs over `defaults`.

    Positional-independent: `all=V` overwrites all five wherever it sits in the
    string, and each named tier is applied after it — so `all=haiku,high=opus`
    and `high=opus,all=haiku` both mean haiku everywhere but high. A named tier
    masks ONLY itself; unnamed tiers keep their default, which is what makes a
    partial override partial. Defaults are total and a merge only overwrites,
    so the result is total too.

    Values are not validated here, by design: a tier-map value naming a member
    the family declares no override for is the legal Stock state, and nothing
    in this repository owns the set of legal claude aliases a pin-map value is
    drawn from (see the module docstring — accepted risk, not an oversight).
    """
    if spec is None:
        return dict(defaults)
    named: TierMap = {}
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
    merged = {tier: named[MAP_ALL] for tier in TIERS} if MAP_ALL in named else dict(defaults)
    merged.update({tier: value for tier, value in named.items() if tier != MAP_ALL})
    return merged


def effective_tuning(
    path: Path,
    family: Family,
    *,
    tier_spec: str | None = None,
    pin_spec: str | None = None,
    harness: str = DEFAULT_HARNESS,
    family_dir: Path = FAMILY_DIR,
) -> Tuning:
    """Build the run's triple from the loaded family and the two map flags,
    under `harness`."""
    tier_map = effective_map(family.tiers, tier_spec, flag="--model-tier-map")
    pin_map = effective_map(DEFAULT_PIN_MAP, pin_spec, flag="--model-pin-map")
    default_family = family_dir / f"{DEFAULT_FAMILY}{FAMILY_SUFFIX}"
    return Tuning(
        family=path,
        tier_map=tier_map,
        pin_map=pin_map,
        harness=harness,
        stock=stock_tiers(family.entries, tier_map),
        is_default=(
            path.resolve() == default_family.resolve()
            and tier_map == family.tiers
            and pin_map == DEFAULT_PIN_MAP
            and harness == DEFAULT_HARNESS
        ),
    )


def map_spec(mapping: TierMap) -> str:
    """A map as the banner records it: TIERS order, never sorted — deterministic
    by construction, and readable highest-to-lowest."""
    return ",".join(f"{tier}={mapping[tier]}" for tier in TIERS)


def report_overlays(entries: dict[str, dict], overlays: OverlayMap, tuning: Tuning) -> None:
    """State which anchors the family file filled, and from which scope, for an
    output with no tier — the family-wide resolution every output starts from.
    Prints nothing for a family declaring no anchors, which is every default
    run today."""
    if not entries:
        return
    print()
    print(f"overlay anchors from {rel(tuning.family)}")
    print("=" * 60)
    for anchor in sorted(entries):
        scope = overlays[anchor][1] if anchor in overlays else "unfilled (no scope matched)"
        print(f"  {anchor:<28} {scope}")


def report_tuning(tuning: Tuning) -> None:
    """The run's triple and harness, echoed once in generate and install alike.

    A DISPLAY serialization, deliberately not the banner's: the banner is a
    machine claim, read back field for field and stable across versions, while
    this brackets each map for a human scanning a terminal and is free to
    change. One shared serializer would couple a display choice to a parsed
    contract — every banner in the tree reading differently for an added space.
    """
    print(
        f"tuning: family={rel(tuning.family)} "
        f"tier[{map_spec(tuning.tier_map)}] pin[{map_spec(tuning.pin_map)}] harness={tuning.harness}"
    )


def report_divergence(tuning: Tuning, *, family_dir: Path = FAMILY_DIR) -> None:
    """Notice — never a gate, never an exit status — when the two maps disagree
    within the claude family.

    Gated on the effective family file BEING claude.toml, however it was
    reached. For any other family the two maps diverge at every tier by
    construction — the tier map holds family members and the pin map holds
    claude aliases — so the notice would fire five times a run carrying no
    information. Within claude the namespaces coincide, so a divergence is a
    deliberate act worth naming: tuning against one member's overrides while
    shipping another's capacity is the isolation this feature exists to allow.
    """
    if tuning.family.resolve() != (family_dir / f"{DEFAULT_FAMILY}{FAMILY_SUFFIX}").resolve():
        return
    diverging = [tier for tier in TIERS if tuning.tier_map[tier] != tuning.pin_map[tier]]
    if not diverging:
        return
    where = ", ".join(f"{tier} (tier={tuning.tier_map[tier]}, pin={tuning.pin_map[tier]})" for tier in diverging)
    print(f"notice: tier map and pin map diverge at {where} — tuning/capacity isolation, not an error")


def report_tuned(tuning: Tuning) -> None:
    """Notice — one summary line, never per-tier, never an error — naming the
    tiers whose mapped member the family declares overrides for, and the member
    each one resolved to.

    Silence is the stock render: no mapped member carries a
    [family.*.models.<member>] table, which is every run of both shipped families
    today. The set is the complement of `tuning.stock` rather than a second
    walk of the family entries, so this line and the banner's `stock=` field
    answer out of one computation and cannot drift apart.
    """
    tuned = [tier for tier in TIERS if tier not in tuning.stock]
    if not tuned:
        return
    where = ", ".join(f"{tier} ({tuning.tier_map[tier]})" for tier in tuned)
    print(f"notice: member-scoped tuning is in force at {where} — {rel(tuning.family)} fills their anchors")
