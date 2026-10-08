"""The `Definition` value: what a definition renders as, where its file goes, its
frontmatter values, and its body, a tuple of `Section`. Harness-neutral: no
harness spellings, no model names, no I/O, no rendering."""

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from adjagent.errors import InputError
from adjagent.section import Section
from adjagent.vocabulary import ALL, IDENTIFIER, TIERS, Kind, Tier, Tool, Tools

_COLOR = r"#[0-9A-Fa-f]{6}"
_ROOTS = {Kind.AGENT: "agents", Kind.DOCUMENT: "agents", Kind.COMMAND: "commands"}


@dataclass(frozen=True, kw_only=True)
class Definition:
    """One rendered file: its kind and place, frontmatter values, and body sections, in order.

    description, tools and tier are an agent's, required for one and refused for any other kind; so
    is color."""

    name: str  # output name, IDENTIFIER
    sections: tuple[Section, ...]  # non-empty; rendered in order, joined by a blank line
    kind: Kind = Kind.AGENT
    folder: str = ""  # the path below the output root: IDENTIFIER parts joined by "/", or ""
    description: str | None = None  # one line; emitted double-quoted; holds no '"' and no newline
    tools: Tools | None = None  # see Tools; an empty tuple and a repeated tool are refused
    tier: Tier | None = None  # the seat; the family's tier map binds the model
    color: str | None = None  # "#RRGGBB"; emitted double-quoted

    def __post_init__(self) -> None:
        """Refuse (InputError, naming the definition) any field outside its comment's contract."""
        where = f"definition '{self.name}'"
        if re.fullmatch(IDENTIFIER, self.name) is None:
            raise InputError(f"{where}: name is not a strict-kebab identifier")
        if self.folder and not all(re.fullmatch(IDENTIFIER, part) for part in self.folder.split("/")):
            raise InputError(f"{where}: folder '{self.folder}' is not strict-kebab identifiers joined by '/'")
        agent_fields = {"description": self.description, "tools": self.tools, "tier": self.tier}
        if self.kind is Kind.AGENT:
            missing = [field for field, value in agent_fields.items() if value is None]
            if missing:
                raise InputError(f"{where}: an agent requires {', '.join(missing)}")
            self._check_agent_fields(where)
        else:
            given = [field for field, value in {**agent_fields, "color": self.color}.items() if value is not None]
            if given:
                raise InputError(f"{where}: a {self.kind.value} takes no {', '.join(given)}")
        if not isinstance(self.sections, tuple) or not self.sections:
            raise InputError(f"{where}: sections must be a non-empty tuple")
        for index, section in enumerate(self.sections):
            if not isinstance(section, Section):
                raise InputError(f"{where}: section {index} is a {type(section).__name__}, not a Section")

    def _check_agent_fields(self, where: str) -> None:
        if not self.description or '"' in self.description or "\n" in self.description:
            raise InputError(f"{where}: description must be one non-empty line holding no double quote")
        if self.tools is not ALL:
            if not self.tools or not all(isinstance(tool, Tool) for tool in self.tools):
                raise InputError(f"{where}: tools must be ALL or a non-empty tuple of Tool")
            if len(set(self.tools)) != len(self.tools):
                raise InputError(f"{where}: tools names a tool twice")
        if self.tier not in TIERS:
            raise InputError(f"{where}: tier '{self.tier}' is not one of {', '.join(TIERS)}")
        if self.color is not None and re.fullmatch(_COLOR, self.color) is None:
            raise InputError(f"{where}: color '{self.color}' is not #RRGGBB")

    @property
    def output_path(self) -> PurePosixPath:
        """`agents/<folder>/<name>.md` for an agent or a document, `commands/<folder>/<name>.md` for a
        command; an empty folder adds no part."""
        return PurePosixPath(_ROOTS[self.kind], self.folder, f"{self.name}.md")
