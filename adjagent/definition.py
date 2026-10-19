"""The `Definition` value: what a definition renders as, where its files go, its
frontmatter values, and its body text; and the `SkillFile` values a skill's
supporting files are. Harness-neutral: no harness spellings, no model names, no
I/O, no rendering."""

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from adjagent.errors import InputError
from adjagent.vocabulary import ALL, IDENTIFIER, TIERS, Kind, Tier, Tool, Tools

_COLOR = r"#[0-9A-Fa-f]{6}"
_ROOTS = {Kind.AGENT: "agents", Kind.DOCUMENT: "agents", Kind.COMMAND: "commands", Kind.SKILL: "skills"}
_SKILL_FILE = "SKILL.md"
_SKILL_FILE_PATH = rf"{IDENTIFIER}\.md"


def _check_body(body: str, where: str) -> None:
    """Refuse a body that is not non-empty text with no leading or trailing newline."""
    if not isinstance(body, str) or not body.strip() or body != body.strip("\n"):
        raise InputError(f"{where}: body must be non-empty text with no leading or trailing newline")


def _check_description(description: str | None, where: str) -> None:
    """Refuse a description that is not one non-empty line holding no double quote: a quote breaks the
    line it emits and the definition then silently fails to load."""
    if not description or '"' in description or "\n" in description:
        raise InputError(f"{where}: description must be one non-empty line holding no double quote")


@dataclass(frozen=True, kw_only=True)
class SkillFile:
    """One supporting file of a skill: its path below the skill's directory, and its body text.

    A path of kebab directory parts and a `.md` name cannot leave the skill's directory and cannot
    name the skill's own `SKILL.md`, whose name is upper-case. The body holds to `Definition.body`'s
    rule: non-empty text, no edge newline, its only holes `vocabulary.hole` placeholders."""

    path: str
    body: str

    def __post_init__(self) -> None:
        """Refuse (InputError, naming the file) a path or a body outside its comment's contract."""
        where = f"skill file '{self.path}'"
        *directories, name = self.path.split("/")
        if (
            not all(re.fullmatch(IDENTIFIER, part) for part in directories)
            or re.fullmatch(_SKILL_FILE_PATH, name) is None
        ):
            raise InputError(f"{where}: path is not kebab directory parts and a .md name")
        _check_body(self.body, where)


@dataclass(frozen=True, kw_only=True)
class Definition:
    """One rendered definition: its kind and place, frontmatter values, and text.

    description is an agent's and a skill's, required for either and refused for any other kind; tools
    and tier are an agent's, and so is color. files are a skill's, and its directory is its name."""

    name: str  # output name, IDENTIFIER
    body: str  # non-empty, no edge newline; its only holes are `vocabulary.hole` placeholders
    kind: Kind
    folder: str = ""  # the path below the output root: IDENTIFIER parts joined by "/", or ""
    description: str | None = None  # one line; emitted double-quoted; holds no '"' and no newline
    tools: Tools | None = None  # see Tools; an empty tuple and a repeated tool are refused
    tier: Tier | None = None  # the seat; the family's tier map binds the model
    color: str | None = None  # "#RRGGBB"; emitted double-quoted
    files: tuple[SkillFile, ...] = ()  # a skill's supporting files; no other kind takes any

    def __post_init__(self) -> None:
        """Refuse (InputError, naming the definition) any field outside its comment's contract."""
        where = f"definition '{self.name}'"
        if re.fullmatch(IDENTIFIER, self.name) is None:
            raise InputError(f"{where}: name is not a strict-kebab identifier")
        if self.folder and not all(re.fullmatch(IDENTIFIER, part) for part in self.folder.split("/")):
            raise InputError(f"{where}: folder '{self.folder}' is not strict-kebab identifiers joined by '/'")
        agent_fields = {"description": self.description, "tools": self.tools, "tier": self.tier}
        if self.kind is Kind.SKILL:
            self._check_skill_fields(where)
        elif self.kind is Kind.AGENT:
            missing = [field for field, value in agent_fields.items() if value is None]
            if missing:
                raise InputError(f"{where}: an agent requires {', '.join(missing)}")
            self._check_agent_fields(where)
        else:
            given = [field for field, value in {**agent_fields, "color": self.color}.items() if value is not None]
            if given:
                raise InputError(f"{where}: a {self.kind.value} takes no {', '.join(given)}")
        if self.files and self.kind is not Kind.SKILL:
            raise InputError(f"{where}: a {self.kind.value} takes no files")
        _check_body(self.body, where)

    def _check_agent_fields(self, where: str) -> None:
        _check_description(self.description, where)
        if self.tools is not ALL:
            if not self.tools or not all(isinstance(tool, Tool) for tool in self.tools):
                raise InputError(f"{where}: tools must be ALL or a non-empty tuple of Tool")
            if len(set(self.tools)) != len(self.tools):
                raise InputError(f"{where}: tools names a tool twice")
        if self.tier not in TIERS:
            raise InputError(f"{where}: tier '{self.tier}' is not one of {', '.join(TIERS)}")
        if self.color is not None and re.fullmatch(_COLOR, self.color) is None:
            raise InputError(f"{where}: color '{self.color}' is not #RRGGBB")

    def _check_skill_fields(self, where: str) -> None:
        """A skill carries a description, no other frontmatter value, and its own directory."""
        if self.description is None:
            raise InputError(f"{where}: a skill requires description")
        _check_description(self.description, where)
        given = [
            field
            for field, value in {"tools": self.tools, "tier": self.tier, "color": self.color}.items()
            if value is not None
        ]
        if given:
            raise InputError(f"{where}: a skill takes no {', '.join(given)}")
        if self.folder:
            raise InputError(f"{where}: a skill takes no folder — its directory is its name")
        paths = [file.path for file in self.files]
        if len(set(paths)) != len(paths):
            raise InputError(f"{where}: files names a path twice")

    @property
    def output_path(self) -> PurePosixPath:
        """`skills/<name>/SKILL.md` for a skill, `agents/<folder>/<name>.md` for an agent or a document,
        `commands/<folder>/<name>.md` for a command; an empty folder adds no part. An agents file has
        none, and asking is refused naming the definition."""
        if self.kind is Kind.AGENTS_FILE:
            raise InputError(f"definition '{self.name}': an agents file has no output path")
        if self.kind is Kind.SKILL:
            return PurePosixPath(_ROOTS[self.kind], self.name, _SKILL_FILE)
        return PurePosixPath(_ROOTS[self.kind], self.folder, f"{self.name}.md")

    def file_output_path(self, file: SkillFile) -> PurePosixPath:
        """`file`'s rendered path: its `path` below this definition's own output directory."""
        return self.output_path.parent / file.path

    @property
    def output_paths(self) -> tuple[PurePosixPath, ...]:
        """`output_path`, then each supporting file's path beneath the directory it sits in."""
        return (self.output_path, *(self.file_output_path(file) for file in self.files))
