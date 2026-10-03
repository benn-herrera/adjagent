"""dupe_sweep — one constant, two definitions: module-level literal bindings and their candidates.

A candidate is one name bound twice, or one distinctive value bound under similar names in two
modules.
"""

import ast
import difflib
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations

from .normalization import ellipsis
from .python_corpus import parse_module

_TRIVIAL_LITERALS = frozenset({"None", "True", "False", "''", '""', "()", "[]", "{}", "0", "1", "-1", "0.0", "b''"})
#: What makes a literal identifying rather than a coincidence — see :func:`_distinctive`.
_DISTINCTIVE_MAGNITUDE = 10
_DISTINCTIVE_WIDTH = 5


@dataclass(frozen=True)
class Constant:
    """One module-level binding of a literal value."""

    path: str
    line: int
    name: str
    value: str


def constants(files: dict[str, str]) -> list[Constant]:
    """Module-level literal bindings, trivia dropped."""
    found = []
    for path, text in sorted(files.items()):
        tree = parse_module(path, text)
        if tree is None:
            continue
        for node in tree.body:
            if isinstance(node, ast.Assign):
                targets = [target for target in node.targets if isinstance(target, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target]
            else:
                continue
            value = _literal(node.value)
            if value is None:
                continue
            for target in targets:
                if not target.id.startswith("__"):
                    found.append(Constant(path, node.lineno, target.id, value))
    return found


def _literal(node: ast.expr | None) -> str | None:
    """`repr` of a literal expression, or None when it is not one or is trivia."""
    if node is None:
        return None
    try:
        value = ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return None
    shown = repr(value)
    return None if shown in _TRIVIAL_LITERALS else shown


def _distinctive(value: str) -> bool:
    """Whether a value is identifying enough for two bindings of it to mean anything.

    A bare small integer is not: `EXIT_USAGE = 2` and `EDGE_STROKE_WIDTH = 2` share
    a value and nothing else, and reporting every such coincidence is how a
    candidate list stops being read. The repeated-name check still covers them.
    """
    try:
        return abs(float(value)) >= _DISTINCTIVE_MAGNITUDE
    except ValueError:
        return len(value) >= _DISTINCTIVE_WIDTH


def _similar(left: str, right: str) -> float:
    return difflib.SequenceMatcher(None, left.lower(), right.lower(), autojunk=False).ratio()


def constant_candidates(found: Sequence[Constant], *, name_similarity: float = 0.6) -> list[tuple[str, list[Constant]]]:
    """(what makes them look alike, sites) for repeated values and repeated names."""
    candidates: list[tuple[str, list[Constant]]] = []

    by_value: dict[str, list[Constant]] = {}
    by_name: dict[str, list[Constant]] = {}
    for constant in sorted(found, key=lambda item: (item.path, item.line, item.name)):
        by_value.setdefault(constant.value, []).append(constant)
        by_name.setdefault(constant.name, []).append(constant)

    # Names first: a group both rules find is the repeated name, and reporting it
    # again as a repeated value says nothing the reader did not just read.
    reported: set[frozenset[tuple[str, int]]] = set()
    for name, sites in sorted(by_name.items()):
        if len(sites) < 2:
            continue
        modules = {site.path for site in sites}
        where = "twice in one module" if len(modules) == 1 else f"in {len(modules)} modules"
        candidates.append((f"one name bound {where}: {name}", sites))
        reported.add(frozenset((site.path, site.line) for site in sites))

    for value, sites in sorted(by_value.items()):
        modules = {site.path for site in sites}
        if len(modules) < 2 or not _distinctive(value):
            continue
        if frozenset((site.path, site.line) for site in sites) in reported:
            continue
        pairs = combinations(sites, 2)
        if any(left.path != right.path and _similar(left.name, right.name) >= name_similarity for left, right in pairs):
            candidates.append((f"one value in {len(modules)} modules under similar names: {ellipsis(value)}", sites))

    candidates.sort(key=lambda item: (-len(item[1]), item[0]))
    return candidates
