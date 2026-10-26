"""The harness dataclass. The instances, one module each, are in `adjagent.harnesses`.

A harness is everything rendered output differs on between harnesses: the
directory and file names prose spells, the tool spellings, the model shape it
accepts and the words that render no model at all, whether a map flag's bare
value names the whole map, the frontmatter lines it reads, the rule a dispatched
agent follows when running recipes in its shell, the agents file's
coder-dispatch bullet as a callable over the rendered model, the files it
renders beside the definitions, the definitions it renders nothing for, the
settings file it registers an MCP server in, and the Bash guardrail hook it
registers, where it has one. It holds no tier map, no family and
no knowledge of any one definition. Its emitter only lays out lines; the
renderer maps tools to spellings and computes the governed keys.
"""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

from adjagent.errors import InputError
from adjagent.vocabulary import IDENTIFIER, HarnessText, OptionalHarnessText, Tool


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
class HarnessFile:
    """A file a harness renders into the output root beside the definitions: the path below the root,
    the builder for its whole text, and the marker a file at that path must hold to be one this
    repository wrote (a format admitting no comment carries its ownership as a value inside it)."""

    path: str  # harness-relative, e.g. ".claude-plugin/plugin.json"
    text: Callable[[], str]  # the whole file, final newline included
    marker: str  # the value inside the file that makes it ours


class McpEntryBuilder(Protocol):
    """Builds the `kbase` server entry and the container path it nests under, from the server command
    string and the directory that the command is named relative to when it sits inside it;
    keyword-only, so the two cannot be swapped."""

    def __call__(self, *, command: str, base: Path) -> tuple[dict[str, str | list[str]], tuple[str, ...]]: ...


class McpSite(Enum):
    """Where a harness's MCP settings file lives: at the project root, where the file is the project's own
    and the install edits it in place; or at ROOT, where it is the plugin's own, beside `skills/`."""

    PROJECT = "project"
    HARNESS = "harness"


@dataclass(frozen=True)
class McpSettings:
    """The settings file a harness registers the `kbase` MCP server in. `canonical` is the path relative
    to `site`, created when absent; `alternatives` are the discovered names probed in precedence order,
    a found one overriding the canonical; `site` is the directory those paths are joined to; `entry`
    builds the server entry and the container path it nests under."""

    canonical: str
    alternatives: tuple[str, ...]
    site: McpSite
    entry: McpEntryBuilder


def command_relative(command: str, base: Path) -> str:
    """`command` named relative to `base` in POSIX form, so the settings file names no machine-specific
    path and a project can track it."""
    return Path(command).resolve().relative_to(base.resolve()).as_posix()


class HookClaim(Enum):
    """What one element of a settings file's hook array holds of the guardrail hook: none of it, only
    it, or it beside a command of the project's own."""

    NONE = "none"
    ALONE = "alone"
    SHARED = "shared"


@dataclass(frozen=True)
class GuardrailHook:
    """The Bash guardrail hook a harness ships and registers in a project settings file. `script` is the
    hook script's path under `resources/<harness>/`, which is also its path under the harness directory;
    `settings` is the settings file relative to the project root; `container` is the path in it to the
    array the entry is an element of; `entry` builds the entry from the harness directory's path
    relative to the project root, refusing one it cannot name; `claim` reads an element of that array
    as `entry` writes it, for any harness directory."""

    script: str
    settings: str
    container: tuple[str, ...]
    entry: Callable[[str], dict[str, object]]
    claim: Callable[[object], HookClaim]


@dataclass(frozen=True)
class Harness:
    """Everything a harness differs on; a new harness fills every field or fails at import."""

    name: str  # "claude", "opencode"; the --harness value
    agents_file: str  # "CLAUDE.md" / "AGENTS.md"
    project_harness_dir: str  # ".claude" / ".opencode"
    project_temp_dir: str  # ".claude-temp" / ".opencode-temp"
    user_harness_dir: str  # "~/.claude" / "~/.config/opencode"
    mcp_tool_prefix: str  # "mcp__kbase__" / "kbase_"; this prefix + the tool's own name is its offered name
    recipe_rule: str  # the rule a dispatched agent follows running recipes in its shell; "" where there is none
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
    mcp: McpSettings  # the settings file this harness registers the kbase server in
    guardrail: GuardrailHook | None  # the Bash guardrail hook it registers; None where its own file registers itself
    rendered_files: tuple[HarnessFile, ...] = ()  # files it renders beside the definitions
    omits: frozenset[str] = frozenset()  # definition names it renders nothing for

    def __post_init__(self) -> None:
        """Refuse a non-IDENTIFIER name or omitted definition name, an empty HarnessText field or
        model_shape, a recipe_rule that is not a string, a coder_dispatch that is neither None nor
        callable, a tools table not total in Tool order, an MCP settings contract lacking a canonical
        path, a non-empty alternative name, or a builder, or a guardrail hook lacking a script path, a
        settings path, a container path, a builder, or a recogniser.

        An empty string is refused of the fields a body naming them always renders, since every harness
        supplies each HarnessText and a model shape. `recipe_rule` is an OptionalHarnessText, which a
        harness imposes or does not, so there "" is a value rather than a missing one: it drops the
        paragraph its placeholder stands in."""
        if re.fullmatch(IDENTIFIER, self.name) is None:
            raise InputError(f"harness '{self.name}': name is not a strict-kebab identifier")
        if any(re.fullmatch(IDENTIFIER, name) is None for name in self.omits):
            raise InputError(f"harness '{self.name}': omits holds a name that is not a strict-kebab identifier")
        if not all(self.text(part) for part in HarnessText) or not self.model_shape:
            raise InputError(f"harness '{self.name}': an empty string field")
        if not isinstance(self.recipe_rule, str):
            raise InputError(f"harness '{self.name}': recipe_rule must be a string")
        if self.coder_dispatch is not None and not callable(self.coder_dispatch):
            raise InputError(f"harness '{self.name}': coder_dispatch must be a callable or None")
        if tuple(self.tools) != tuple(Tool) or not all(self.tools.values()):
            raise InputError(f"harness '{self.name}': tools table must name every Tool, in Tool order, non-empty")
        if not self.mcp.canonical or not all(self.mcp.alternatives) or not callable(self.mcp.entry):
            raise InputError(
                f"harness '{self.name}': MCP settings needs a canonical path, non-empty alternative names, "
                "and a builder"
            )
        guardrail = self.guardrail
        if guardrail is not None and not (
            guardrail.script
            and guardrail.settings
            and guardrail.container
            and all(guardrail.container)
            and callable(guardrail.entry)
            and callable(guardrail.claim)
        ):
            raise InputError(
                f"harness '{self.name}': guardrail hook needs a script path, a settings path, a container "
                "path, a builder, and a recogniser"
            )

    def text(self, part: HarnessText | OptionalHarnessText) -> str:
        """The value of the string field `part` names; "" where an optional one is supplied nowhere."""
        return getattr(self, part.value)


def quoted(value: str) -> str:
    """A frontmatter value in double quotes, as every emitter writes description and color."""
    return f'"{value}"'
