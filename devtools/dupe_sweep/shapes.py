"""dupe_sweep — one concept, two implementations: each function's structural shape as a unit.

A shape is the pre-order sequence of AST node types of a function's parameters and body,
docstring dropped: names, literals and comments are invisible to it, so two spellings of one
algorithm collide. Classes are swept through their methods, never whole — a class's shape
contains its methods', so each would match its own class.
"""

import ast
from collections.abc import Iterator

from .clustering import Unit
from .python_corpus import parse_module


def _shape(node: ast.AST) -> list[str]:
    shape = []
    for child in ast.iter_child_nodes(node):
        shape.append(type(child).__name__)
        shape.extend(_shape(child))
    return shape


def _without_docstring(body: list[ast.stmt]) -> list[ast.stmt]:
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        if isinstance(body[0].value.value, str):
            return body[1:]
    return body


def shape_units(files: dict[str, str]) -> list[Unit]:
    """One unit per function — top-level or a method — carrying its structural shape.

    A function nested inside another is not its own unit: its shape is already
    part of its parent's, so the two would report as duplicates of each other.
    """
    units = []
    for path, text in sorted(files.items()):
        tree = parse_module(path, text)
        if tree is None:
            continue
        lines = text.splitlines()
        for owner, function in _functions(tree):
            tokens = _shape(function.args) + [
                token
                for statement in _without_docstring(function.body)
                for token in [type(statement).__name__, *_shape(statement)]
            ]
            label = f"{owner}.{function.name}()" if owner else f"{function.name}()"
            signature = lines[function.lineno - 1].strip() if function.lineno <= len(lines) else label
            units.append(Unit(path, function.lineno, label, signature, tuple(tokens)))
    return units


def _functions(tree: ast.Module) -> Iterator[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef]]:
    """(owning class name or "", function) for every module-level function and method."""
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield "", node
        elif isinstance(node, ast.ClassDef):
            for member in node.body:
                if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield node.name, member
