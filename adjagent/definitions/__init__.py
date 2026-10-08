"""One module per definition template, registered by existing.

A definition module defines `DEFINITIONS`, a non-empty tuple of `Definition`
values. Nothing in it takes the `Render`, which enters when a section renders;
it may hold private builder functions that take no `ctx`, called to build its
values. A module with several outputs has a longer tuple. There is no list to
join. Its other module-level names are private (`_UPPER`, `_lower`). Text shared
with any other definition lives in `adjagent.sections`. Nothing imports a
definition module by name.

A module is named from its output path below `agents/` or `commands/`, the
folder as a prefix and each "/" and "-" read as "_":
`mad_design_topics_architecture.py` for `agents/mad/design-topics/architecture.md`.
"""

from adjagent.definition import Definition
from adjagent.errors import InputError
from adjagent.loading import load


def definitions_of(module: str, found: object) -> tuple[Definition, ...]:
    """`found`, the dotted `module`'s `DEFINITIONS`, when it is a non-empty tuple of Definition;
    anything else is refused, naming the module."""
    if not isinstance(found, tuple) or not found or not all(isinstance(defn, Definition) for defn in found):
        raise InputError(f"definition module '{module}' defines no DEFINITIONS, a non-empty tuple of Definition")
    return found


def discover() -> tuple[tuple[str, tuple[Definition, ...]], ...]:
    """(dotted module name, its DEFINITIONS) for every module in this package not starting with "_",
    in name order."""
    discovered = []
    for key, found in load(__name__, "DEFINITIONS").items():
        module = f"{__name__}.{'_'.join(key.split('-'))}"
        discovered.append((module, definitions_of(module, found)))
    return tuple(discovered)
