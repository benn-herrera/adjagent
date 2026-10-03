"""dupe_sweep — what the python pass reads: kb_tools/ less its tests and vendored source, parsed.

``tests/`` is unswept because a fixture is data and a test function is called by pytest;
``_vendor/`` because it is third-party source this repository never edits.
"""

import ast
import logging

from .corpus import corpus

log = logging.getLogger(__name__)

CODE_PREFIX = "kb_tools"
CODE_UNSWEPT = ("kb_tools/tests/", "kb_tools/_vendor/")


def code_corpus(*, rev: str | None) -> dict[str, str]:
    swept = corpus(rev=rev, prefixes=[CODE_PREFIX], suffix=".py")
    return {path: text for path, text in swept.items() if not path.startswith(CODE_UNSWEPT)}


def parse_module(path: str, text: str) -> ast.Module | None:
    try:
        return ast.parse(text, filename=path)
    except SyntaxError as exc:
        log.warning("%s does not parse (%s) — skipped", path, exc)
        return None
