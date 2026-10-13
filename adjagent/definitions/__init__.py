"""One module per definition, or per set of definitions that share text and ship
together, registered by existing.

A definition module is its rendered text with holes, read top to bottom. It
holds imports, string constants and `DEFINITIONS`, a non-empty tuple of
`Definition` values whose `body` is a string, usually an f-string over
`adjagent.clauses` (imported as `from adjagent import clauses`, written
`{clauses.NAME}`) and the module's own constants; its only render-time holes are the
`vocabulary.hole` placeholders, which the renderer fills. A module with several
outputs has a longer tuple. There is no list to join. Its own constants are
private (`_UPPER`): text its definitions share is one of them, and text they
word differently in a few places is a slot constant, a string literal with
`{name}` holes filled where each uses it (`{_NAME.format(name="...")}`). Text
shared with a definition in another module lives in `adjagent.clauses`. A private
constant cannot name `clauses.*`: where shared text holds a harness string, give it a
`{harness_dir}` hole filled at the call site. Nothing imports a definition module
by name.

A module is named from its output path below `agents/` or `commands/`, the
folder as a prefix and each "/" and "-" read as "_": `python_coder.py` for
`agents/python-coder.md`. A module of a set is named for the set:
`mad_design_topics.py` for `agents/mad/design-topics/*.md`, `mad_referees.py`
for the two `agents/mad-*-referee.md`. The harness agents file, which has no
output path, is `harness_agents_file.py`.
"""

import importlib
import pkgutil

from adjagent.definition import Definition
from adjagent.errors import InputError


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
    names = sorted(info.name for info in pkgutil.iter_modules(__path__) if not info.name.startswith("_"))
    for name in names:
        module = f"{__name__}.{name}"
        found = getattr(importlib.import_module(module), "DEFINITIONS", None)
        discovered.append((module, definitions_of(module, found)))
    return tuple(discovered)
