"""The source rules a definition module and the clauses module are written to, checked over their
syntax trees. Nothing here runs at render: the suite asserts `check_structure` empty over the
package, and proves each rule on a fixture.

A definition module holds imports, string constants and `DEFINITIONS`. Its constants are string
literals or f-strings over its own constants. Its only calls are `Definition(...)` as a
`DEFINITIONS` element and, inside a `body=` value, `clauses.<name>(...)` and
`<constant>.format(...)` on one of its string literals, every argument a string literal or a
constant. The clauses module holds string constants and text functions: at most three keyword-only
parameters, one returned string over the parameters and its constants, and no call.
"""

import ast
from pathlib import Path

TEXT_MODULE = "clauses.py"
CLAUSES = "clauses"

ASSIGNMENT_RULE = "a module-level assignment is a string literal or an f-string over the module's constant names"
CALL_RULE = (
    "a definition module calls only Definition(...) in DEFINITIONS and, inside a body= value, "
    "clauses.<name>(...) or .format(...) on one of its string literals"
)
ARGUMENT_RULE = "an argument to a text function or a .format is a string literal or a module-level constant"
BODY_RULE = "a body= expression is a module constant, a clauses.<name>, or a permitted call"
FUNCTION_RULE = (
    "a text function takes at most three keyword-only parameters and returns one string over its "
    "parameters and module constants, with no call"
)
DEFINITION_TOP_RULE = "a definition module's top level holds only imports, string constants and DEFINITIONS"
TEXT_TOP_RULE = "the text module's top level holds only string constants and text functions"
IMPORT_RULE = "the clauses module is imported only as `from adjagent import clauses`"


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
    return node.module == "adjagent" and any(
        alias.name == CLAUSES and alias.asname is not None for alias in node.names
    )


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
    """DEFINITIONS is a non-empty tuple of Definition(...) calls; a call anywhere in it but in a
    body= value is a violation, and in a body= value only the permitted calls and names stand."""
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
        for argument in [*element.args, *element.keywords]:
            if isinstance(argument, ast.keyword) and argument.arg == "body":
                found += _body_violations(argument.value, constants)
            else:
                found += [(call.lineno, CALL_RULE) for call in ast.walk(argument) if isinstance(call, ast.Call)]
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
    return isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == CLAUSES


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
