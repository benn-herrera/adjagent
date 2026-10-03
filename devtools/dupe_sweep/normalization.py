"""dupe_sweep — text as the comparison reads it: lower-cased words, markers and fenced code dropped.

Every text becomes its lower-cased alphanumeric words — case, punctuation,
markup and where the text wrapped all vanish — each remembering its source line.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

from .clustering import Unit

_MARKER = re.compile(r"@![^!]*!@")
_WORD = re.compile(r"[a-z0-9]+")


def prose_tokens(text: str) -> tuple[str, ...]:
    """Lowercased alphanumeric words, chunk markers dropped and every other
    character a separator. Code-span contents are kept: two sentences differing
    only in the identifier they name are still one idea."""
    return tuple(_WORD.findall(_MARKER.sub(" ", text).lower()))


def ellipsis(text: str, width: int = 150) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= width else flat[: width - 1] + "…"


@dataclass(frozen=True)
class ProseText:
    """One prose body as the overlap detector reads it: its words, and each word's line."""

    path: str
    label: str
    words: tuple[str, ...]
    lines: tuple[int, ...]

    def unit(self, start: int, end: int) -> Unit:
        """The words `start` up to `end` as a reportable span, sited at its first word's line."""
        words = self.words[start:end]
        return Unit(self.path, self.lines[start], self.label, " ".join(words), words)


def prose_text(path: str, label: str, body: str, *, line_of: Callable[[int], int]) -> ProseText:
    """`body`'s words outside fenced code blocks, each sited by `line_of(0-based line offset)`."""
    words: list[str] = []
    lines: list[int] = []
    fenced = False
    for offset, line in enumerate(body.splitlines()):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced:
            for word in prose_tokens(line):
                words.append(word)
                lines.append(line_of(offset))
    return ProseText(path, label, tuple(words), tuple(lines))
