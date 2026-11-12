"""The plugin dataclass. The instances, one module each, are in `devpro.plugins`.

A plugin is the selection of definitions one install delivers: a name, and the definition names it
states, either the ones it ships or the ones it leaves out. It holds no harness value and knows no
definition beyond those names."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import cast

from devpro.errors import InputError
from devpro.vocabulary import IDENTIFIER


@dataclass(frozen=True)
class Plugin:
    """A named selection of definitions: `include`, the names it ships, or `exclude`, the names it
    ships every other definition but; exactly one of the two is given."""

    name: str  # the module name; the plugin argument and the value every `{plugin}` template takes
    include: frozenset[str] | None = None
    exclude: frozenset[str] | None = None

    def __post_init__(self) -> None:
        """Refuse a name or a stated definition name that is not a strict-kebab identifier, and a plugin
        giving both sets or neither."""
        if re.fullmatch(IDENTIFIER, self.name) is None:
            raise InputError(f"plugin '{self.name}': name is not a strict-kebab identifier")
        if (self.include is None) == (self.exclude is None):
            raise InputError(f"plugin '{self.name}': give exactly one of include and exclude")
        if any(re.fullmatch(IDENTIFIER, name) is None for name in self.named):
            raise InputError(f"plugin '{self.name}': a stated definition name is not a strict-kebab identifier")

    @property
    def named(self) -> frozenset[str]:
        """The definition names the plugin states, whichever set holds them; `__post_init__` refuses a plugin
        giving neither."""
        return self.include if self.include is not None else cast("frozenset[str]", self.exclude)

    def ships(self, name: str) -> bool:
        """Whether the definition `name` is in this plugin."""
        if self.include is not None:
            return name in self.include
        return name not in self.named
