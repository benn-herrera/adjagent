"""The gen_defs package's import structure: imports at module level only, and an
acyclic graph between the package's modules.

Cycles are kept out of the package by where definitions are placed, never by an
import deferred into a function body — which would hide a cycle rather than
remove it. Both halves are read from the source's AST alone; nothing here
imports `gen_defs`, so no module (`__main__` included) runs.

There is deliberately no layer table: acyclicity is the invariant, and a list
of which module may import which would restate today's layout.
"""

import ast
import graphlib
from pathlib import Path

_PACKAGE = "gen_defs"
_PACKAGE_DIR = Path(__file__).resolve().parent.parent / _PACKAGE


def _modules() -> dict[str, ast.Module]:
    """Every module in the package, parsed, keyed by module name."""
    return {
        path.stem: ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for path in sorted(_PACKAGE_DIR.glob("*.py"))
    }


def _imported_modules(node: ast.Import | ast.ImportFrom, *, names: set[str]) -> set[str]:
    """The package modules one import statement reaches. `from . import x`
    reaches submodule `x` when there is one, and `__init__` otherwise."""
    if isinstance(node, ast.Import):
        dotted = [alias.name for alias in node.names]
    elif node.level == 1:
        dotted = [f"{_PACKAGE}.{node.module}"] if node.module else [f"{_PACKAGE}.{a.name}" for a in node.names]
    elif node.level == 0 and node.module == _PACKAGE:
        dotted = [f"{_PACKAGE}.{alias.name}" for alias in node.names]
    elif node.level == 0:
        dotted = [node.module or ""]
    else:
        raise AssertionError(f"line {node.lineno}: relative import reaches outside the package")
    reached = set()
    for name in dotted:
        head, _, rest = name.partition(".")
        if head != _PACKAGE:
            continue
        module = rest.partition(".")[0]
        reached.add(module if module in names else "__init__")
    return reached


def test_no_import_below_module_level():
    nested = [
        f"{module}.py:{node.lineno}"
        for module, tree in _modules().items()
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom)) and node not in tree.body
    ]
    assert not nested, f"imports below module level: {', '.join(nested)}"


def test_import_graph_is_acyclic():
    modules = _modules()
    graph = {
        module: {
            target
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for target in _imported_modules(node, names=set(modules))
        }
        for module, tree in modules.items()
    }
    try:
        tuple(graphlib.TopologicalSorter(graph).static_order())
    except graphlib.CycleError as exc:
        raise AssertionError(f"import cycle: {' -> '.join(exc.args[1])}") from None


def test_only_the_renders_reference_the_expander():
    # Sources are pure lookups: a module outside the renders reaching
    # `expand` is a source expanding its own text.
    allowed = {"markers", "rendering", "agents_file"}
    referencing = {
        module
        for module, tree in _modules().items()
        for node in ast.walk(tree)
        if (isinstance(node, ast.Name) and node.id == "expand")
        or (isinstance(node, ast.Attribute) and node.attr == "expand")
        or (isinstance(node, ast.alias) and node.name == "expand")
    }
    assert referencing <= allowed, f"modules referencing the expander: {', '.join(sorted(referencing - allowed))}"
