"""The agent-facing write-op contract, held to its load-bearing tokens.

The kb-maintainer definition's own text states the contract for the seat that writes metadata, read
by a seat that may have no brief at all: every metadata write is one write-op tool call whose schema
is that op's closed set of value keys, an insert mints the id, and the outcome ladder decides what
the seat does next. That ladder is the write op's — `done`, `unchanged`, `refused`, `retry`,
`failed` — not the build's, whose `bounded` and `cancelled` no write op returns. This module asserts
a token vocabulary of it, so editing that text into silence about a fact a seat acts on mid-call
fails the suite rather than shipping.

The body under test is the definition's rendered text, clauses included: a token below that lives in
a shared clause the body interpolates (`adjagent/clauses.py`) is fixed there, not in the definition.

Tokens, not sentences: the assertions have to survive a rewording of the text. What they may not
survive is a definition that has stopped carrying the fact.
"""

import pytest

from adjagent.render import definitions

#: What the definition must carry, and what each token is load-bearing *for*. Every
#: one of these is a fact a seat acts on mid-call, which is why a definition that has
#: quietly lost one is a defect rather than a style drift.
CONTRACT_TOKENS: tuple[tuple[str, str], ...] = (
    # Composition. The call is the unit, not the document: a seat that batches two
    # entries into one call writes neither.
    ("entry per call", "one call carries one entry's values — a second entry is a second call"),
    ("closed set", "the op's schema is its closed set of value keys, which is what the seat supplies"),
    # Where an id comes from. A seat that expects to be told one, or picks one, stalls or invents.
    ("mints the id", "the insert mints the id and returns it — no separate step, no id to choose"),
    # The 0 class, whose least obvious member is a success rather than a partial write.
    ("unchanged", "0 covers done/unchanged, so a write that changed nothing is a success and the seat proceeds"),
    ("adopts", "an insert re-issued over an existing entry adopts it rather than minting a second"),
    # 1's facts: the write did not happen, the whole item list arrives in one refusal, and one
    # item's remedy is not the seat's to apply.
    ("wrote nothing", "a refusal wrote nothing — the correction is to the values, then call again"),
    ("offending", "every offending item is named at once, each with the remedy that clears it"),
    ("lock", "the lock item is a build running on the KB, which no change to the values clears — stop and report"),
    # 2 is the outcome a *correct* set of values can still get: re-run, do not re-author.
    ("identical", "the retry re-issues the same call unchanged — re-run, do not re-author"),
    ("three times", "the retry bound, so a contended KB is reported rather than looped on"),
    ("contended", "another writer holds the lock — an outcome a correct set of values can still get"),
    # 3, which is not a retry: re-issuing will not fix it.
    ("failed", "a defect in the tool, its input or the environment — re-issuing will not fix it"),
)


@pytest.mark.parametrize(("token", "carries"), CONTRACT_TOKENS, ids=[token for token, _ in CONTRACT_TOKENS])
def test_the_maintainer_definition_carries_the_contract(token: str, carries: str) -> None:
    [defn] = [defn for _, defn in definitions() if defn.name == "kb-maintainer"]
    assert token in defn.body, carries
