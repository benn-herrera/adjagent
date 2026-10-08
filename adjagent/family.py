"""Model families: the member staffing each tier, and the overlay text a family
fills at a definition's anchors. One `Family` instance per family, selected by
`--family NAME`; a family is a name, never a path.

Schema. `Family.tiers` names the member staffing each of the five tiers
(`definition.TIERS`). It is required and total: a family that omits a tier, or
names a key outside the five, fails at import rather than falling back to a
partial map or to another family's members. A family name is reservable before
any observed failure motivates tuning: an empty `overlays` is legal, but the
five tiers are what make the instance construct at all. Two tiers staffed by one
member is legal, a statement about that family's ladder rather than a defect.

`Family.overlays[Anchor.X]` is an `Overlay`: family-wide `text`, per-member
`members` overrides, or both. A definition exposes an anchor by asking
`Render.overlay(Anchor.X, tier=...)` for it. A member override must be
reachable, spelled as some tier reaches it in the family's own `tiers` or in an
effective `--model-tier-map`; an unreachable member is refused when the `Render`
is built, rather than kept as an override that quietly never fires.

The tier map is the model source. Tier to member comes from `Family.tiers`, or
whole from `--model-tier-map`; it decides which member's overrides a definition
is tuned against, and the `model:` text it renders. Tier to alias comes from
`--model-pin-tier-alias-map` only, with no default; where given, it is the
`model:` text each tier renders in place of its member, and tuning is
untouched. Every tier's rendered text is checked against the harness's model
pattern before anything is written.

Tuned and Stock. A tier whose member has member overrides in this family gets
member text, winning over family-wide text per anchor, and drops out of the
banner's `stock=` list. A tier whose member has zero overrides anywhere in the
family gets family-wide text only and is named in `stock=`. Stock is a legal
reported state, not a warning: it is where a family sits until probe data
motivates an override. A member holding an override for one anchor and not
another is not stock; that anchor falls back to family-wide text.

One overlay per anchor, most specific wins. At most one overlay renders per
anchor: the override for the member the definition's tier maps to, otherwise
the family-wide text, otherwise nothing. Family and member texts are never
concatenated. The text renders verbatim in place, with no lead-in and no
wrapper (any lead-in belongs in the text itself), and adds no family or member
name of its own, so this module is the provenance record.

Never touches base. A family can only fill anchors. It has no vocabulary for
replacing, suppressing or modifying a definition's base text, and an anchor the
family does not fill renders as nothing. Base text is tuned by editing the
definition or its sections, never from here.

Provenance discipline. Anchors are authored on demand, when an observed failure
motivates one, never pre-sprinkled speculatively: strip first, observe, patch.
Every overlay carries a comment recording the observed behavior it corrects,
against which model it was observed, and when; not what the text says, but why
it exists. Without that record a later maintainer cannot tell "still
load-bearing" from "residue from a model we no longer use".
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from adjagent.definition import IDENTIFIER, TIERS, Anchor, Tier
from adjagent.errors import InputError


@dataclass(frozen=True)
class Overlay:
    """Text filling one anchor: family-wide text, per-member overrides, or both."""

    text: str | None = None
    members: Mapping[str, str] = field(default_factory=dict)  # member name -> override text

    def __post_init__(self) -> None:
        """Refuse an overlay filling nothing, or any text with a leading/trailing newline."""
        if self.text is None and not self.members:
            raise InputError("an overlay fills nothing (no text, no members)")
        for text in (self.text, *self.members.values()):
            if text is not None and (not text or text.startswith("\n") or text.endswith("\n")):
                raise InputError("overlay text is empty or carries an edge newline")


@dataclass(frozen=True)
class Family:
    """A model family: the member staffing each tier, and its overlays keyed by anchor."""

    name: str  # "claude", "qwen3", "gemma-4"; the --family value
    tiers: Mapping[Tier, str]  # exactly TIERS, in TIERS order; no whitespace in a member
    overlays: Mapping[Anchor, Overlay] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Refuse a non-IDENTIFIER name, or tiers not exactly TIERS with whitespace-free members."""
        if re.fullmatch(IDENTIFIER, self.name) is None:
            raise InputError(f"family '{self.name}': name is not a strict-kebab identifier")
        if tuple(self.tiers) != TIERS:
            raise InputError(f"family '{self.name}': tiers must be exactly {', '.join(TIERS)}, in that order")
        for tier, member in self.tiers.items():
            if member.split() != [member]:
                raise InputError(f"family '{self.name}': {tier} must be a non-empty member name with no whitespace")


