"""The agent-facing write-op contract, held to its load-bearing tokens.

``templates/shared-chunks.toml``'s ``kb-metadata-write`` chunk states the
contract for the seats that write metadata — it is expanded into the distiller
and maintainer definitions, read by a seat that may have no brief at all. This
module asserts a token vocabulary of it, so editing the chunk into silence about
a fact a seat acts on mid-call fails the suite rather than shipping.

Tokens, not sentences: the assertions have to survive a rewording of the chunk.
What they may not survive is a chunk that has stopped carrying the fact.
"""

import tomllib
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SHARED_CHUNKS = _REPO_ROOT / "templates" / "shared-chunks.toml"
_CHUNK_NAME = "kb-metadata-write"

#: What the chunk must carry, and what each token is load-bearing *for*. Every
#: one of these is a fact a seat acts on mid-call, which is why a chunk that has
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


def _chunk_text() -> str:
    """The ``kb-metadata-write`` chunk body, as the generator resolves it."""
    data = tomllib.loads(_SHARED_CHUNKS.read_text(encoding="utf-8"))
    chunks = data["chunks"]
    assert _CHUNK_NAME in chunks, f"{_CHUNK_NAME} is gone from {_SHARED_CHUNKS.name}"
    return chunks[_CHUNK_NAME]["text"]


@pytest.mark.parametrize(("token", "carries"), CONTRACT_TOKENS, ids=[token for token, _ in CONTRACT_TOKENS])
def test_the_definition_chunk_carries_the_contract(token: str, carries: str) -> None:
    assert token in _chunk_text(), carries
