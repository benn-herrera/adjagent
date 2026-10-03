"""The dupe_sweep package's import structure: imports at module level only, the
package's own modules reached by relative import, and an acyclic graph between them.

Cycles are kept out of the package by where definitions are placed, never by an
import deferred into a function body — which would hide a cycle rather than
remove it. Everything is read from the source's AST alone; nothing here imports
the package, so no module (`__main__` included) runs.
"""

import ast
import graphlib
from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent.parent / "dupe_sweep"


def _modules() -> dict[str, ast.Module]:
    """Every module in the package, parsed, keyed by module name."""
    return {
        path.stem: ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for path in sorted(_PACKAGE_DIR.glob("*.py"))
    }


def _imports(tree: ast.Module) -> list[ast.Import | ast.ImportFrom]:
    return [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]


def test_no_import_below_module_level():
    nested = [
        f"{module}.py:{node.lineno}"
        for module, tree in _modules().items()
        for node in _imports(tree)
        if node not in tree.body
    ]
    assert not nested, f"imports below module level: {', '.join(nested)}"


def _absolute_names(node: ast.Import | ast.ImportFrom) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    return [node.module or ""] if node.level == 0 else []


def test_the_package_reaches_its_own_modules_by_relative_import_and_nothing_else_by_one():
    """Only a relative import is an edge the graph below reads, so an absolute
    one would be a cycle it cannot see; a parent-relative one leaves the package."""
    wrong = [
        f"{module}.py:{node.lineno}"
        for module, tree in _modules().items()
        for node in _imports(tree)
        if (isinstance(node, ast.ImportFrom) and node.level > 1)
        or any(name == "devtools" or name.startswith(("devtools.", "dupe_sweep")) for name in _absolute_names(node))
    ]
    assert not wrong, f"imports reaching the package absolutely or leaving it relatively: {', '.join(wrong)}"


def test_import_graph_is_acyclic():
    modules = _modules()
    graph = {
        module: {
            target
            for node in _imports(tree)
            if isinstance(node, ast.ImportFrom) and node.level == 1
            for target in ([node.module] if node.module else [alias.name for alias in node.names])
            if target in modules
        }
        for module, tree in modules.items()
    }
    try:
        tuple(graphlib.TopologicalSorter(graph).static_order())
    except graphlib.CycleError as exc:
        raise AssertionError(f"import cycle: {' -> '.join(exc.args[1])}") from None
