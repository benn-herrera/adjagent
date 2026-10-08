"""One module per definition template, registered by existing.

A definition module defines `DEFINITIONS`, a non-empty tuple of `Definition`
values, and no function: nothing in it takes the `Render`, which enters when a
section renders. A module with several outputs has a longer tuple. There is no
list to join. Beside it sits the module's `Profile`, if its sections read one
(`PYTHON`); its other module-level names are private (`_UPPER`). Text shared with
any other definition lives in `adjagent.sections`. Nothing imports a definition
module by name.
"""

import importlib
import pkgutil
from types import ModuleType

from adjagent.definition import Definition
from adjagent.errors import InputError


def definitions_of(module: ModuleType) -> tuple[Definition, ...]:
    """The module's `DEFINITIONS`; a module without one, or with anything but a non-empty tuple of
    Definition there, is refused, naming it."""
    found = getattr(module, "DEFINITIONS", None)
    if not isinstance(found, tuple) or not found or not all(isinstance(defn, Definition) for defn in found):
        raise InputError(
            f"definition module '{module.__name__}' defines no DEFINITIONS, a non-empty tuple of Definition"
        )
    return found


def discover() -> tuple[tuple[str, tuple[Definition, ...]], ...]:
    """(dotted module name, its DEFINITIONS) for every module in this package not starting with "_",
    in name order."""
    names = sorted(info.name for info in pkgutil.iter_modules(__path__) if not info.name.startswith("_"))
    modules = [importlib.import_module(f"{__name__}.{name}") for name in names]
    return tuple((module.__name__, definitions_of(module)) for module in modules)
