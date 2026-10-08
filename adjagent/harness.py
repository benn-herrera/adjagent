"""The harness dataclass and its two instances, `claude` and `opencode`.

A harness is everything rendered output differs on between harnesses: the
directory and file names prose spells, the tool spellings, the model shape it
accepts, and the frontmatter lines it reads. It holds no tier map, no family and
no knowledge of any one definition. Its emitter only lays out lines; the
renderer maps tools to spellings and computes the governed keys.
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from adjagent.definition import IDENTIFIER, Tool
from adjagent.errors import InputError


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
    frontmatter: Callable[[AgentFields], tuple[str, ...]]  # the field lines between the fences

    def __post_init__(self) -> None:
        """Refuse a non-IDENTIFIER name, an empty string field (inherit_text excepted), or a tools table
        not total in Tool order."""
        if re.fullmatch(IDENTIFIER, self.name) is None:
            raise InputError(f"harness '{self.name}': name is not a strict-kebab identifier")
        texts = (self.agents_file, self.project_harness_dir, self.project_temp_dir, self.user_harness_dir)
        if not all(texts) or not self.model_shape:
            raise InputError(f"harness '{self.name}': an empty string field")
        if tuple(self.tools) != tuple(Tool) or not all(self.tools.values()):
            raise InputError(f"harness '{self.name}': tools table must name every Tool, in Tool order, non-empty")


def _quoted(value: str) -> str:
    return f'"{value}"'


def claude_frontmatter(fields: AgentFields) -> tuple[str, ...]:
    """name; description "…"; model if non-empty; color "…" if set; `tools: A, B` unless tools is None."""
    lines = [f"name: {fields.name}", f"description: {_quoted(fields.description)}"]
    if fields.model:
        lines.append(f"model: {fields.model}")
    if fields.color is not None:
        lines.append(f"color: {_quoted(fields.color)}")
    if fields.tools is not None:
        lines.append(f"tools: {', '.join(fields.tools)}")
    return tuple(lines)


def opencode_frontmatter(fields: AgentFields) -> tuple[str, ...]:
    """description "…"; model if non-empty; color "…" if set; unless tools is None, `permission:` and
    one `  <key>: allow|deny` line per governed key; then `mode: subagent`."""
    lines = [f"description: {_quoted(fields.description)}"]
    if fields.model:
        lines.append(f"model: {fields.model}")
    if fields.color is not None:
        lines.append(f"color: {_quoted(fields.color)}")
    if fields.tools is not None:
        lines.append("permission:")
        lines += [f"  {key}: {'allow' if key in fields.tools else 'deny'}" for key in fields.governed]
    lines.append("mode: subagent")
    return tuple(lines)


claude = Harness(
    name="claude",
    agents_file="CLAUDE.md",
    project_harness_dir=".claude",
    project_temp_dir=".claude-temp",
    user_harness_dir="~/.claude",
    tools={
        Tool.READ: ("Read",),
        Tool.GREP: ("Grep",),
        Tool.GLOB: ("Glob",),
        Tool.EDIT: ("Edit",),
        Tool.WRITE: ("Write",),
        Tool.BASH: ("Bash",),
        Tool.WEBFETCH: ("WebFetch",),
        Tool.WEBSEARCH: ("WebSearch",),
        Tool.AGENT: ("Agent",),
    },
    model_pattern=re.compile(r"^(fable|opus|sonnet|haiku|inherit|claude-\S+)$"),
    model_shape="a Claude alias (fable, opus, sonnet, haiku), a full model id such as claude-opus-4-1, or inherit",
    inherit_text="inherit",
    frontmatter=claude_frontmatter,
)
opencode = Harness(
    name="opencode",
    agents_file="AGENTS.md",
    project_harness_dir=".opencode",
    project_temp_dir=".opencode-temp",
    user_harness_dir="~/.config/opencode",
    tools={
        Tool.READ: ("read",),
        Tool.GREP: ("grep",),
        Tool.GLOB: ("glob", "list"),
        Tool.EDIT: ("edit",),
        Tool.WRITE: ("edit",),
        Tool.BASH: ("bash",),
        Tool.WEBFETCH: ("webfetch",),
        Tool.WEBSEARCH: ("websearch",),
        Tool.AGENT: ("task",),
    },
    model_pattern=re.compile(r"^(inherit|[^/\s]+/\S+)$"),
    model_shape=(
        "provider/model with the provider named as your opencode config names it, "
        "for example omlx/Qwen3.8-Flash-Next, or inherit"
    ),
    inherit_text="",
    frontmatter=opencode_frontmatter,
)
HARNESSES: Mapping[str, Harness] = {h.name: h for h in (claude, opencode)}
