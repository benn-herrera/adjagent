"""Which module may import what, around the KB format, as a mechanical assertion.

`kb_migrate` is pure conversion — text in, text out — so it imports the dialect, the schema
vocabulary and the standard library, and nothing that could reach a file or another module's
internals. `kb_load` is imported by `kb_index_lib`, `kb_pipeline` and `kb_write`, so it imports none
of them. `kb_yaml` imports nothing of the package. No module imports a YAML package: the dialect is
`kb_yaml`'s, in the standard library alone.

What counts as an import is every `import` and `from … import` statement anywhere in the module,
function bodies included, relative imports resolved against the module's own package.
"""

import ast
import sys
from pathlib import Path

import pytest

import kb_tools

_PACKAGE_ROOT = Path(kb_tools.__file__).resolve().parent
_YAML_PACKAGES = frozenset({"yaml", "ruamel", "strictyaml", "oyaml"})


def _imports(source: str, package: str) -> set[str]:
    """Every module `source` imports, a `kb_tools` one named to its first submodule."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parent = package.split(".")[: len(package.split(".")) - node.level + 1]
                base = ".".join([*parent, base] if base else parent)
            if base == "kb_tools":
                names.update(f"kb_tools.{alias.name}" for alias in node.names)
            else:
                names.add(base)
    return {".".join(name.split(".")[:2]) if name.startswith("kb_tools.") else name for name in names}


def _module_imports(relpath: str) -> set[str]:
    path = _PACKAGE_ROOT / relpath
    package = ".".join(["kb_tools", *Path(relpath).parent.parts])
    return _imports(path.read_text(encoding="utf-8"), package)


def _is_stdlib(name: str) -> bool:
    return name.split(".")[0] in sys.stdlib_module_names


def test_kb_migrate_imports_only_the_dialect_the_schema_and_the_standard_library() -> None:
    imported = _module_imports("kb_migrate.py")

    assert {name for name in imported if not _is_stdlib(name)} <= {"kb_tools.kb_yaml", "kb_tools.kb_schema"}
    assert "kb_tools.kb_yaml" in imported, "the sweep no longer sees kb_migrate's own imports"


def test_kb_load_imports_none_of_the_modules_that_import_it() -> None:
    imported = _module_imports("kb_load.py")

    assert imported & {"kb_tools.kb_index_lib", "kb_tools.kb_pipeline", "kb_tools.kb_write"} == set()
    assert "kb_tools.kb_migrate" in imported, "the sweep no longer sees kb_load's own imports"


def test_kb_yaml_imports_only_the_standard_library() -> None:
    assert {name for name in _module_imports("kb_yaml.py") if not _is_stdlib(name)} == set()


def test_no_module_imports_a_yaml_package() -> None:
    modules = sorted(path.relative_to(_PACKAGE_ROOT).as_posix() for path in _PACKAGE_ROOT.rglob("*.py"))
    importing = {
        relpath for relpath in modules if {name.split(".")[0] for name in _module_imports(relpath)} & _YAML_PACKAGES
    }

    assert len(modules) >= 30, "the sweep no longer walks the package"
    assert importing == set()


@pytest.mark.parametrize(
    ("source", "package", "expected"),
    [
        ("import json\nfrom collections.abc import Mapping\n", "kb_tools", {"json", "collections.abc"}),
        ("from kb_tools import kb_yaml, kb_util\n", "kb_tools", {"kb_tools.kb_yaml", "kb_tools.kb_util"}),
        ("from kb_tools.kb_write.ops import run\n", "kb_tools", {"kb_tools.kb_write"}),
        ("from . import kb_index_lib\n", "kb_tools", {"kb_tools.kb_index_lib"}),
        ("from ..kb_index_lib import X\n", "kb_tools.kb_docgraph", {"kb_tools.kb_index_lib"}),
        ("def f():\n    import yaml\n", "kb_tools", {"yaml"}),
        ('"""Reads YAML without import yaml."""\n', "kb_tools", set()),
    ],
    ids=["stdlib", "package", "deep", "relative", "relative-parent", "in-function", "prose"],
)
def test_the_sweep_sees_every_import_form_and_no_prose(source: str, package: str, expected: set[str]) -> None:
    assert _imports(source, package) == expected
