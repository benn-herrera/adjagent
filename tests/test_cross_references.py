"""Definition text names another definition only through a reference hole, so each harness renders
every reference with its own prefix. The guard reads the text a render starts from — every body,
description and skill supporting file, the agents file, and every family overlay — rather than
`rendered/`, a gitignored product that may be absent or stale.

A spelling counts as a reference when it is:
- a hyphenated definition name as a whole word, not inside a path or a longer name;
- any other definition name in backticks, except the three that are also an executable, a tool or
  a CLI (`adjagent`, `docdicer`, `kbase`);
- one of those three in backticks followed by ` skill`.

Role nouns ("hand that to the architect") and those three names as their programs ("Every other
`adjagent` command") are prose, and stay bare.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable
from typing import cast

import pytest

from adjagent.definitions import discover
from adjagent.family import Family
from adjagent.loading import load
from adjagent.render import PLACEHOLDER
from adjagent.vocabulary import reference

_PROGRAM_NAMES = frozenset({"adjagent", "docdicer", "kbase"})


def _reference_spellings(names: Collection[str]) -> re.Pattern[str]:
    """The spellings of a reference to any of `names` outside a hole, per this module's rule."""
    hyphenated = sorted((name for name in names if "-" in name), key=len, reverse=True)
    single = sorted(name for name in names if "-" not in name and name not in _PROGRAM_NAMES)
    programs = sorted(name for name in names if name in _PROGRAM_NAMES)
    alternation = lambda chosen: "|".join(map(re.escape, chosen))
    return re.compile(
        rf"(?<![a-z0-9_/.-])(?:{alternation(hyphenated)})(?![a-z0-9_-])"
        rf"|`(?:{alternation(single)})`"
        rf"|`(?:{alternation(programs)})` skill\b"
    )


def unheld_references(texts: Iterable[tuple[str, str]], *, names: Collection[str]) -> list[str]:
    """`<where>: <spelling>` for each reference to one of `names` that a text spells outside a hole."""
    spellings = _reference_spellings(names)
    return [f"{where}: {match[0]}" for where, text in texts for match in spellings.finditer(PLACEHOLDER.sub("", text))]


def _definition_texts() -> list[tuple[str, str]]:
    texts = []
    for _, entries in discover():
        for defn in entries:
            texts.append((f"{defn.name} body", defn.body))
            if defn.description is not None:
                texts.append((f"{defn.name} description", defn.description))
            texts += [(f"{defn.name} {file.path}", file.body) for file in defn.files]
    return texts


def _overlay_texts() -> list[tuple[str, str]]:
    families = cast(dict[str, Family], load("adjagent.families", "FAMILY"))
    texts = []
    for family_name, family in families.items():
        for anchor, overlay in family.overlays.items():
            where = f"family {family_name} overlay {anchor.value}"
            if overlay.text is not None:
                texts.append((where, overlay.text))
            texts += [(f"{where} member {member}", text) for member, text in overlay.members.items()]
    return texts


_NAMES = frozenset(defn.name for _, entries in discover() for defn in entries)


def test_no_definition_text_names_a_definition_outside_a_hole() -> None:
    texts = [*_definition_texts(), *_overlay_texts()]
    assert len(texts) > len(_NAMES)
    found = unheld_references(texts, names=_NAMES)
    assert found == [], "\n".join(found)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Prefer over python-coder for any Python task.", ["python-coder"]),
        ("revision by `architect`.", ["`architect`"]),
        ("diced (the `docdicer` skill), and", ["`docdicer` skill"]),
        ("load the `development` skill.", ["`development`"]),
        (f"Prefer over {reference('python-coder')} for any Python task.", []),
        (f"load the `{reference('development')}` skill.", []),
        ("hand that to the architect to integrate", []),
        ("Every other `adjagent` command runs as installed", []),
        ("Run `kbase` itself", []),
        ("the file agents/python-coder.md", []),
        ("a python-coders seat", []),
    ],
)
def test_the_guard_reads_exactly_the_reference_spellings(text: str, expected: list[str]) -> None:
    assert unheld_references([("t", text)], names=_NAMES) == [f"t: {spelling}" for spelling in expected]
