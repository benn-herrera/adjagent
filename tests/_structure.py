"""The source rules a definition module and the clauses module are written to, checked over their
syntax trees. Nothing here runs at render: the suite asserts `check_structure` empty over the
package, and proves each rule on a fixture.

A definition module holds imports, string constants and `DEFINITIONS`. Its constants are string
literals or f-strings over its own constants. Its only calls are `Definition(...)` as a
`DEFINITIONS` element, `SkillFile(...)` as a `files=` element, and, inside a `body=` or
`description=` value or a `SkillFile` body, `clauses.<name>(...)` and `<constant>.format(...)` on one of its string literals,
every argument a string literal or a constant. The clauses module holds string constants and text
functions: at most three keyword-only parameters, one returned string over the parameters and its
constants, and no call.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

TEXT_MODULE = "clauses.py"
CLAUSES = "clauses"

ASSIGNMENT_RULE = "a module-level assignment is a string literal or an f-string over the module's constant names"
CALL_RULE = (
    "a definition module calls only Definition(...) in DEFINITIONS, SkillFile(...) in a files= value, and "
    "clauses.<name>(...) or .format(...) on a string literal inside a body= or description= value"
)
ARGUMENT_RULE = "an argument to a text function or a .format is a string literal or a module-level constant"
BODY_RULE = "a body= or description= expression is a module constant, a clauses.<name>, or a permitted call"
DEFINITION_CALL_RULE = "a Definition(...) in DEFINITIONS takes keyword arguments only"
FILES_RULE = "files= is a tuple of SkillFile(path=<string literal>, body=<body>) calls"
FUNCTION_RULE = (
    "a text function takes at most three keyword-only parameters and returns one string over its "
    "parameters and module constants, with no call"
)
DEFINITION_TOP_RULE = "a definition module's top level holds only imports, string constants and DEFINITIONS"
TEXT_TOP_RULE = "the text module's top level holds only string constants and text functions"
IMPORT_RULE = "the clauses module is imported only as `from adjagent import clauses`"


def carried_clauses(source: str) -> dict[str, set[str]]:
    """For each `Definition(...)` call in a definition module's source, its `name=` literal mapped to
    the `clauses.<name>` attributes the call names, whether read or called."""
    return {
        name: {node.attr for node in ast.walk(call) if _is_clause(node)} for name, call in _definition_calls(source)
    }


def _definition_calls(source: str) -> Iterator[tuple[str, ast.Call]]:
    """Each `Definition(...)` call in a definition module's source, with its `name=` literal; a
    `name=` that is not a string literal raises ValueError."""
    for call in ast.walk(ast.parse(source)):
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "Definition"):
            continue
        name = next((keyword.value for keyword in call.keywords if keyword.arg == "name"), None)
        if not (name is not None and _is_literal(name)):
            raise ValueError(f"line {call.lineno}: a Definition(...) call's name= is not a string literal")
        yield name.value, call


@dataclass(frozen=True)
class ClauseNode:
    """A clauses-module constant or text function: the names its string interpolates, in order, and
    for a text function each keyword parameter mapped to its constant default, or None where the
    default is a literal or absent."""

    edges: tuple[str, ...]
    defaults: dict[str, str | None]


@dataclass(frozen=True)
class ClauseRoot:
    """A `clauses.<name>` a body names, with the keyword parameters a call to it passes."""

    name: str
    passed: frozenset[str]


Reach = tuple[str, tuple[str, ...]]
"""Where a node was reached: the label of the roots that reached it, and the chain from the root."""


def clause_graph(source: str) -> dict[str, ClauseNode]:
    """Every constant and text function of the clauses module's source, by name."""
    graph = {}
    for node in ast.parse(source).body:
        if name := _target(node):
            graph[name] = ClauseNode(edges=_interpolated(node.value), defaults={})
        elif isinstance(node, ast.FunctionDef):
            returned = next(statement.value for statement in node.body if isinstance(statement, ast.Return))
            defaults = {
                argument.arg: default.id if isinstance(default, ast.Name) else None
                for argument, default in zip(node.args.kwonlyargs, node.args.kw_defaults)
            }
            graph[node.name] = ClauseNode(edges=_interpolated(returned), defaults=defaults)
    return graph


def body_roots(source: str, graph: dict[str, ClauseNode]) -> dict[tuple[str, str | None], tuple[ClauseRoot, ...]]:
    """For each body in a definition module's source, keyed by its definition's `name=` and its
    `SkillFile` `path=` (None for the definition's own body), the `clauses.<name>` it names in source
    order. A text-function call's argument is listed once for each time the function, per `graph`,
    interpolates that parameter."""
    roots = {}
    for name, call in _definition_calls(source):
        keywords = {keyword.arg: keyword.value for keyword in call.keywords}
        roots[name, None] = tuple(_clause_roots(keywords["body"], graph))
        for file in keywords["files"].elts if "files" in keywords else ():
            file_keywords = {keyword.arg: keyword.value for keyword in file.keywords}
            roots[name, file_keywords["path"].value] = tuple(_clause_roots(file_keywords["body"], graph))
    return roots


