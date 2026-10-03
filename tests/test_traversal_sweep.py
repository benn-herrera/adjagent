"""The traversal-obligation sweep's mechanism, against a fixture it owns.

Graph traversal sits off the inference side: coverage, tiling, containment, the
tree diff and reachability are the validator's, proved and logged. A sweep that
says no definition still *asks a seat* to perform one of those walks matches
every logical line — a paragraph or list item with its wrap undone, see
:func:`_logical_lines` — against :data:`PATTERNS`, the four traversal-obligation
shapes, and requires each hit to match exactly one judgment-site entry: a
``(definition, phrase)`` key whose value says why the site's object is a
*judgment* rather than a *resolution*. A hit with no entry is unclassified; a
hit matching two entries is ambiguous; an entry matching no hit is stale.

This file tests that mechanism and nothing else. Its corpus and its judgment
sites are inline fixtures, so no template's wording, name or existence is
something this test knows about.
"""

import re
from collections.abc import Iterator, Mapping

#: The four shapes. ``follow`` is matched only with ``links``
#: in reach — bare "follow" is ordinary English ("follow the canonical
#: direction") and matching it would drown the map in prose.
PATTERNS = {
    "trace": re.compile(r"\btrac(?:e|es|ed|ing)\b", re.IGNORECASE),
    "walk": re.compile(r"\bwalk(?:s|ed|ing)?\b", re.IGNORECASE),
    "follow-links": re.compile(r"\bfollow(?:s|ed|ing)?\b[^.!?]{0,80}\blinks?\b", re.IGNORECASE),
    "starting-from-any": re.compile(r"starting from any", re.IGNORECASE),
}

#: A line opening one of these starts a new logical line instead of continuing
#: the paragraph above it: list item, heading, table row, quote, fence.
_BLOCK_START = re.compile(r"(?:[-*+]\s|\d+[.)]\s|#|\||>|```)")


def _logical_lines(text: str) -> Iterator[tuple[int, str]]:
    """``(first line number, whitespace-normalized text)`` per paragraph, list item or block line.

    A wrapped paragraph or list item is one logical line, so a verb and the
    phrase that classifies it read the same at any wrap width. Sibling list
    items stay apart, and headings, table rows and fenced lines take no
    continuation, so no block lends its phrase to its neighbour.
    """
    start, words, accepts_continuation, in_fence = 0, [], False, False
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if accepts_continuation and stripped and not _BLOCK_START.match(stripped):
            words.extend(stripped.split())
            continue
        if words:
            yield start, " ".join(words)
        start, words = number, stripped.split()
        if stripped.startswith("```"):
            in_fence = not in_fence
        accepts_continuation = bool(stripped) and not in_fence and not stripped.startswith(("```", "#", "|"))
    if words:
        yield start, " ".join(words)


def _hits(definitions: tuple[tuple[str, str], ...]) -> Iterator[tuple[str, int, str, tuple[str, ...]]]:
    """``(definition, first line number, logical line, the patterns it matched)`` for every hit."""
    for name, text in definitions:
        for number, line in _logical_lines(text):
            matched = tuple(sorted(key for key, pattern in PATTERNS.items() if pattern.search(line)))
            if matched:
                yield name, number, line, matched


def _sweep_report(definitions: tuple[tuple[str, str], ...], sites: Mapping[tuple[str, str], str]) -> list[str]:
    """Every unclassified hit, ambiguous hit and stale entry, as report lines; empty means clean.

    An entry belongs to its own definition and its phrase is matched
    case-insensitively within the hit's logical line.
    """
    hits = list(_hits(definitions))
    report = []
    for name, number, line, keys in hits:
        phrases = [phrase for site, phrase in sites if site == name and phrase.lower() in line.lower()]
        if not phrases:
            report.append(f"unclassified {name}:{number} [{','.join(keys)}] {line}")
        elif len(phrases) > 1:
            report.append(f"ambiguous {name}:{number} matches {phrases}")
    for site, phrase in sites:
        if not any(name == site and phrase.lower() in line.lower() for name, _, line, _ in hits):
            report.append(f"stale {site}: {phrase!r}")
    return report


FIXTURE_DEFINITIONS = (
    (
        "seat-a.md",
        """\
# Seat A

When the user checks a derivation, trace the solidity of the
chain it rests on and name the weakest link.

Follow the canonical direction when naming ids.

- Preserve walk-back annotations verbatim.
- Walk every up-link in the tree and confirm each one
  resolves.

```
trace the solidity of the chain
walk the tree
```
""",
    ),
    (
        "seat-b.md",
        """\
Follow each index's child
links down to the leaves.

Starting from any leaf, trace the solidity of the chain.

Walk the proof and trace each step.
""",
    ),
)

FIXTURE_SITES = {
    ("seat-a.md", "trace the solidity of the chain"): "judged, and wrapped across two lines",
    ("seat-a.md", "walk-back annotations"): "a noun, not a traversal",
    ("seat-b.md", "walk the proof"): "one of two entries on one logical line",
    ("seat-b.md", "trace each step"): "the other of the two",
    ("seat-b.md", "walk the derivation backwards"): "no site carries this phrase",
}


def test_hits_start_at_the_first_line_of_their_logical_line() -> None:
    """Wrapped text is one hit at its first line; list items, fenced lines and bare "follow" are not merged in."""
    hits = [(name, number, keys) for name, number, _, keys in _hits(FIXTURE_DEFINITIONS)]

    assert hits == [
        ("seat-a.md", 3, ("trace",)),
        ("seat-a.md", 8, ("walk",)),
        ("seat-a.md", 9, ("walk",)),
        ("seat-a.md", 13, ("trace",)),
        ("seat-a.md", 14, ("walk",)),
        ("seat-b.md", 1, ("follow-links",)),
        ("seat-b.md", 4, ("starting-from-any", "trace")),
        ("seat-b.md", 6, ("trace", "walk")),
    ]
    assert {key for *_, keys in hits for key in keys} == PATTERNS.keys()


def test_the_report_names_every_unjudged_ambiguous_and_stale_site() -> None:
    """The classifier's teeth: an entry covers only its own definition, its own logical line, and one site."""
    assert _sweep_report(FIXTURE_DEFINITIONS, FIXTURE_SITES) == [
        "unclassified seat-a.md:9 [walk] - Walk every up-link in the tree and confirm each one resolves.",
        "unclassified seat-a.md:14 [walk] walk the tree",
        "unclassified seat-b.md:1 [follow-links] Follow each index's child links down to the leaves.",
        "unclassified seat-b.md:4 [starting-from-any,trace] Starting from any leaf, trace the solidity of the chain.",
        "ambiguous seat-b.md:6 matches ['walk the proof', 'trace each step']",
        "stale seat-b.md: 'walk the derivation backwards'",
    ]


def test_a_clean_corpus_reports_nothing() -> None:
    """A report that is never empty is equally consistent with a classifier that flags everything."""
    judged = (("seat-a.md", "Assist by tracing the solidity\nof the chain.\n"),)

    assert _sweep_report(judged, {("seat-a.md", "tracing the solidity of the chain"): "judged"}) == []
