"""The agent-facing write-op contract, held to its load-bearing tokens.

The kb-maintainer definition's own text states the contract for the seat that writes metadata,
read by a seat that may have no brief at all. This module asserts a token vocabulary of it, so
editing that text into silence about a fact a seat acts on mid-call fails the suite rather than
shipping.

Tokens, not sentences: the assertions have to survive a rewording of the text. What they may not
survive is a definition that has stopped carrying the fact.
"""

import pytest

from adjagent.render import definitions

#: What the definition must carry, and what each token is load-bearing *for*. Every
#: one of these is a fact a seat acts on mid-call, which is why a definition that has
#: quietly lost one is a defect rather than a style drift.
CONTRACT_TOKENS: tuple[tuple[str, str], ...] = (
    # M11's transport. A seat that thinks values travel on the command line
    # writes a call the op refuses.
    ("values file", "values travel in a file the caller writes"),
    # M13's exit ladder. 7 and 8 are separated precisely so the caller branches
    # differently on them; a body naming one and not the other collapses that.
    ("**7**", "refused, nothing written — correct the field and call again"),
    ("**8**", "contended — the outcome a *correct* set of values can still get"),
    # The whole point of separating 8 from 7: re-run, do not re-author.
    ("identical", "the re-run is of the same call on the same file"),
    ("three times", "the retry bound, so a contended file is reported not looped"),
)


@pytest.mark.parametrize(("token", "carries"), CONTRACT_TOKENS, ids=[token for token, _ in CONTRACT_TOKENS])
def test_the_maintainer_definition_carries_the_contract(token: str, carries: str) -> None:
    [defn] = [defn for _, defn in definitions() if defn.name == "kb-maintainer"]
    assert token in defn.body, carries
