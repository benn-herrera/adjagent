"""One module per definition, registered by existing.

A definition registers as the file `adjagent/definitions/<snake_name>.py`
defining `def <snake_name>(ctx: Render) -> Definition`, or one returning
`tuple[Definition, ...]` for a module with several outputs. There is no list to
join. A module's other module-level names are private (`_UPPER`); prose shared
with any other definition lives in `adjagent.sections`. Nothing imports a
definition module by name.
"""

import importlib
import pkgutil
from collections.abc import Callable

from adjagent.context import Render
from adjagent.definition import Definition
from adjagent.errors import InputError

DefinitionFunction = Callable[[Render], Definition | tuple[Definition, ...]]


def discover() -> tuple[DefinitionFunction, ...]:
    """Every module in this package not starting with "_" (pkgutil.iter_modules over __path__, sorted
    by name), imported with importlib; each must define a callable named exactly as the module, which
    is its definition function. A module without one is refused, naming it."""
    found = []
    for name in sorted(info.name for info in pkgutil.iter_modules(__path__) if not info.name.startswith("_")):
        module = importlib.import_module(f"{__name__}.{name}")
        function = getattr(module, name, None)
        if not callable(function):
            raise InputError(f"definition module '{module.__name__}' defines no function named '{name}'")
        found.append(function)
    return tuple(found)
