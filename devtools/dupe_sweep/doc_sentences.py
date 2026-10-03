"""dupe_sweep — one rule, two homes: every docstring and comment sentence as a unit.

*Docstring and comment sentence splitting* is punctuation, not linguistic: an
abbreviation mid-sentence ("e.g.") splits, and the fragments are usually short
enough to fall under ``--min-words``. Each docstring and comment block is first
rejoined across its hard wrap, because a sentence broken at a different column
is still the same sentence; *a sentence's line* is the line its block starts on.
"""

import ast
import io
import logging
import re
import tokenize
from collections.abc import Iterator, Sequence

from .clustering import Unit
from .normalization import prose_tokens
from .python_corpus import parse_module

log = logging.getLogger(__name__)

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_WHITESPACE = re.compile(r"\s+")


def _split_sentences(text: str) -> list[str]:
    return [piece.strip() for piece in _SENTENCE_END.split(text) if piece.strip()]


def block_sentences(numbered: Sequence[tuple[int, str]]) -> Iterator[tuple[int, str]]:
    """(1-based line its block starts on, sentence) over hard-wrapped prose.

    Takes already-numbered lines so a docstring's offset and a run of comment
    lines reach it the same way. A blank line ends a block; inside one, every
    whitespace run is a single space, so where the text wrapped is invisible to
    the split.
    """
    block: list[str] = []
    start = 0
    for number, line in [*numbered, (0, "")]:
        if line.strip():
            if not block:
                start = number
            block.append(line)
            continue
        for sentence in _split_sentences(_WHITESPACE.sub(" ", " ".join(block))):
            yield start, sentence
        block = []


def doc_units(files: dict[str, str]) -> list[Unit]:
    """Every sentence of every docstring and comment, rejoined across its hard wrap."""
    units = []
    for path, text in sorted(files.items()):
        tree = parse_module(path, text)
        if tree is None:
            continue
        for owner, doc, first_line in _docstrings(tree):
            lines = list(enumerate(doc.splitlines(), start=first_line))
            for line, sentence in block_sentences(lines):
                units.append(Unit(path, line, owner, sentence, prose_tokens(sentence)))
        for line, sentence in block_sentences(_comment_lines(path, text)):
            units.append(Unit(path, line, "comment", sentence, prose_tokens(sentence)))
    return units


def _docstrings(tree: ast.Module) -> Iterator[tuple[str, str, int]]:
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        doc = ast.get_docstring(node, clean=True)
        if doc:
            name = "module docstring" if isinstance(node, ast.Module) else f"{node.name} docstring"
            yield name, doc, node.body[0].lineno


def _comment_lines(path: str, text: str) -> list[tuple[int, str]]:
    """(line, comment text) for every comment, with a blank line between blocks.

    The blank separates comments that merely sit near each other, so
    :func:`block_sentences` rejoins a wrapped comment and nothing else.
    """
    lines: list[tuple[int, str]] = []
    previous = 0
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError) as exc:
        log.warning("%s does not tokenize (%s) — its comments are skipped", path, exc)
        return lines
    for token in tokens:
        if token.type != tokenize.COMMENT:
            continue
        line = token.start[0]
        if line != previous + 1:
            lines.append((line, ""))
        lines.append((line, token.string.lstrip("#:").strip()))
        previous = line
    return lines