def repeated_clause_reaches(
    graph: dict[str, ClauseNode], rooted: list[tuple[str, tuple[ClauseRoot, ...]]], *, uncounted: frozenset[str]
) -> list[tuple[str, Reach, Reach]]:
    """Each node a depth-first walk from the labelled roots reaches a second time, with the reach that
    came first and the repeat. A node in `uncounted` is not walked; nothing below a repeat is walked,
    so a node is never reported under a parent already reported. A parameter's constant default is
    an edge only where the root's call does not pass that parameter."""
    first: dict[str, Reach] = {}
    repeats = []

    def visit(name: str, *, label: str, chain: tuple[str, ...], passed: frozenset[str]) -> None:
        if name in uncounted:
            return
        path = (*chain, name)
        if name in first:
            repeats.append((name, first[name], (label, path)))
            return
        first[name] = (label, path)
        node = graph[name]
        for edge in node.edges:
            if edge in node.defaults:
                default = node.defaults[edge]
                if default is None or edge in passed:
                    continue
                edge = default
            visit(edge, label=label, chain=path, passed=frozenset())

    for label, roots in rooted:
        for root in roots:
            visit(root.name, label=label, chain=(), passed=root.passed)
    return repeats


def _interpolated(value: ast.expr) -> tuple[str, ...]:
    """The bare names an f-string interpolates, in order; none for a string literal."""
    if not isinstance(value, ast.JoinedStr):
        return ()
    return tuple(part.value.id for part in value.values if isinstance(part, ast.FormattedValue))


def _clause_roots(node: ast.AST, graph: dict[str, ClauseNode]) -> list[ClauseRoot]:
    if isinstance(node, ast.Call) and _is_clause(node.func):
        edges = graph[node.func.attr].edges
        roots = [ClauseRoot(node.func.attr, frozenset(keyword.arg for keyword in node.keywords))]
        for keyword in node.keywords:
            roots += _clause_roots(keyword.value, graph) * edges.count(keyword.arg)
        return roots
    if _is_clause(node):
        return [ClauseRoot(node.attr, frozenset())]
    return [root for child in ast.iter_child_nodes(node) for root in _clause_roots(child, graph)]


def _is_clause(node: ast.AST) -> bool:
    return isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == CLAUSES


def check_structure(paths: list[Path]) -> list[str]:
    """Every violation in the given files, as `<path>:<line>: <rule>`; the file named `clauses.py`
    is read as the clauses module, any other as a definition module."""
    violations = []
    for path in paths:
        source = path.read_text(encoding="utf-8")
        violations += check_source(source, where=str(path), text_module=path.name == TEXT_MODULE)
    return violations


def check_source(source: str, *, where: str, text_module: bool) -> list[str]:
    """`check_structure` for one module's source."""
    tree = ast.parse(source)
    found: list[tuple[int, str]] = []
    constants = _constants(tree)
    for index, node in enumerate(tree.body):
        if index == 0 and isinstance(node, ast.Expr) and _is_literal(node.value):
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if text_module:
                found.append((node.lineno, TEXT_TOP_RULE))
            elif _imports_text_wrongly(node):
                found.append((node.lineno, IMPORT_RULE))
        elif text_module and isinstance(node, ast.FunctionDef):
            if not _is_text_function(node, constants):
                found.append((node.lineno, FUNCTION_RULE))
        elif not text_module and _target(node) == "DEFINITIONS":
            found += _definitions_violations(node, constants)
        elif isinstance(node, ast.Assign) and _target(node):
            if not _is_constant_text(node.value, names=constants):
                found.append((node.lineno, ASSIGNMENT_RULE))
        else:
            found.append((node.lineno, TEXT_TOP_RULE if text_module else DEFINITION_TOP_RULE))
    return [f"{where}:{line}: {rule}" for line, rule in sorted(set(found))]


def _target(node: ast.stmt) -> str:
    """The one name a single-target assignment binds, or ""."""
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    return ""


def _constants(tree: ast.Module) -> dict[str, ast.expr]:
    """Every module-level single-name assignment but DEFINITIONS, by name, with its value."""
    return {_target(node): node.value for node in tree.body if _target(node) not in ("", "DEFINITIONS")}


