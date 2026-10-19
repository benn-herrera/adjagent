"""The harness dataclass. The instances, one module each, are in `adjagent.harnesses`.

A harness is everything rendered output differs on between harnesses: the
directory and file names prose spells, the tool spellings, the model shape it
accepts and the words that render no model at all, whether a map flag's bare
value names the whole map, the frontmatter lines it reads, the agents file's
coder-dispatch bullet as a callable over the rendered model, and the project
settings file it registers an MCP server in. It holds no tier map, no family and
no knowledge of any one definition. Its emitter only lays out lines; the
renderer maps tools to spellings and computes the governed keys.
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

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


class McpEntryBuilder(Protocol):
    """Builds the `kbase` server entry and the container path it nests under, from the server command
    string, the absolute KB root path, and the project root — a path, not a string — that the command
    is named relative to when it sits inside it; keyword-only, so the strings cannot be swapped."""

    def __call__(
        self, *, command: str, kb_root: str, project_root: Path
    ) -> tuple[dict[str, str | list[str]], tuple[str, ...]]: ...


@dataclass(frozen=True)
class McpSettings:
    """The project settings file a harness registers the `kbase` MCP server in. `canonical` is the path
    relative to the project root, created when absent; `alternatives` are the discovered names probed
    in precedence order, a found one overriding the canonical; `entry` builds the server entry and the
    container path it nests under."""

    canonical: str
    alternatives: tuple[str, ...]
    entry: McpEntryBuilder


@dataclass(frozen=True)
class Harness:
    """Everything a harness differs on; a new harness fills every field or fails at import."""

    name: str  # "claude", "opencode"; the --harness value
    agents_file: str  # "CLAUDE.md" / "AGENTS.md"
    project_harness_dir: str  # ".claude" / ".opencode"
    project_temp_dir: str  # ".claude-temp" / ".opencode-temp"
    user_harness_dir: str  # "~/.claude" / "~/.config/opencode"
    mcp_tool_prefix: str  # "mcp__kbase__" / "kbase_"; this prefix + the tool's own name is its offered name
    coder_dispatch: (
        Callable[[str], str] | None
    )  # the agents file's coder-dispatch bullet, built from the rendered model; None where the harness cannot choose a model per dispatch
    tools: Mapping[Tool, tuple[str, ...]]  # total over Tool, in Tool order, each non-empty
    model_pattern: re.Pattern[str]  # every tier's rendered text must fullmatch it
    model_shape: str  # the pattern in words; the only form a refusal shows
    inherit_text: str  # what a tier rendering "inherit" emits
    inherit_synonyms: tuple[str, ...]  # further words emitting inherit_text; model_pattern accepts them
    bare_tier_spec_is_all: bool  # a --model-tier-map value naming no tier is all=<value>
    frontmatter: Callable[[AgentFields], tuple[str, ...]]  # an agent's field lines between the fences
    document_frontmatter: tuple[str, ...]  # a document's field lines between the fences
    mcp: McpSettings  # the project settings file this harness registers the kbase server in

    def __post_init__(self) -> None:
        """Refuse a non-IDENTIFIER name, an empty HarnessText field or model_shape, a coder_dispatch that
        is neither None nor callable, a tools table not total in Tool order, or an MCP settings contract
        lacking a canonical path, a non-empty alternative name, or a builder."""
        if re.fullmatch(IDENTIFIER, self.name) is None:
            raise InputError(f"harness '{self.name}': name is not a strict-kebab identifier")
        if not all(self.text(part) for part in HarnessText) or not self.model_shape:
            raise InputError(f"harness '{self.name}': an empty string field")
        if self.coder_dispatch is not None and not callable(self.coder_dispatch):
            raise InputError(f"harness '{self.name}': coder_dispatch must be a callable or None")
        if tuple(self.tools) != tuple(Tool) or not all(self.tools.values()):
            raise InputError(f"harness '{self.name}': tools table must name every Tool, in Tool order, non-empty")
        if not self.mcp.canonical or not all(self.mcp.alternatives) or not callable(self.mcp.entry):
            raise InputError(
                f"harness '{self.name}': MCP settings needs a canonical path, non-empty alternative names, "
                "and a builder"
            )

    def text(self, part: HarnessText) -> str:
        """The value of the string field `part` names."""
        return getattr(self, part.value)


def quoted(value: str) -> str:
    """A frontmatter value in double quotes, as every emitter writes description and color."""
    return f'"{value}"'
