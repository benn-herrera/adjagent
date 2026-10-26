"""The retired metadata forms appear nowhere in the `kbase` skill.

kbase consolidated its metadata form: a KB's nodes and edges are the server's own records, and the
register pages, `strength` and the build-status band are rendered from them. Forms of an earlier
layout — a document's frontmatter, an in-body strength annotation, a leaf-level key — describe a KB
this toolchain no longer produces, and a skill that names one sends a session looking for a file or
a field that is not there.

A sweep run once while making that change is evidence for it; it is not a guard for the skill. This
file is the guard: it re-runs the sweep on every test run, so a reference that re-acquires an old
spelling is caught here rather than by the session that follows it.

It reads the skill's composed bodies — the router's and each supporting file's — from
`adjagent.definitions.discover()`, never `rendered/`: the definition package is what a render is a
function of, and `rendered/` is a gitignored build product that may be absent or stale.
"""

import re

from adjagent.definitions import discover

#: The retired forms, each with what a session would go looking for if it read one. Spelled here
#: rather than imported: these strings no longer exist in the skill to import, which is the whole
#: property being asserted.
RETIRED_FORMS: tuple[tuple[str, str], ...] = (
    ("frontmatter", "no document carries one; the records hold what it held"),
    ("set-frontmatter", "no such tool is offered"),
    ("no-claim", "a leaf has no claims field to restate"),
    ("(strength", "in-body strength annotations are retired; strength renders in the register"),
    ("subtree-claims", "a frontmatter key of a form the current KB does not carry"),
    ("subtree-experiments", "a frontmatter key of a form the current KB does not carry"),
)

#: Matched on both sides so `frontmatter` does not answer for `frontmattered` and `set-frontmatter`
#: is reported under its own name, and a token opening with `(` is still its own. Each token is
#: reported once per body it is found in.
_PATTERNS = {token: re.compile(rf"(?<![\w-]){re.escape(token)}(?![\w-])") for token, _ in RETIRED_FORMS}

#: The skill whose bodies the sweep covers.
SKILL_NAME = "kbase"


def _bodies() -> dict[str, str]:
    """Each body the skill ships, keyed by the path a session reads it at."""
    [skill] = [definition for _, found in discover() for definition in found if definition.name == SKILL_NAME]
    return {"SKILL.md": skill.body} | {file.path: file.body for file in skill.files}


def scan(bodies: dict[str, str]) -> list[str]:
    """``<path>: <token>`` for every retired form found in one of ``bodies``.

    ``bodies`` is a parameter rather than the skill itself so the teeth check below can aim this
    same scanner at planted text: a guard exercised only against the surface it already passes on
    is a guard exercised against nothing.
    """
    return [
        f"{path}: {token}"
        for path, body in bodies.items()
        for token, pattern in _PATTERNS.items()
        if pattern.search(body)
    ]


def test_no_file_of_the_kbase_skill_carries_a_retired_form() -> None:
    """The standing assertion: every body the skill ships describes the current metadata form."""
    assert scan(_bodies()) == []


def test_the_retired_form_guard_has_teeth() -> None:
    """A planted form in each spelling is caught, one finding per body and token."""
    planted = {
        f"planted-{number}.md": f"A sentence naming {token} here.\n" for number, (token, _) in enumerate(RETIRED_FORMS)
    }

    findings = scan(planted)

    assert sorted(finding.rsplit(": ", 1)[1] for finding in findings) == sorted(token for token, _ in RETIRED_FORMS)


def test_a_longer_word_is_not_matched_by_a_retired_token() -> None:
    """The boundaries are load-bearing: `frontmattered` carries `frontmatter` and is not it."""
    assert scan({"prose.md": "A frontmattered document, and subtree-claiming prose.\n"}) == []
