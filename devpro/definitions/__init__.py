"""One module per definition, or per set of definitions that share text and ship
together, registered by existing.

A definition module is its rendered text with placeholders, read top to bottom. It
holds imports, string constants and `DEFINITIONS`, a non-empty tuple of
`Definition` values whose `body` is a string, usually an f-string over
`devpro.clauses` (imported as `from devpro import clauses`, written
`{clauses.NAME}`) and the module's own constants; its only render-time placeholders are
those `vocabulary.hole` spells and the references to other definitions
(`{clauses.ref(name="...")}`), which the renderer fills. A `description` follows the
rule `body=` does, and names another definition the same way. A module with several
outputs has a longer tuple. There is no list to join. A skill's supporting files
are its `files`, each a `SkillFile(path=…, body=…)` whose body follows the rule
`body=` does: its own constants, `clauses.<name>(...)` and a `.format` on one of
its string literals. Its own constants are private (`_UPPER`): text its
definitions share is one of them, and text they word differently in a few places
is a slot constant, a string literal with `{name}` slots filled where each uses
it (`{_NAME.format(name="...")}`). Text shared with a definition in another
module lives in `devpro.clauses`. A private constant cannot name `clauses.*`:
where shared text holds a harness string, give it a `{harness_dir}` slot filled
at the call site. Nothing imports a definition module by name.

A module is named from its output path below `agents/`, `commands/` or
`skills/`, the folder as a prefix and each "/" and "-" read as "_":
`python_coder.py` for `agents/python-coder.md`, `kbase.py` for
`skills/kbase/SKILL.md`. A module of a set is named for the set, not for one
member's output path. The harness agents file, which has no output path, is
`harness_agents_file.py`.
"""

import importlib
import pkgutil

from devpro.definition import Definition
from devpro.errors import InputError


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
