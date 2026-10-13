"""dupe_sweep — text as the comparison reads it: lower-cased words, markers dropped.

Every text becomes its lower-cased alphanumeric words — case, punctuation,
markup and where the text wrapped all vanish.
"""

import re

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
