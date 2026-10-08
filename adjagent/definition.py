"""The vocabulary a definition is written in: tiers, tools, overlay anchors, and
the `Definition` value itself. Harness-neutral: no harness spellings, no model
names, no I/O, no rendering."""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from adjagent.errors import InputError

IDENTIFIER = r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*"
"""Output, family and harness names: strict kebab, as CONVENTIONS.md states the class."""

Tier = Literal["highest", "high", "medium", "low", "lowest"]
TIERS: tuple[Tier, ...] = ("highest", "high", "medium", "low", "lowest")
"""Canonical order; every serialization of a tier map uses it."""

_COLOR = r"#[0-9A-Fa-f]{6}"


class Tool(Enum):
    """The harness-neutral tool vocabulary; member order is the order every harness table follows."""

    READ = "read"
    GREP = "grep"
    GLOB = "glob"
    EDIT = "edit"
    WRITE = "write"
    BASH = "bash"
    WEBFETCH = "webfetch"
    WEBSEARCH = "websearch"
    AGENT = "agent"


class Unrestricted(Enum):
    """The typed sentinel for 'no tool restriction authored'."""

    ALL = "all"


ALL = Unrestricted.ALL
Tools = tuple[Tool, ...] | Unrestricted
"""An authored allowlist in authored order, or ALL. ALL emits no tools field on any harness,
which is not the same as a tuple naming all nine tools."""


class Anchor(Enum):
    """The overlay anchors a definition may expose; a family fills them by this key."""

    GAP_AVERSION = "gap-aversion"
    ASK_VS_STIPULATE = "ask-vs-stipulate"


@dataclass(frozen=True)
class Definition:
    """One rendered agent definition: frontmatter values plus its body sections, in order."""

    name: str  # output name, IDENTIFIER; the file is agents/<name>.md
    description: str  # one line; emitted double-quoted; holds no '"' and no newline
    tools: Tools  # see Tools; an empty tuple and a repeated tool are refused
    tier: Tier  # the seat; the family's tier map binds the model
    sections: tuple[str, ...]  # non-empty; each one non-empty, starting and ending with no "\n"
    color: str | None = None  # "#RRGGBB"; emitted double-quoted

    def __post_init__(self) -> None:
        """Refuse (InputError, naming the definition) any field outside its comment's contract."""
        where = f"definition '{self.name}'"
        if re.fullmatch(IDENTIFIER, self.name) is None:
            raise InputError(f"{where}: name is not a strict-kebab identifier")
        if not self.description or '"' in self.description or "\n" in self.description:
            raise InputError(f"{where}: description must be one non-empty line holding no double quote")
        if self.tools is not ALL:
            if not self.tools or not all(isinstance(tool, Tool) for tool in self.tools):
                raise InputError(f"{where}: tools must be ALL or a non-empty tuple of Tool")
            if len(set(self.tools)) != len(self.tools):
                raise InputError(f"{where}: tools names a tool twice")
        if self.tier not in TIERS:
            raise InputError(f"{where}: tier '{self.tier}' is not one of {', '.join(TIERS)}")
        if not self.sections:
            raise InputError(f"{where}: has no sections")
        for index, section in enumerate(self.sections):
            if not section or section.startswith("\n") or section.endswith("\n"):
                raise InputError(f"{where}: section {index} is empty or carries an edge newline")
        if self.color is not None and re.fullmatch(_COLOR, self.color) is None:
            raise InputError(f"{where}: color '{self.color}' is not #RRGGBB")
