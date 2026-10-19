"""dupe_sweep — what the python pass reads: the owned python trees, less their tests.

``tests/`` is unswept because a fixture is data and a test function is called by pytest.
"""

import ast
import logging

from .corpus import corpus

log = logging.getLogger(__name__)

CODE_PREFIXES = ("liaison_tools", "adjagent", "devtools")
CODE_UNSWEPT = ("liaison_tools/tests/", "devtools/tests/")


def code_corpus(*, rev: str | None) -> dict[str, str]:
    swept = corpus(rev=rev, prefixes=list(CODE_PREFIXES), suffix=".py")
    return {path: text for path, text in swept.items() if not path.startswith(CODE_UNSWEPT)}


def parse_module(path: str, text: str) -> ast.Module | None:
    try:
        return ast.parse(text, filename=path)
    except SyntaxError as exc:
        log.warning("%s does not parse (%s) — skipped", path, exc)
        return None
