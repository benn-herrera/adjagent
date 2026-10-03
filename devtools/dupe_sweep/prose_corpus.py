"""dupe_sweep — what the prose pass reads: chunk bodies and template bodies, as prose texts.

Every ``text`` and ``variants`` body in ``templates/shared-chunks.toml``, and the body of every
template under ``templates/agents/`` and ``templates/commands/``. A chunk's ``defaults`` values
are argument text a call site binds, not a body, and are not read. A chunk passage is sited at
its ``[chunks.<name>]`` header line, since a TOML string's interior lines have no positions to
read back; its label identifies it.
"""

import logging
import re
import tomllib

from gen_defs.paths import TEMPLATE_SUFFIX

from .corpus import corpus
from .normalization import ProseText, prose_text

log = logging.getLogger(__name__)

TEMPLATE_PREFIXES = ("templates/agents", "templates/commands")
CHUNK_SOURCE = "templates/shared-chunks.toml"

_CHUNK_HEADER = re.compile(r"^[ \t]*\[chunks\.([a-z0-9-]+)", re.MULTILINE)


def template_body(text: str) -> tuple[int, str]:
    """(1-based line the body starts at, the body) — `+++` fence and frontmatter dropped.

    Neither renders into a prompt: the fence declares a multi-output template's
    parameters and carries maintainer comments, and the frontmatter is dispatch
    metadata. A sentence in either is not prose a seat reads.
    """
    lines = text.splitlines()
    at = 0
    for opener in ("+++", "---"):
        while at < len(lines) and not lines[at].strip():
            at += 1
        if at < len(lines) and lines[at].strip() == opener:
            closing = next((index for index in range(at + 1, len(lines)) if lines[index].strip() == opener), None)
            if closing is None:
                log.warning("unclosed %s block — the whole file is read as body", opener)
                break
            at = closing + 1
    return at + 1, "\n".join(lines[at:])


def chunk_bodies(text: str) -> list[tuple[str, int, str]]:
    """(label, header line, body) for every chunk `text` body and every variant body."""
    data = tomllib.loads(text)
    header_lines: dict[str, int] = {}
    for match in _CHUNK_HEADER.finditer(text):
        header_lines.setdefault(match.group(1), text.count("\n", 0, match.start()) + 1)

    bodies = []
    for name, chunk in sorted(data.get("chunks", {}).items()):
        line = header_lines.get(name, 1)
        if isinstance(chunk.get("text"), str):
            bodies.append((f"chunks.{name}", line, chunk["text"]))
        for variant, body in sorted(chunk.get("variants", {}).items()):
            if isinstance(body, str):
                bodies.append((f"chunks.{name}.{variant}", line, body))
    return bodies


def prose_texts(*, rev: str | None) -> list[ProseText]:
    """Every body of the template corpus, chunk bodies and inline prose alike, in a fixed order."""
    texts: list[ProseText] = []
    for path, text in corpus(rev=rev, prefixes=[CHUNK_SOURCE], suffix=".toml").items():
        for label, line, body in chunk_bodies(text):
            texts.append(prose_text(path, label, body, line_of=lambda _offset: line))
    for path, text in corpus(rev=rev, prefixes=TEMPLATE_PREFIXES, suffix=TEMPLATE_SUFFIX).items():
        start, body = template_body(text)
        texts.append(prose_text(path, "", body, line_of=lambda offset: start + offset))
    return texts