claude = Family(
    "claude",
    {"highest": "fable", "high": "opus", "medium": "sonnet", "low": "haiku", "lowest": "haiku"},
)
qwen3 = Family(
    "qwen3",
    {
        "highest": "Qwen3.8-Flash-Next",
        "high": "Qwen3.8-Flash-Next",
        "medium": "Qwen3.8-27B",
        "low": "Qwen3.6-35B-A3B",
        "lowest": "Qwen3.5-9B",
    },
)
gemma_4 = Family(
    "gemma-4",
    {
        "highest": "gemma-4-31B-it",
        "high": "gemma-4-31B-it",
        "medium": "gemma-4-26B-A4B-it",
        "low": "gemma-4-12B-it",
        "lowest": "gemma-4-E4B-it",
    },
    overlays={
        # gap-aversion: observed behavior — silently filling axiom gaps with textbook
        # conventions; model — Gemma 4 31B-it, probe data 2026-04-29. Prior delivery
        # vehicle: the whole-definition fork applied-mathematician-strict.md (created
        # f9866d2, tightened f9e2911, retired cabf3c9). The three bullets below were
        # that fork's proven prompt text carried over essentially verbatim; only the
        # packaging changed — the anchor renders this text verbatim in place, so the
        # one-line lead-in above the bullets is written into the text itself.
        #
        # 2026-09-06, no longer verbatim. This anchor is now authored in
        # kb-claim-scorer.tmpl.md and reaches that seat alone: this family staffs the KB
        # scoring wave, and applied-mathematician — the fork's original subject — is an
        # interactive seat nothing runs on gemma. So the text is written for a batch
        # grader, and two places where it addressed a collaborator are gone.
        #   · Step 3 read "Either request the missing piece from the user, or proceed by
        #     *stipulating* a specific closure with the closure labeled as a
        #     stipulation rather than a derivation." Base text now forbids closing a
        #     break with a supplied step, and an overlay fills rather than replaces, so a
        #     gemma render carried the permission and the prohibition at once. The
        #     grader has no user to ask and no channel a label could travel on.
        #   · The bullet's closing sentence promised "contingent answers the user can
        #     vet", which followed from step 3 and does not survive it.
        # What the 2026-04-29 probe validated included the escape valve; whether the
        # model holds a gap open without one is unprobed. Re-probe before trusting it
        # under load.
        #
        # Open question, deliberately not acted on: with base text corrected, bullet 2's
        # middle is close to a restatement of it (the derivation-chain and
        # operator/symbol bullets now both say a gap is not one whose conventional
        # reading you may supply). Bullets 1 and 3 are still additive — a pre-derivation
        # inventory pass, and the receipts rule, neither of which base states. Cutting
        # bullet 2 on that reading alone would be exactly the unprobed churn this file's
        # discipline forbids; the settling probe is a scoring wave run with and without
        # it against entries whose grades are known.
        Anchor.GAP_AVERSION: Overlay(
            text=r"""Three further disciplines apply:

- **Inventory functional forms before derivation.** Briefly check that the stated axioms specify the functional form, value, or evolution of every quantity the derivation needs. Quantities that appear in the axioms but whose form is not specified are gaps. Surface them before you settle a value (see Foundational gap discipline below for what to do once a gap is identified).

- **Foundational gap discipline.** Treat the stated postulate set as a *closed* specification. If a derivation requires information that is not in the stated axioms (a missing functional form, an unstated boundary condition, an unspecified spatial profile, an undefined coupling between named quantities), do **not** fill the gap with a default, a textbook convention, or a plausible interpolation. Instead:

  1. Identify the gap explicitly — by name and by location in the derivation chain.
  2. State what would be needed to close it (an additional axiom, a boundary condition, a functional form, etc.).
  3. Stop there. The gap stands as the material's own, and what you report is the gap and what would close it — never a closure you supplied, and never a result that reads as though the gap were not there.

  "It is conventional to assume X" is **not** a justification for filling a gap inside this postulate set. The framework may have deliberately omitted X, or may intend a different closure; you do not yet know which. The convention belongs to a different framework, not necessarily this one. Silent gap-filling produces confident-but-wrong readings that look correct because they agree with orthodoxy: a gap you close in your own head is a gap you then assess as though it had never been there.

- **Reproduction claims require receipts.** When a framework claims to reproduce, recover, or re-derive a known result — a value, phenomenon, equation, or observable from another framework — treat that claim as unproven unless the derivation chain is supplied with it or can be trivially produced from the stated axioms. Bare assertions of reproduction, without the chain, are *hypotheses*, not derivations. If your reasoning depends on a reproduction claim that lacks receipts, surface that fact: name the claim, name what would be needed to produce its receipt. The rule applies to claims about the framework's outputs, not to known values the framework borrows as inputs."""
        ),
        # ask-vs-stipulate: observed behavior — silently filling axiom gaps with
        # textbook conventions; model — Gemma 4 31B-it, probe data 2026-04-29. Prior
        # delivery vehicle: applied-mathematician-strict.md (created f9866d2,
        # tightened f9e2911, retired cabf3c9), which carried this as an in-place
        # expansion of the "Ask for what you need" bullet; the anchor renders it as a
        # trailing note on that bullet instead.
        #
        # 2026-09-06, two edits. Asking is this entry's whole subject, so it stays
        # authored in applied-mathematician.tmpl.md — the interactive seat is the only
        # one with a channel to ask on, and the scoring seat carries no ask bullet for
        # it to sit under.
        #   · "Asking is preferred over stipulating; stipulating with explicit labels is
        #     preferred over silent gap-filling" is struck. It ranked a labelled
        #     stipulation as an acceptable second-best; base text now forbids closing a
        #     gap with a supplied step however it is labelled, and an overlay fills rather
        #     than replaces.
        #   · "(see the foundational gap discipline above)" is struck: gap-aversion now
        #     renders only in kb-claim-scorer, so in this seat that pointer resolved to
        #     nothing.
        # STANDING QUESTION for whoever owns this file: nothing is run on gemma but the
        # KB scoring wave, and this entry fills an anchor only the interactive seat
        # authors — so it tunes a render that is not currently produced. Retiring it is
        # a live option and was not taken here; it needs the owner's call, not a
        # maintenance edit.
        Anchor.ASK_VS_STIPULATE: Overlay(
            text=r"""The ask above extends to functional forms and boundary conditions. Do not invent values, default forms, or boundary conditions to make a derivation close: ask for the missing piece, and where you cannot ask, the gap itself is what you deliver. A closure of your own is not a lesser evil for being labelled."""
        ),
    },
)
FAMILIES: Mapping[str, Family] = {f.name: f for f in (claude, qwen3, gemma_4)}
