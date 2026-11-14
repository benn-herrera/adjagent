"""The gemma-4 family."""

from devpro.family import Family, Overlay
from devpro.vocabulary import Anchor

FAMILY = Family(
    "gemma-4",
    {
        "highest": "gemma-4-31B-it",
        "high": "gemma-4-31B-it",
        "medium": "gemma-4-26B-A4B-it",
        "low": "gemma-4-12B-it",
        "lowest": "gemma-4-E4B-it",
    },
    overlays={
        # ask-vs-stipulate: observed behavior — silently filling axiom gaps with textbook
        # conventions; model — Gemma 4 31B-it, probe data 2026-04-29. The anchor renders as a
        # trailing note on the "Ask for what you need" bullet, so the text opens by extending that
        # ask; it stays authored in applied-mathematician.tmpl.md, the interactive seat, the only
        # one with a channel to ask on.
        Anchor.ASK_VS_STIPULATE: Overlay(
            text=r"""The ask above extends to functional forms and boundary conditions. Do not invent values, default forms, or boundary conditions to make a derivation close: ask for the missing piece, and where you cannot ask, the gap itself is what you deliver. A closure of your own is not a lesser evil for being labelled."""
        ),
    },
)
