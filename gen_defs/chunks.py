"""
The chunk table (templates/shared-chunks.toml) and the chunk source — what a
bare marker resolves from.

    @!name!@                     expand chunk "name" — ALWAYS a chunk, and
                                 nothing else
    @!name variant="platform"!@  expand that variant of a multi-variant chunk
    @!name key="value"!@         bind @!arg.key!@ inside the chunk body
    @!name wrap="70"!@           greedy-wrap the expanded body to 70 columns

"variant" and "wrap" are reserved argument keys; any other key binds a value
the chunk body reads as @!arg.<key>!@, defaulting to [chunks.<name>.defaults]
when the marker omits it. Argument values cannot contain a double quote. Only
a bare marker takes arguments at all.

The chunk source returns a call as a `markers.Span`; the expander expands its
body with `arg` bound to the call's arguments, then applies the `wrap=` width.
An unknown chunk name and a bad variant are errors, so a typo fails loudly
rather than shipping into a system prompt.
"""

import functools
import tomllib
from dataclasses import dataclass

from .errors import InputError
from .markers import Span
from .paths import SHARED_CHUNKS


def load_chunks() -> dict[str, dict]:
    """Load shared-chunks.toml. Chunk bodies are stripped of edge newlines.

    No name is reserved here. A bare marker resolves from this table and from
    nothing else, so no other source has a name to collide with: the overlay
    marker and the five tier tokens carry namespaces of their own, and a chunk
    called `overlay` or `tier-high` is now an ordinary chunk.
    """
    data = tomllib.loads(SHARED_CHUNKS.read_text(encoding="utf-8"))
    chunks = data.get("chunks", {})
    if not chunks:
        raise InputError(f"no [chunks.*] tables in {SHARED_CHUNKS.name}")
    for name, chunk in chunks.items():
        if "text" in chunk:
            chunk["text"] = chunk["text"].strip("\n")
        for variant, text in chunk.get("variants", {}).items():
            chunk["variants"][variant] = text.strip("\n")
        if "text" not in chunk and "variants" not in chunk:
            raise InputError(f"chunk '{name}' has neither text nor variants")
        if "text" in chunk and "variants" in chunk:
            raise InputError(f"chunk '{name}' has both text and variants — a chunk is one or the other")
    return chunks


def wrap(text: str, width: int) -> str:
    """Greedy-wrap each paragraph of `text` to `width` columns on whitespace."""
    wrapped = []
    for paragraph in text.split("\n\n"):
        lines: list[str] = []
        current = ""
        for word in paragraph.split():
            if not current:
                current = word
            elif len(current) + 1 + len(word) <= width:
                current = f"{current} {word}"
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        wrapped.append("\n".join(lines))
    return "\n\n".join(wrapped)


def chunk_body(name: str, chunk: dict, args: dict[str, str]) -> str:
    variants = chunk.get("variants")
    if variants is None:
        if "variant" in args:
            raise InputError(f"chunk '{name}' takes no variant")
        return chunk["text"]
    variant = args.get("variant")
    if variant is None:
        raise InputError(f"chunk '{name}' requires variant= (one of {sorted(variants)})")
    if variant not in variants:
        raise InputError(f"chunk '{name}' has no variant '{variant}' (one of {sorted(variants)})")
    return variants[variant]


@dataclass(frozen=True)
class ChunkSource:
    """A chunk call -> its Span: the body, the arguments it binds (defaults
    overlaid by the call's own, minus the reserved keys), and the wrap."""

    chunks: dict[str, dict]

    def __call__(self, name: str, args: dict[str, str]) -> Span:
        chunk = self.chunks.get(name)
        if chunk is None:
            raise InputError(f"unknown chunk '{name}' — a bare marker names a chunk and nothing else")
        call = dict(args)
        width = call.pop("wrap", None)
        body = chunk_body(name, chunk, call)
        bound = {**chunk.get("defaults", {}), **call}
        bound.pop("variant", None)
        return Span(body, bound, functools.partial(wrap, width=int(width)) if width else None)