def _is_literal(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _is_constant_text(node: ast.expr, *, names: dict[str, ast.expr] | set[str]) -> bool:
    """A string literal, or an f-string whose every expression is a bare name among `names`."""
    if _is_literal(node):
        return True
    return isinstance(node, ast.JoinedStr) and all(
        part.conversion == -1
        and part.format_spec is None
        and isinstance(part.value, ast.Name)
        and part.value.id in names
        for part in node.values
        if isinstance(part, ast.FormattedValue)
    )


def _imports_text_wrongly(node: ast.Import | ast.ImportFrom) -> bool:
    if isinstance(node, ast.Import):
        return any(alias.name == f"adjagent.{CLAUSES}" for alias in node.names)
    if node.module == f"adjagent.{CLAUSES}":
        return True
    return node.module == "adjagent" and any(alias.name == CLAUSES and alias.asname is not None for alias in node.names)


def _is_text_function(node: ast.FunctionDef, constants: dict[str, ast.expr]) -> bool:
    arguments = node.args
    if node.decorator_list or arguments.posonlyargs or arguments.args or arguments.vararg or arguments.kwarg:
        return False
    if len(arguments.kwonlyargs) > 3:
        return False
    if not all(
        default is None or _is_literal(default) or (isinstance(default, ast.Name) and default.id in constants)
        for default in arguments.kw_defaults
    ):
        return False
    body = node.body[1:] if isinstance(node.body[0], ast.Expr) and _is_literal(node.body[0].value) else node.body
    names = {argument.arg for argument in arguments.kwonlyargs} | set(constants)
    return (
        len(body) == 1
        and isinstance(body[0], ast.Return)
        and body[0].value is not None
        and _is_constant_text(body[0].value, names=names)
    )


def _definitions_violations(node: ast.stmt, constants: dict[str, ast.expr]) -> list[tuple[int, str]]:
    """DEFINITIONS is a non-empty tuple of Definition(...) calls; a call anywhere in it but in a body= or
    description= value or in a files= element is a violation, and in those only the permitted calls and
    names stand."""
    value = node.value if isinstance(node, ast.Assign) else None
    if not isinstance(value, ast.Tuple) or not value.elts:
        return [(node.lineno, DEFINITION_TOP_RULE)]
    found = []
    for element in value.elts:
        if not (
            isinstance(element, ast.Call) and isinstance(element.func, ast.Name) and element.func.id == "Definition"
        ):
            found.append((element.lineno, DEFINITION_TOP_RULE))
            continue
        if element.args:
            found.append((element.lineno, DEFINITION_CALL_RULE))
            continue
        for keyword in element.keywords:
            if keyword.arg in ("body", "description"):
                found += _body_violations(keyword.value, constants)
            elif keyword.arg == "files":
                found += _files_violations(keyword.value, constants)
            else:
                found += [(call.lineno, CALL_RULE) for call in ast.walk(keyword) if isinstance(call, ast.Call)]
    return found


def _files_violations(files: ast.expr, constants: dict[str, ast.expr]) -> list[tuple[int, str]]:
    """`files=` is a tuple of `SkillFile(path=<string literal>, body=<body>)` calls; each body is walked
    under the body= rule, and a call standing anywhere else in the value is a violation."""
    if not isinstance(files, ast.Tuple):
        return [(files.lineno, FILES_RULE)]
    found = []
    for element in files.elts:
        if not (
            isinstance(element, ast.Call) and isinstance(element.func, ast.Name) and element.func.id == "SkillFile"
        ):
            found.append((element.lineno, CALL_RULE))
            continue
        keywords = {keyword.arg: keyword.value for keyword in element.keywords}
        if element.args or None in keywords or set(keywords) != {"path", "body"}:
            found.append((element.lineno, FILES_RULE))
            continue
        if not _is_literal(keywords["path"]):
            found.append((keywords["path"].lineno, FILES_RULE))
        found += _body_violations(keywords["body"], constants)
    return found


def _body_violations(body: ast.expr, constants: dict[str, ast.expr]) -> list[tuple[int, str]]:
    if _is_literal(body) or _is_reference(body, constants):
        return []
    if not isinstance(body, ast.JoinedStr):
        return [(body.lineno, BODY_RULE)]
    found = []
    for part in body.values:
        if not isinstance(part, ast.FormattedValue):
            continue
        expression = part.value
        if part.conversion != -1 or part.format_spec is not None:
            found.append((expression.lineno, BODY_RULE))
        elif isinstance(expression, ast.Call):
            found += _call_violations(expression, constants)
        elif not _is_reference(expression, constants):
            found.append((expression.lineno, BODY_RULE))
    return found


def _is_reference(node: ast.expr, constants: dict[str, ast.expr]) -> bool:
    """A name among the module's constants, or `clauses.<name>`."""
    if isinstance(node, ast.Name):
        return node.id in constants
    return _is_clause(node)


def _call_violations(call: ast.Call, constants: dict[str, ast.expr]) -> list[tuple[int, str]]:
    function = call.func
    text_call = isinstance(function, ast.Attribute) and _is_reference(function, constants)
    receiver = function.value if isinstance(function, ast.Attribute) else None
    format_call = (
        isinstance(function, ast.Attribute)
        and function.attr == "format"
        and isinstance(receiver, ast.Name)
        and _is_literal(constants.get(receiver.id, ast.Constant(None)))
    )
    if not (text_call or format_call):
        return [(call.lineno, CALL_RULE)]
    values = [*call.args, *(keyword.value for keyword in call.keywords)]
    if any(keyword.arg is None for keyword in call.keywords) or not all(
        _is_literal(value) or _is_reference(value, constants) for value in values
    ):
        return [(call.lineno, ARGUMENT_RULE)]
    return []
