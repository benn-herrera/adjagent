"""The harness dataclass. The instances, one module each, are in `adjagent.harnesses`.

A harness is everything rendered output differs on between harnesses: the
directory and file names prose spells, the tool spellings, the model shape it
accepts, and the frontmatter lines it reads. It holds no tier map, no family and
no knowledge of any one definition. Its emitter only lays out lines; the
renderer maps tools to spellings and computes the governed keys.
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from adjagent.errors import InputError
from adjagent.vocabulary import IDENTIFIER, HarnessText, Tool


@dataclass(frozen=True)
class AgentFields:
    """One agent's frontmatter values in the one form every emitter reads: neutral except tool spellings."""

    name: str
    description: str
    model: str  # rendered model text; "" elides the model line
    color: str | None
    tools: tuple[str, ...] | None  # harness spellings, authored order, lists flattened; None = ALL
    governed: tuple[str, ...]  # the image of Harness.tools in table order, de-duplicated


@dataclass(frozen=True)
class Harness:
    """Everything a harness differs on; a new harness fills every field or fails at import."""

    name: str  # "claude", "opencode"; the --harness value
    agents_file: str  # "CLAUDE.md" / "AGENTS.md"
    project_harness_dir: str  # ".claude" / ".opencode"
    project_temp_dir: str  # ".claude-temp" / ".opencode-temp"
    user_harness_dir: str  # "~/.claude" / "~/.config/opencode"
    tools: Mapping[Tool, tuple[str, ...]]  # total over Tool, in Tool order, each non-empty
    model_pattern: re.Pattern[str]  # every tier's rendered text must fullmatch it
    model_shape: str  # the pattern in words; the only form a refusal shows
    inherit_text: str  # what a tier rendering "inherit" emits
    frontmatter: Callable[[AgentFields], tuple[str, ...]]  # an agent's field lines between the fences
    document_frontmatter: tuple[str, ...]  # a document's field lines between the fences

    def __post_init__(self) -> None:
        """Refuse a non-IDENTIFIER name, an empty HarnessText field or model_shape, or a tools table
        not total in Tool order."""
        if re.fullmatch(IDENTIFIER, self.name) is None:
            raise InputError(f"harness '{self.name}': name is not a strict-kebab identifier")
        if not all(self.text(part) for part in HarnessText) or not self.model_shape:
            raise InputError(f"harness '{self.name}': an empty string field")
        if tuple(self.tools) != tuple(Tool) or not all(self.tools.values()):
            raise InputError(f"harness '{self.name}': tools table must name every Tool, in Tool order, non-empty")

    def text(self, part: HarnessText) -> str:
        """The value of the string field `part` names."""
        return getattr(self, part.value)


def quoted(value: str) -> str:
    """A frontmatter value in double quotes, as every emitter writes description and color."""
    return f'"{value}"'
