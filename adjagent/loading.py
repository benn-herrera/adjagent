"""The one loader for the instance packages: `definitions/`, `harnesses/` and
`families/` each hold one module per instance, which defines a fixed
module-level name."""

import importlib
import pkgutil

from adjagent.errors import InputError


def load(package: str, attribute: str) -> dict[str, object]:
    """`attribute` of every module in the dotted `package` whose name does not start with "_", in
    module-name order, keyed by the module name with each "_" read as "-" (`gemma_4` is `gemma-4`).
    A module that does not define `attribute` is refused, naming it."""
    names = sorted(
        info.name
        for info in pkgutil.iter_modules(importlib.import_module(package).__path__)
        if not info.name.startswith("_")
    )
    loaded: dict[str, object] = {}
    for name in names:
        module = importlib.import_module(f"{package}.{name}")
        if not hasattr(module, attribute):
            raise InputError(f"module '{module.__name__}' defines no {attribute}")
        loaded["-".join(name.split("_"))] = getattr(module, attribute)
    return loaded
